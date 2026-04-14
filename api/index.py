import io
import base64
import json
import requests
import os
import re
import numpy as np
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from PIL import Image, ImageDraw, ImageFont

# Optional OCR — graceful fallback if not installed
try:
    import pytesseract
    from pytesseract import Output as TessOutput
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

# Optional GIF support
try:
    from PIL import ImageSequence
    HAS_GIF = True
except ImportError:
    HAS_GIF = False

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), '..', 'templates'),
    static_folder=os.path.join(os.path.dirname(__file__), '..', 'static')
)
CORS(app)

FONT_PATH    = os.path.join(os.path.dirname(__file__), '..', 'fonts', 'impact.ttf')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
GROQ_VISION_MODELS = [
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "llama-3.2-90b-vision-preview",
]

DEFAULT_ZONES = [
    {"label": "Top text",    "x": 0.0, "y": 0.0,  "w": 1.0, "h": 0.25, "pos": "center"},
    {"label": "Bottom text", "x": 0.0, "y": 0.75, "w": 1.0, "h": 0.25, "pos": "center"},
]

_zone_cache = {}   # url -> {'zones': [...], 'img': PIL.Image}

# ── Download helper ───────────────────────────────────────────────────────────

DOWNLOAD_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36',
    'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://imgflip.com/',
}

def download_image_bytes(url: str, timeout: int = 14) -> bytes:
    """Download image bytes, trying multiple strategies for CORS/blocked URLs."""
    # Strategy 1: direct with spoofed headers
    try:
        resp = requests.get(url, timeout=timeout, headers=DOWNLOAD_HEADERS, allow_redirects=True)
        resp.raise_for_status()
        if len(resp.content) > 100:
            return resp.content
    except Exception as e:
        print(f"[download] direct failed: {e}")

    # Strategy 2: no referer
    try:
        h2 = {k: v for k, v in DOWNLOAD_HEADERS.items() if k != 'Referer'}
        resp = requests.get(url, timeout=timeout, headers=h2, allow_redirects=True)
        resp.raise_for_status()
        if len(resp.content) > 100:
            return resp.content
    except Exception as e:
        print(f"[download] no-referer failed: {e}")

    raise ValueError(f"Could not download image from {url}. The URL may be private or blocked.")


def open_image_safe(raw_bytes: bytes) -> Image.Image:
    """
    Open image bytes safely. Returns a single PIL Image (first frame for GIFs).
    Raises on failure with a clean error message.
    """
    buf = io.BytesIO(raw_bytes)
    buf.seek(0)
    try:
        img = Image.open(buf)
        img.load()  # Force loading so we catch errors here
        # For non-GIF, convert to RGB
        if img.format != 'GIF':
            return img.convert('RGB')
        return img  # Keep GIF as-is
    except Exception as e:
        raise ValueError(f"Could not read image file. Make sure the URL points to a valid image (jpg/png/gif). Detail: {e}")


def is_gif_url(url: str) -> bool:
    return bool(re.search(r'\.gif(\?|$)', url, re.IGNORECASE))


# ── Meme-API subreddits ───────────────────────────────────────────────────────
MEME_SUBREDDITS = [
    "memes","dankmemes","me_irl","AdviceAnimals","funny","wholesomememes",
    "terriblefacebookmemes","okbuddyretard","ProgrammerHumor","gaming",
    "sports","BlackPeopleTwitter","WhitePeopleTwitter","HistoryMemes",
    "ComedyCemetery","surrealmemes","shitposting","deepfriedmemes",
    "nukedmemes","bonehurtingjuice","antimeme","ComedyNecromancy",
    "dogelore","lotrmemes","prequelmemes","sequelmemes","BikiniBottomTwitter",
    "GoodDoggoGoodPupperino","PoliticalHumor","sciencememes","chemicalreactiongifs",
]

_meme_api_cache = {}
_meme_api_all   = []
_meme_api_loaded = False

# ── Extended hardcoded catalog ────────────────────────────────────────────────
EXTRA_CATALOG = [
    {"name":"Surprised Pikachu",          "url":"https://i.imgflip.com/2kbn1e.jpg","genre":"reaction","boxes":1},
    {"name":"Bernie Once Again Asking",   "url":"https://i.imgflip.com/3lmzyx.jpg","genre":"classic", "boxes":1},
    {"name":"Buff Doge vs Cheems",        "url":"https://i.imgflip.com/43a45p.png","genre":"animals", "boxes":4},
    {"name":"Who Would Win",              "url":"https://i.imgflip.com/1g8my4.jpg","genre":"reaction","boxes":2},
    {"name":"This Is Fine Dog",           "url":"https://i.imgflip.com/wxica.jpg", "genre":"reaction","boxes":2},
    {"name":"Gru's Plan 4 Panels",        "url":"https://i.imgflip.com/26jxvz.jpg","genre":"drake",   "boxes":4},
    {"name":"Always Has Been Astronaut",  "url":"https://i.imgflip.com/46e43q.png","genre":"reaction","boxes":2},
    {"name":"Left Exit 12 Off Ramp",      "url":"https://i.imgflip.com/22bdq6.jpg","genre":"drake",   "boxes":2},
    {"name":"Futurama Fry Not Sure If",   "url":"https://i.imgflip.com/6ys.jpg",   "genre":"classic", "boxes":2},
    {"name":"Ancient Aliens Guy",         "url":"https://i.imgflip.com/xgq9k.jpg", "genre":"classic", "boxes":2},
    {"name":"Third World Skeptical Kid",  "url":"https://i.imgflip.com/4t0m5.jpg", "genre":"classic", "boxes":2},
    {"name":"Oprah You Get A Car",        "url":"https://i.imgflip.com/1bhf.jpg",  "genre":"classic", "boxes":2},
    {"name":"Philosoraptor",              "url":"https://i.imgflip.com/rq5n.jpg",  "genre":"classic", "boxes":2},
    {"name":"Confession Bear",            "url":"https://i.imgflip.com/1bgw.jpg",  "genre":"classic", "boxes":2},
    {"name":"Matrix Morpheus",            "url":"https://i.imgflip.com/2fm6x.jpg", "genre":"classic", "boxes":2},
    {"name":"Disaster Girl",              "url":"https://i.imgflip.com/23ls.jpg",  "genre":"classic", "boxes":2},
    {"name":"Bad Luck Brian",             "url":"https://i.imgflip.com/1bip.jpg",  "genre":"classic", "boxes":2},
    {"name":"Success Kid",                "url":"https://i.imgflip.com/1bhk.jpg",  "genre":"classic", "boxes":2},
    {"name":"Good Guy Greg",              "url":"https://i.imgflip.com/6cy.jpg",   "genre":"classic", "boxes":2},
    {"name":"Scumbag Steve",              "url":"https://i.imgflip.com/1biz.jpg",  "genre":"classic", "boxes":2},
    {"name":"Forever Alone",              "url":"https://i.imgflip.com/1bhg.jpg",  "genre":"classic", "boxes":2},
    {"name":"Y U No Guy",                 "url":"https://i.imgflip.com/1bhs.jpg",  "genre":"classic", "boxes":2},
    {"name":"First World Problems",       "url":"https://i.imgflip.com/1bgs.jpg",  "genre":"classic", "boxes":2},
    {"name":"Crying Jordan",              "url":"https://i.imgflip.com/9vct.jpg",  "genre":"sports",  "boxes":2},
    {"name":"Leo DiCaprio Cheers",        "url":"https://i.imgflip.com/3m1ykh.png","genre":"reaction","boxes":1},
    {"name":"Business Cat",               "url":"https://i.imgflip.com/6bz.jpg",   "genre":"animals", "boxes":2},
    {"name":"Actual Advice Mallard",      "url":"https://i.imgflip.com/1biw.jpg",  "genre":"animals", "boxes":2},
    {"name":"Courage Wolf",               "url":"https://i.imgflip.com/1bgv.jpg",  "genre":"animals", "boxes":2},
    {"name":"Patrick Star Not My Problem","url":"https://i.imgflip.com/1bf2j.jpg", "genre":"reaction","boxes":2},
]

# ─────────────────────────────────────────────────────────────────────────────
# LAYOUT LIBRARY
# ─────────────────────────────────────────────────────────────────────────────

_DRAKE = [
    {"label": "No",  "x": 0.52, "y": 0.02, "w": 0.46, "h": 0.46, "pos": "center"},
    {"label": "Yes", "x": 0.52, "y": 0.52, "w": 0.46, "h": 0.46, "pos": "center"},
]
_TWO_BUTTONS = [
    {"label": "Button 1",        "x": 0.05, "y": 0.05, "w": 0.40, "h": 0.30, "pos": "center"},
    {"label": "Button 2",        "x": 0.52, "y": 0.05, "w": 0.40, "h": 0.30, "pos": "center"},
    {"label": "Sweating person", "x": 0.10, "y": 0.60, "w": 0.80, "h": 0.30, "pos": "center"},
]
_DISTRACTED_BF = [
    {"label": "Boyfriend",  "x": 0.30, "y": 0.02, "w": 0.38, "h": 0.18, "pos": "center"},
    {"label": "Other girl", "x": 0.58, "y": 0.50, "w": 0.40, "h": 0.38, "pos": "center"},
    {"label": "Girlfriend", "x": 0.02, "y": 0.50, "w": 0.40, "h": 0.38, "pos": "center"},
]
_EXPANDING_BRAIN = [
    {"label": "Tiny brain",   "x": 0.0, "y": 0.0,  "w": 0.52, "h": 0.25, "pos": "center"},
    {"label": "Medium brain", "x": 0.0, "y": 0.25, "w": 0.52, "h": 0.25, "pos": "center"},
    {"label": "Large brain",  "x": 0.0, "y": 0.50, "w": 0.52, "h": 0.25, "pos": "center"},
    {"label": "Galaxy brain", "x": 0.0, "y": 0.75, "w": 0.52, "h": 0.25, "pos": "center"},
]
_GRU_PLAN = [
    {"label": "Step 1 (plan)", "x": 0.52, "y": 0.01, "w": 0.46, "h": 0.24, "pos": "center"},
    {"label": "Step 2",        "x": 0.52, "y": 0.26, "w": 0.46, "h": 0.24, "pos": "center"},
    {"label": "Step 3 (oops)", "x": 0.52, "y": 0.51, "w": 0.46, "h": 0.24, "pos": "center"},
    {"label": "Step 4",        "x": 0.52, "y": 0.76, "w": 0.46, "h": 0.24, "pos": "center"},
]
_CHANGE_MY_MIND   = [{"label": "Controversial opinion", "x": 0.30, "y": 0.52, "w": 0.55, "h": 0.32, "pos": "center"}]
_WOMAN_CAT        = [{"label": "Yelling woman", "x": 0.0, "y": 0.0, "w": 0.50, "h": 1.0, "pos": "center"}, {"label": "Smug cat", "x": 0.5, "y": 0.0, "w": 0.50, "h": 1.0, "pos": "center"}]
_SPIDERMAN        = [{"label": "Left", "x": 0.0, "y": 0.0, "w": 0.50, "h": 1.0, "pos": "center"}, {"label": "Right", "x": 0.5, "y": 0.0, "w": 0.50, "h": 1.0, "pos": "center"}]
_BATMAN_SLAP      = [{"label": "Batman says", "x": 0.02, "y": 0.02, "w": 0.44, "h": 0.40, "pos": "center"}, {"label": "Robin says", "x": 0.54, "y": 0.02, "w": 0.44, "h": 0.40, "pos": "center"}]
_CLASSIC_TOP_BOTTOM = [{"label": "Top text", "x": 0.0, "y": 0.0, "w": 1.0, "h": 0.20, "pos": "center"}, {"label": "Bottom text", "x": 0.0, "y": 0.80, "w": 1.0, "h": 0.20, "pos": "center"}]
_BERNIE           = [{"label": "I am once again asking", "x": 0.0, "y": 0.62, "w": 1.0, "h": 0.33, "pos": "center"}]
_THIS_IS_FINE     = [{"label": "Caption", "x": 0.0, "y": 0.0, "w": 1.0, "h": 0.18, "pos": "center"}]
_ALWAYS_HAS_BEEN  = [{"label": "Wait, it's all…", "x": 0.02, "y": 0.28, "w": 0.44, "h": 0.32, "pos": "center"}, {"label": "Always has been", "x": 0.54, "y": 0.08, "w": 0.44, "h": 0.32, "pos": "center"}]
_LEFT_EXIT        = [{"label": "The exit (temptation)", "x": 0.30, "y": 0.04, "w": 0.35, "h": 0.28, "pos": "center"}, {"label": "Car label", "x": 0.60, "y": 0.55, "w": 0.38, "h": 0.22, "pos": "center"}]
_STONKS           = [{"label": "Top", "x": 0.0, "y": 0.0, "w": 1.0, "h": 0.20, "pos": "center"}, {"label": "Bottom", "x": 0.0, "y": 0.80, "w": 1.0, "h": 0.20, "pos": "center"}]
_BUFF_DOGE_CHEEMS = [{"label": "Buff Doge (strong)", "x": 0.0, "y": 0.0, "w": 0.50, "h": 1.0, "pos": "center"}, {"label": "Cheems (weak)", "x": 0.50, "y": 0.0, "w": 0.50, "h": 1.0, "pos": "center"}]
_WHO_WOULD_WIN    = [{"label": "Side A", "x": 0.0, "y": 0.0, "w": 0.45, "h": 1.0, "pos": "center"}, {"label": "Side B", "x": 0.55, "y": 0.0, "w": 0.45, "h": 1.0, "pos": "center"}]
_TRADE_OFFER      = [{"label": "I receive", "x": 0.0, "y": 0.3, "w": 0.48, "h": 0.4, "pos": "center"}, {"label": "You receive", "x": 0.52, "y": 0.3, "w": 0.48, "h": 0.4, "pos": "center"}]
_PANIK_KALM       = [{"label": "Panik (top)", "x": 0.55, "y": 0.0, "w": 0.44, "h": 0.33, "pos": "center"}, {"label": "Kalm (middle)", "x": 0.55, "y": 0.33, "w": 0.44, "h": 0.33, "pos": "center"}, {"label": "Panik (bottom)", "x": 0.55, "y": 0.66, "w": 0.44, "h": 0.33, "pos": "center"}]
_WOMAN_WINDOW     = [{"label": "Person's label", "x": 0.0, "y": 0.55, "w": 0.48, "h": 0.42, "pos": "center"}, {"label": "Window thing", "x": 0.52, "y": 0.05, "w": 0.46, "h": 0.42, "pos": "center"}]

NAME_LAYOUTS = [
    (["drake","hotline bling"],                        _DRAKE),
    (["two buttons","two button"],                     _TWO_BUTTONS),
    (["distracted boyfriend","distracted bf"],         _DISTRACTED_BF),
    (["expanding brain","galaxy brain","brain size"],  _EXPANDING_BRAIN),
    (["gru's plan","gru plan","gru's"],                _GRU_PLAN),
    (["change my mind"],                               _CHANGE_MY_MIND),
    (["woman yelling","yelling at cat","woman cat"],   _WOMAN_CAT),
    (["spider-man","spiderman","pointing spider"],     _SPIDERMAN),
    (["batman slap","batman slapping","slap robin"],   _BATMAN_SLAP),
    (["bernie","once again asking"],                   _BERNIE),
    (["this is fine"],                                 _THIS_IS_FINE),
    (["always has been"],                              _ALWAYS_HAS_BEEN),
    (["left exit 12","left exit"],                     _LEFT_EXIT),
    (["stonks"],                                       _STONKS),
    (["buff doge","cheems"],                           _BUFF_DOGE_CHEEMS),
    (["who would win"],                                _WHO_WOULD_WIN),
    (["trade offer"],                                  _TRADE_OFFER),
    (["panik","kalm"],                                 _PANIK_KALM),
    (["woman window","woman looking out"],             _WOMAN_WINDOW),
    (["one does not simply","boromir"],                _CLASSIC_TOP_BOTTOM),
    (["roll safe","think about it"],                   _CLASSIC_TOP_BOTTOM),
    (["hide the pain","harold"],                       _CLASSIC_TOP_BOTTOM),
    (["mocking spongebob","spongebob mocking"],        _CLASSIC_TOP_BOTTOM),
    (["pikachu","surprised pikachu"],                  _CLASSIC_TOP_BOTTOM),
    (["disaster girl"],                                _CLASSIC_TOP_BOTTOM),
    (["is this a pigeon","is this"],                   _CLASSIC_TOP_BOTTOM),
    (["grumpy cat","no grumpy"],                       _CLASSIC_TOP_BOTTOM),
    (["success kid"],                                  _CLASSIC_TOP_BOTTOM),
    (["bad luck brian"],                               _CLASSIC_TOP_BOTTOM),
    (["good guy greg"],                                _CLASSIC_TOP_BOTTOM),
    (["scumbag steve"],                                _CLASSIC_TOP_BOTTOM),
    (["ancient aliens"],                               _CLASSIC_TOP_BOTTOM),
    (["futurama fry","not sure if"],                   _CLASSIC_TOP_BOTTOM),
    (["doge"],                                         _CLASSIC_TOP_BOTTOM),
    (["forever alone"],                                _CLASSIC_TOP_BOTTOM),
    (["y u no"],                                       _CLASSIC_TOP_BOTTOM),
    (["overly attached girlfriend"],                   _CLASSIC_TOP_BOTTOM),
    (["creepy condescending wonka"],                   _CLASSIC_TOP_BOTTOM),
    (["confession bear"],                              _CLASSIC_TOP_BOTTOM),
    (["first world problems"],                         _CLASSIC_TOP_BOTTOM),
    (["matrix morpheus","what if i told you"],         _CLASSIC_TOP_BOTTOM),
    (["third world skeptical kid","skeptical kid"],    _CLASSIC_TOP_BOTTOM),
    (["blinking guy","blinking white guy"],            _CLASSIC_TOP_BOTTOM),
    (["epic handshake"],                               _CLASSIC_TOP_BOTTOM),
    (["philosoraptor"],                                _CLASSIC_TOP_BOTTOM),
    (["tuxedo winnie","tuxedo pooh"],                  _DRAKE),
    (["uno draw","draw 25"],                           [
        {"label":"Option",  "x":0.52,"y":0.04,"w":0.44,"h":0.42,"pos":"center"},
        {"label":"Or draw", "x":0.0, "y":0.62,"w":1.0, "h":0.33,"pos":"center"},
    ]),
]

ID_LAYOUTS = {
    "181913649": _DRAKE, "87743020": _TWO_BUTTONS, "112126428": _DISTRACTED_BF,
    "93895088": _EXPANDING_BRAIN, "131940431": _GRU_PLAN, "129242436": _CHANGE_MY_MIND,
    "188390779": _WOMAN_CAT, "101470": _SPIDERMAN, "9440985": _BATMAN_SLAP,
    "91538330": _BERNIE, "55311130": _THIS_IS_FINE, "252600902": _ALWAYS_HAS_BEEN,
    "124822590": _LEFT_EXIT, "89370399": _CLASSIC_TOP_BOTTOM, "27813981": _CLASSIC_TOP_BOTTOM,
    "102156234": _CLASSIC_TOP_BOTTOM, "61579": _CLASSIC_TOP_BOTTOM,
    "119139145": _CLASSIC_TOP_BOTTOM, "161865971": _CLASSIC_TOP_BOTTOM,
    "217743513": _CLASSIC_TOP_BOTTOM, "4087833": _CLASSIC_TOP_BOTTOM,
    "135256802": _CLASSIC_TOP_BOTTOM, "322841258": _CLASSIC_TOP_BOTTOM,
    "247375501": _BUFF_DOGE_CHEEMS, "301733230": _TRADE_OFFER, "226297822": _PANIK_KALM,
}


def match_layout_by_name(name: str):
    lower = name.lower()
    for keywords, layout in NAME_LAYOUTS:
        if any(kw in lower for kw in keywords):
            return layout
    return None


def match_layout_by_url(url: str):
    m = re.search(r'/(\d{5,12})(?:[/.])', url)
    if m:
        return ID_LAYOUTS.get(m.group(1))
    return None


# ── Pixel analysis ────────────────────────────────────────────────────────────

def detect_zones_from_pixels(img: Image.Image):
    w, h = img.size
    arr  = np.array(img.convert('RGB'), dtype=np.float32)
    BRIGHT = 215
    col_brightness = arr.mean(axis=(0, 2))
    row_brightness = arr.mean(axis=(1, 2))
    col_runs = _find_runs(col_brightness > BRIGHT, 0.20, w)
    row_runs = _find_runs(row_brightness > BRIGHT, 0.15, h)
    zones = []
    if col_runs and not row_runs:
        for x0, x1 in col_runs:
            col_arr  = arr[:, x0:x1, :]
            sub_rows = _find_runs(col_arr.mean(axis=(1,2)) > BRIGHT, 0.25, h)
            if len(sub_rows) >= 2:
                for y0, y1 in sub_rows:
                    zones.append(_zone(x0, y0, x1-x0, y1-y0, w, h, f"Panel {len(zones)+1}"))
            else:
                zones.append(_zone(x0, 0, x1-x0, h, w, h, f"Panel {len(zones)+1}"))
    elif row_runs and not col_runs:
        for y0, y1 in row_runs:
            zones.append(_zone(0, y0, w, y1-y0, w, h, f"Panel {len(zones)+1}"))
    elif col_runs and row_runs:
        for y0, y1 in row_runs:
            for x0, x1 in col_runs:
                zones.append(_zone(x0, y0, x1-x0, y1-y0, w, h, f"Cell {len(zones)+1}"))
    if not zones:
        top_b = float(arr[:int(h*0.18),:,:].mean())
        bot_b = float(arr[int(h*0.82):,:,:].mean())
        mid_b = float(arr[int(h*0.2):int(h*0.8),:,:].mean())
        if top_b > BRIGHT and top_b > mid_b + 20:
            zones.append({"label":"Top text",    "x":0.0,"y":0.0, "w":1.0,"h":0.18,"pos":"center"})
        if bot_b > BRIGHT and bot_b > mid_b + 20:
            zones.append({"label":"Bottom text", "x":0.0,"y":0.82,"w":1.0,"h":0.18,"pos":"center"})
    return zones if zones else None


def _zone(px, py, pw, ph, img_w, img_h, label):
    p = 0.01
    return {"label":label, "x":max(0.0,px/img_w+p), "y":max(0.0,py/img_h+p),
            "w":min(1.0,pw/img_w-p*2), "h":min(1.0,ph/img_h-p*2), "pos":"center"}


def _find_runs(mask, min_frac, total):
    min_len = max(1, int(min_frac * total))
    runs, in_run, start = [], False, 0
    for i, v in enumerate(mask):
        if v and not in_run:   in_run, start = True, i
        elif not v and in_run:
            in_run = False
            if i - start >= min_len: runs.append((start, i))
    if in_run and total - start >= min_len: runs.append((start, total))
    return runs


# ── AI fallback ───────────────────────────────────────────────────────────────

def _call_groq_ai(url):
    if not GROQ_API_KEY: return None
    prompt = ("Return ONLY a JSON array of meme text zones. "
              "Each: {\"label\":str,\"x\":float,\"y\":float,\"w\":float,\"h\":float,\"pos\":\"center\"}. "
              "x,y=top-left corner (0-1 fraction), w,h=size (0-1 fraction). "
              "Zones must cover where TEXT goes, not the photo. No markdown.")
    for model in GROQ_VISION_MODELS:
        try:
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type":"application/json"},
                json={"model":model,"messages":[{"role":"user","content":[
                    {"type":"image_url","image_url":{"url":url}},
                    {"type":"text","text":prompt},
                ]}],"max_tokens":400,"temperature":0.1}, timeout=15,
            )
            r.raise_for_status()
            raw   = re.sub(r"```(?:json)?|```","",r.json()["choices"][0]["message"]["content"]).strip()
            zones = json.loads(raw)
            valid = [z for z in zones if all(k in z for k in ("x","y","w","h")) and float(z["w"])>=0.25]
            if valid: return valid
        except Exception as exc:
            print(f"[zones] AI {model}: {exc}")
    return None


def resolve_zones(url, name, img):
    z = match_layout_by_url(url);   
    if z: print(f"[zones] ID match '{name}'"); return z
    z = match_layout_by_name(name); 
    if z: print(f"[zones] name match '{name}'"); return z
    z = detect_zones_from_pixels(img)
    if z: print(f"[zones] pixel analysis {len(z)} zones '{name}'"); return z
    z = _call_groq_ai(url)
    if z: print(f"[zones] AI zones '{name}'"); return z
    print(f"[zones] DEFAULT '{name}'"); return DEFAULT_ZONES


# ── OCR text extraction ───────────────────────────────────────────────────────

def _merge_nearby_boxes(data, img_w, img_h, gap_frac=0.03):
    words = []
    for i in range(len(data['text'])):
        t = data['text'][i].strip()
        if not t or int(data['conf'][i]) < 40:
            continue
        words.append({
            'text': t,
            'x': data['left'][i],
            'y': data['top'][i],
            'w': data['width'][i],
            'h': data['height'][i],
            'block': data['block_num'][i],
            'par':   data['par_num'][i],
            'line':  data['line_num'][i],
        })
    if not words:
        return []
    groups = {}
    for w in words:
        key = (w['block'], w['par'], w['line'])
        groups.setdefault(key, []).append(w)
    regions = []
    for key, ws in groups.items():
        text = ' '.join(w['text'] for w in ws)
        if len(text.strip()) < 2:
            continue
        x0 = min(w['x'] for w in ws)
        y0 = min(w['y'] for w in ws)
        x1 = max(w['x'] + w['w'] for w in ws)
        y1 = max(w['y'] + w['h'] for w in ws)
        regions.append({'text': text, 'x': x0, 'y': y0, 'w': x1 - x0, 'h': y1 - y0})
    return regions


def _regions_to_zones(regions, img_w, img_h, pad_frac=0.015):
    zones = []
    for r in regions:
        px = max(0, r['x'] - int(img_w * pad_frac))
        py = max(0, r['y'] - int(img_h * pad_frac))
        pw = min(img_w, r['w'] + int(img_w * pad_frac * 2))
        ph = min(img_h, r['h'] + int(img_h * pad_frac * 2))
        if pw / img_w < 0.05 or ph / img_h < 0.02:
            continue
        zones.append({
            'label': r['text'][:40],
            'text':  r['text'],
            'x': round(px / img_w, 4),
            'y': round(py / img_h, 4),
            'w': round(min(pw / img_w, 1.0), 4),
            'h': round(min(ph / img_h, 1.0), 4),
            'pos': 'center',
        })
    return zones


def _preprocess_for_ocr(pil_img):
    from PIL import ImageEnhance, ImageFilter
    variants = [pil_img]
    grey = pil_img.convert('L')
    enhanced = ImageEnhance.Contrast(grey).enhance(2.5)
    variants.append(enhanced.convert('RGB'))
    return variants


def ocr_extract(img: Image.Image):
    if not HAS_TESSERACT:
        return None
    img_w, img_h = img.size
    best_zones = []
    for variant in _preprocess_for_ocr(img):
        try:
            data = pytesseract.image_to_data(
                variant, lang='eng',
                config='--psm 11 --oem 1',
                output_type=TessOutput.DICT,
            )
            regions = _merge_nearby_boxes(data, img_w, img_h)
            zones   = _regions_to_zones(regions, img_w, img_h)
            if len(zones) > len(best_zones):
                best_zones = zones
        except Exception as e:
            print(f"[ocr] variant failed: {e}")
    return best_zones if best_zones else None


# ── Rendering ─────────────────────────────────────────────────────────────────

def get_font(size):
    size = max(10, int(size))
    try:
        if os.path.exists(FONT_PATH):
            return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        pass
    try:    return ImageFont.load_default(size=size)
    except TypeError: return ImageFont.load_default()


def get_font_size(font):
    return font.size if hasattr(font, 'size') else 12


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines, cur = [], []
    for word in words:
        candidate = ' '.join(cur + [word])
        if draw.textbbox((0,0), candidate, font=font)[2] <= max_width:
            cur.append(word)
        else:
            if cur: lines.append(' '.join(cur))
            cur = [word]
    if cur: lines.append(' '.join(cur))
    return lines or ['']


def draw_text_block(draw, text, img_w, img_h, zone, color, preferred_size):
    zx = int(zone.get('x', 0.0) * img_w)
    zy = int(zone.get('y', 0.0) * img_h)
    zw = int(zone.get('w', 1.0) * img_w)
    zh = int(zone.get('h', 1.0) * img_h)
    if zw < 10 or zh < 10: return

    pad     = max(4, int(min(zw, zh) * 0.05))
    avail_w = max(1, zw - pad * 2)
    avail_h = max(1, zh - pad * 2)
    max_start = max(10, int(zh * 0.45))
    cur_size  = min(int(preferred_size), max_start)
    final_lines = final_font = None

    while cur_size >= 10:
        font  = get_font(cur_size)
        lines = wrap_text(draw, text, font, avail_w)
        bbox  = draw.textbbox((0,0), 'Ay', font=font)
        lh    = (bbox[3]-bbox[1]) + max(1, int(cur_size*0.15))
        if lh * len(lines) <= avail_h:
            final_lines, final_font = lines, font; break
        cur_size -= 2

    if final_font is None:
        final_font  = get_font(10)
        final_lines = wrap_text(draw, text, final_font, avail_w)

    bbox    = draw.textbbox((0,0), 'Ay', font=final_font)
    fsize   = get_font_size(final_font)
    lh      = (bbox[3]-bbox[1]) + max(1, int(fsize*0.15))
    total_h = lh * len(final_lines)

    pos = zone.get('pos', 'center')
    start_y = (zy+pad if pos=='top' else
               zy+zh-total_h-pad if pos=='bottom' else
               zy+(zh-total_h)//2)

    stroke_w = max(1, int(fsize*0.07))
    curr_y   = start_y
    for line in final_lines:
        lb = draw.textbbox((0,0), line, font=final_font)
        lw = lb[2]-lb[0]
        cx = zx + (zw-lw)//2
        for ox in range(-stroke_w, stroke_w+1):
            for oy in range(-stroke_w, stroke_w+1):
                if ox==0 and oy==0: continue
                draw.text((cx+ox, curr_y+oy), line, font=final_font, fill=(0,0,0))
        draw.text((cx, curr_y), line, font=final_font, fill=color)
        curr_y += lh


def _pixel_size_from_params(zone, img_h, preferred):
    """Compute pixel font size for a zone+preference combination."""
    zone_h_px  = max(1, zone.get('h', 0.2) * img_h)
    pct        = (preferred - 14) / (80 - 14)
    size_frac  = 0.30 + pct * 0.55
    pixel_size = int(zone_h_px * size_frac)
    return max(14, pixel_size)


# ── Meme sources ──────────────────────────────────────────────────────────────

def _fetch_imgflip():
    try:
        r = requests.get('https://api.imgflip.com/get_memes', timeout=8)
        data = r.json()
        if data.get('success'):
            return [{'id':m['id'],'name':m['name'],'url':m['url'],
                     'width':m['width'],'height':m['height'],'boxes':m['box_count'],
                     'source':'imgflip'} for m in data['data']['memes']]
    except Exception as e:
        print(f"[memes] imgflip: {e}")
    return []


def _fetch_meme_api(subreddit, count=20):
    try:
        r = requests.get(
            f'https://meme-api.com/gimme/{subreddit}/{count}',
            timeout=8, headers={'User-Agent': 'MemeForge/1.0'}
        )
        data = r.json()
        memes = []
        for m in data.get('memes', []):
            if m.get('url','').lower().endswith(('.jpg','.jpeg','.png','.gif','.webp')):
                memes.append({
                    'id':   m.get('postLink','').split('/')[-2] or m['title'][:20],
                    'name': m['title'], 'url':  m['url'],
                    'width':  m.get('preview',[None])[-1], 'height': None,
                    'boxes': 2, 'source': f'reddit/{subreddit}', 'nsfw': m.get('nsfw', False),
                })
        return [m for m in memes if not m['nsfw']]
    except Exception as e:
        print(f"[memes] meme-api {subreddit}: {e}")
    return []


def _build_meme_pool(subreddits=None, per_sub=15):
    seen_urls = set()
    pool = []
    for m in _fetch_imgflip():
        if m['url'] not in seen_urls:
            seen_urls.add(m['url']); pool.append(m)
    subs = subreddits or MEME_SUBREDDITS[:8]
    for sub in subs:
        for m in _fetch_meme_api(sub, per_sub):
            if m['url'] not in seen_urls:
                seen_urls.add(m['url']); pool.append(m)
    for m in EXTRA_CATALOG:
        if m['url'] not in seen_urls:
            seen_urls.add(m['url'])
            pool.append({'id':m['url'],'name':m['name'],'url':m['url'],
                         'width':500,'height':500,'boxes':m['boxes'],'source':'catalog'})
    return pool


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/memes')
def api_memes():
    global _meme_api_all, _meme_api_loaded

    page     = int(request.args.get('page', 0))
    per_page = min(int(request.args.get('per_page', 24)), 48)
    q        = request.args.get('q', '').lower().strip()
    subs_raw = request.args.get('subreddits', '')
    subs     = [s.strip() for s in subs_raw.split(',') if s.strip()] if subs_raw else None

    if not _meme_api_loaded or subs:
        _meme_api_all   = _build_meme_pool(subs)
        _meme_api_loaded = True

    pool = _meme_api_all
    if q:
        pool = [m for m in pool if q in m['name'].lower()]

    total      = len(pool)
    start      = page * per_page
    end        = start + per_page
    page_items = pool[start:end]

    return jsonify({
        'memes': page_items, 'total': total,
        'page': page, 'per_page': per_page, 'has_more': end < total,
    })


@app.route('/api/extract-text', methods=['POST'])
def extract_text():
    body = request.json or {}
    url  = body.get('image_url', '').strip()
    if not url:
        return jsonify({'error': 'image_url required'}), 400

    try:
        raw = download_image_bytes(url)
        img = open_image_safe(raw)
        # For OCR/zone work, use first frame if GIF
        if getattr(img, 'format', None) == 'GIF':
            img_rgb = img.convert('RGB')
        else:
            img_rgb = img
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Could not load image: {e}'}), 400

    img_w, img_h = img_rgb.size

    zones = ocr_extract(img_rgb)
    method = 'ocr'

    if not zones:
        method = 'fallback'
        z = resolve_zones(url, '', img_rgb)
        zones = [{**zone, 'text': ''} for zone in z]

    # Cache for /generate (store original img to preserve GIF)
    _zone_cache[url] = {'zones': zones, 'img': img_rgb, 'raw': raw}

    return jsonify({
        'zones': zones, 'method': method,
        'has_tesseract': HAS_TESSERACT,
        'img_w': img_w, 'img_h': img_h,
    })


@app.route('/zones', methods=['POST'])
def get_zones():
    body      = request.json or {}
    url       = body.get('image_url', '').strip()
    meme_name = body.get('meme_name', '').strip()

    if not url:
        return jsonify({'zones': DEFAULT_ZONES, 'fallback': True})

    if url in _zone_cache:
        entry = _zone_cache[url]
        return jsonify({'zones': entry['zones'], 'fallback': False})

    try:
        raw = download_image_bytes(url, timeout=10)
        img = open_image_safe(raw)
        if getattr(img, 'format', None) == 'GIF':
            img_rgb = img.convert('RGB')
        else:
            img_rgb = img
    except Exception as e:
        print(f"[zones] Download failed: {e}")
        return jsonify({'zones': DEFAULT_ZONES, 'fallback': True})

    zones = resolve_zones(url, meme_name, img_rgb)
    _zone_cache[url] = {'zones': zones, 'img': img_rgb, 'raw': raw}
    return jsonify({'zones': zones, 'fallback': False})


@app.route('/generate', methods=['POST'])
def generate():
    """Generate a static meme (PNG). Used for non-GIF images."""
    try:
        data         = request.json or {}
        image_url    = data.get('image_url', '').strip()
        texts        = data.get('texts', [])
        client_zones = data.get('zones', None)
        preferred    = max(10, int(data.get('font_size', 40)))
        c_hex        = data.get('text_color', '#FFFFFF').lstrip('#').zfill(6)
        color        = tuple(int(c_hex[i:i+2], 16) for i in (0, 2, 4))

        cached = _zone_cache.get(image_url, {})
        if isinstance(cached, dict) and 'img' in cached:
            img   = cached['img'].copy()
            zones = cached['zones']
        else:
            raw  = download_image_bytes(image_url)
            img  = open_image_safe(raw)
            if getattr(img, 'format', None) == 'GIF':
                img = img.convert('RGB')
            zones = cached.get('zones', DEFAULT_ZONES) if isinstance(cached, dict) else DEFAULT_ZONES

        if client_zones and isinstance(client_zones, list) and len(client_zones) > 0:
            zones = client_zones

        img_w, img_h = img.size
        draw = ImageDraw.Draw(img)

        for i, zone in enumerate(zones):
            if i < len(texts) and texts[i].strip():
                pixel_size = _pixel_size_from_params(zone, img_h, preferred)
                short_side = min(img_w, img_h)
                pixel_size = min(pixel_size, short_side // 4)
                draw_text_block(draw, texts[i].upper(), img_w, img_h, zone, color, pixel_size)

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return jsonify({'image': base64.b64encode(buf.getvalue()).decode()})

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/generate-gif', methods=['POST'])
def generate_gif():
    """
    Generate an animated GIF meme with text overlaid on every frame.
    Falls back to static PNG if GIF processing fails.
    """
    try:
        data         = request.json or {}
        image_url    = data.get('image_url', '').strip()
        texts        = data.get('texts', [])
        client_zones = data.get('zones', None)
        preferred    = max(10, int(data.get('font_size', 40)))
        c_hex        = data.get('text_color', '#FFFFFF').lstrip('#').zfill(6)
        color        = tuple(int(c_hex[i:i+2], 16) for i in (0, 2, 4))

        cached = _zone_cache.get(image_url, {})
        raw    = cached.get('raw') if isinstance(cached, dict) else None

        if raw is None:
            raw = download_image_bytes(image_url)
            if isinstance(cached, dict):
                cached['raw'] = raw
                _zone_cache[image_url] = cached

        zones = (cached.get('zones', DEFAULT_ZONES) if isinstance(cached, dict) else DEFAULT_ZONES)
        if client_zones and isinstance(client_zones, list) and len(client_zones) > 0:
            zones = client_zones

        # Try to open as GIF
        gif_buf = io.BytesIO(raw)
        gif_buf.seek(0)
        src = Image.open(gif_buf)

        if getattr(src, 'format', None) != 'GIF' or not getattr(src, 'is_animated', False):
            # Not actually animated — fall back to static PNG
            img = src.convert('RGB')
            img_w, img_h = img.size
            draw = ImageDraw.Draw(img)
            for i, zone in enumerate(zones):
                if i < len(texts) and texts[i].strip():
                    pixel_size = min(_pixel_size_from_params(zone, img_h, preferred), min(img_w, img_h) // 4)
                    draw_text_block(draw, texts[i].upper(), img_w, img_h, zone, color, pixel_size)
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            return jsonify({'image': base64.b64encode(buf.getvalue()).decode()})

        # Extract frames, draw text on each
        frames = []
        durations = []
        try:
            for frame in ImageSequence.Iterator(src):
                fr = frame.copy().convert('RGBA')
                img_w, img_h = fr.size
                # Composite onto white background for drawing
                bg = Image.new('RGBA', (img_w, img_h), (255, 255, 255, 255))
                bg.paste(fr, mask=fr.split()[3] if fr.mode == 'RGBA' else None)
                draw = ImageDraw.Draw(bg)
                for i, zone in enumerate(zones):
                    if i < len(texts) and texts[i].strip():
                        pixel_size = min(_pixel_size_from_params(zone, img_h, preferred), min(img_w, img_h) // 4)
                        draw_text_block(draw, texts[i].upper(), img_w, img_h, zone, color, pixel_size)
                frames.append(bg.convert('P', palette=Image.ADAPTIVE, dither=Image.Dither.NONE))
                durations.append(frame.info.get('duration', 50))
        except Exception as fe:
            print(f"[gif] frame error: {fe}")
            # Fallback: static from first frame
            src.seek(0)
            img = src.convert('RGB')
            img_w, img_h = img.size
            draw = ImageDraw.Draw(img)
            for i, zone in enumerate(zones):
                if i < len(texts) and texts[i].strip():
                    pixel_size = min(_pixel_size_from_params(zone, img_h, preferred), min(img_w, img_h) // 4)
                    draw_text_block(draw, texts[i].upper(), img_w, img_h, zone, color, pixel_size)
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            return jsonify({'image': base64.b64encode(buf.getvalue()).decode()})

        if not frames:
            return jsonify({'error': 'GIF has no frames'}), 500

        out = io.BytesIO()
        frames[0].save(
            out, format='GIF',
            save_all=True,
            append_images=frames[1:],
            loop=src.info.get('loop', 0),
            duration=durations,
            optimize=False,
        )
        return jsonify({'gif': base64.b64encode(out.getvalue()).decode()})

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
