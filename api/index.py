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
    {"label": "Boyfriend",   "x": 0.30, "y": 0.02, "w": 0.38, "h": 0.18, "pos": "center"},
    {"label": "Other girl",  "x": 0.58, "y": 0.50, "w": 0.40, "h": 0.38, "pos": "center"},
    {"label": "Girlfriend",  "x": 0.02, "y": 0.50, "w": 0.40, "h": 0.38, "pos": "center"},
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

_CHANGE_MY_MIND = [
    {"label": "Controversial opinion", "x": 0.30, "y": 0.52, "w": 0.55, "h": 0.32, "pos": "center"},
]

_WOMAN_CAT = [
    {"label": "Yelling woman", "x": 0.0, "y": 0.0, "w": 0.50, "h": 1.0, "pos": "center"},
    {"label": "Smug cat",      "x": 0.5, "y": 0.0, "w": 0.50, "h": 1.0, "pos": "center"},
]

_SPIDERMAN = [
    {"label": "Left",  "x": 0.0, "y": 0.0, "w": 0.50, "h": 1.0, "pos": "center"},
    {"label": "Right", "x": 0.5, "y": 0.0, "w": 0.50, "h": 1.0, "pos": "center"},
]

_BATMAN_SLAP = [
    {"label": "Batman says", "x": 0.02, "y": 0.02, "w": 0.44, "h": 0.40, "pos": "center"},
    {"label": "Robin says",  "x": 0.54, "y": 0.02, "w": 0.44, "h": 0.40, "pos": "center"},
]

_CLASSIC_TOP_BOTTOM = [
    {"label": "Top text",    "x": 0.0, "y": 0.0,  "w": 1.0, "h": 0.20, "pos": "center"},
    {"label": "Bottom text", "x": 0.0, "y": 0.80, "w": 1.0, "h": 0.20, "pos": "center"},
]

_BERNIE = [
    {"label": "I am once again asking", "x": 0.0, "y": 0.62, "w": 1.0, "h": 0.33, "pos": "center"},
]

_THIS_IS_FINE = [
    {"label": "Caption", "x": 0.0, "y": 0.0, "w": 1.0, "h": 0.18, "pos": "center"},
]

_ALWAYS_HAS_BEEN = [
    {"label": "Wait, it's all…", "x": 0.02, "y": 0.28, "w": 0.44, "h": 0.32, "pos": "center"},
    {"label": "Always has been", "x": 0.54, "y": 0.08, "w": 0.44, "h": 0.32, "pos": "center"},
]

_LEFT_EXIT = [
    {"label": "The exit (temptation)", "x": 0.30, "y": 0.04, "w": 0.35, "h": 0.28, "pos": "center"},
    {"label": "Car label",             "x": 0.60, "y": 0.55, "w": 0.38, "h": 0.22, "pos": "center"},
]

_STONKS = [
    {"label": "Top",    "x": 0.0, "y": 0.0,  "w": 1.0, "h": 0.20, "pos": "center"},
    {"label": "Bottom", "x": 0.0, "y": 0.80, "w": 1.0, "h": 0.20, "pos": "center"},
]

_BUFF_DOGE_CHEEMS = [
    {"label": "Buff Doge (strong)",  "x": 0.0,  "y": 0.0, "w": 0.50, "h": 1.0, "pos": "center"},
    {"label": "Cheems (weak)",       "x": 0.50, "y": 0.0, "w": 0.50, "h": 1.0, "pos": "center"},
]

_WHO_WOULD_WIN = [
    {"label": "Side A", "x": 0.0,  "y": 0.0, "w": 0.45, "h": 1.0, "pos": "center"},
    {"label": "Side B", "x": 0.55, "y": 0.0, "w": 0.45, "h": 1.0, "pos": "center"},
]

_TRADE_OFFER = [
    {"label": "I receive",   "x": 0.0,  "y": 0.3,  "w": 0.48, "h": 0.4, "pos": "center"},
    {"label": "You receive", "x": 0.52, "y": 0.3,  "w": 0.48, "h": 0.4, "pos": "center"},
]

_PANIK_KALM = [
    {"label": "Panik (top)",    "x": 0.55, "y": 0.0,  "w": 0.44, "h": 0.33, "pos": "center"},
    {"label": "Kalm (middle)",  "x": 0.55, "y": 0.33, "w": 0.44, "h": 0.33, "pos": "center"},
    {"label": "Panik (bottom)", "x": 0.55, "y": 0.66, "w": 0.44, "h": 0.33, "pos": "center"},
]

_WOMAN_WINDOW = [
    {"label": "Person's label",  "x": 0.0,  "y": 0.55, "w": 0.48, "h": 0.42, "pos": "center"},
    {"label": "Window thing",    "x": 0.52, "y": 0.05, "w": 0.46, "h": 0.42, "pos": "center"},
]

_RUNNING_AWAY_BALLOON = [
    {"label": "Person/label",  "x": 0.0,  "y": 0.50, "w": 0.48, "h": 0.45, "pos": "center"},
    {"label": "Balloon text",  "x": 0.42, "y": 0.04, "w": 0.55, "h": 0.42, "pos": "center"},
]

_BIKE_FALL = [
    {"label": "Stick",       "x": 0.0,  "y": 0.0,  "w": 0.50, "h": 0.50, "pos": "center"},
    {"label": "Pole/wheel",  "x": 0.50, "y": 0.0,  "w": 0.50, "h": 0.50, "pos": "center"},
    {"label": "Result",      "x": 0.10, "y": 0.55, "w": 0.80, "h": 0.40, "pos": "center"},
]

_MONKEY_PUPPET = [
    {"label": "Caption", "x": 0.0, "y": 0.0, "w": 1.0, "h": 0.20, "pos": "center"},
]

_WAIT_THATS_ILLEGAL = [
    {"label": "Normal thing",    "x": 0.0,  "y": 0.0, "w": 0.48, "h": 1.0, "pos": "center"},
    {"label": "Illegal thing",   "x": 0.52, "y": 0.0, "w": 0.48, "h": 1.0, "pos": "center"},
]

_CRYING_JORDAN = [
    {"label": "Caption", "x": 0.0, "y": 0.0, "w": 1.0, "h": 0.20, "pos": "center"},
]

_LEO_CHEERS = [
    {"label": "Toast to…", "x": 0.0, "y": 0.0, "w": 1.0, "h": 0.18, "pos": "center"},
]

# keyword lists → zones
NAME_LAYOUTS = [
    (["drake", "hotline bling"],                        _DRAKE),
    (["two buttons", "two button"],                     _TWO_BUTTONS),
    (["distracted boyfriend", "distracted bf"],         _DISTRACTED_BF),
    (["expanding brain", "galaxy brain", "brain size"], _EXPANDING_BRAIN),
    (["gru's plan", "gru plan", "gru's"],               _GRU_PLAN),
    (["change my mind"],                                _CHANGE_MY_MIND),
    (["woman yelling", "yelling at cat", "woman cat"],  _WOMAN_CAT),
    (["spider-man", "spiderman", "pointing spider"],    _SPIDERMAN),
    (["batman slap", "batman slapping", "slap robin"],  _BATMAN_SLAP),
    (["bernie", "once again asking"],                   _BERNIE),
    (["this is fine"],                                  _THIS_IS_FINE),
    (["always has been"],                               _ALWAYS_HAS_BEEN),
    (["left exit 12", "left exit"],                     _LEFT_EXIT),
    (["stonks"],                                        _STONKS),
    (["buff doge", "cheems"],                           _BUFF_DOGE_CHEEMS),
    (["who would win"],                                 _WHO_WOULD_WIN),
    (["trade offer"],                                   _TRADE_OFFER),
    (["panik", "kalm"],                                 _PANIK_KALM),
    (["woman window", "woman looking out"],             _WOMAN_WINDOW),
    (["running away balloon"],                          _RUNNING_AWAY_BALLOON),
    (["bike fall", "stick figure bike"],                _BIKE_FALL),
    (["monkey puppet", "awkward look monkey"],          _MONKEY_PUPPET),
    (["wait that's illegal", "wait thats illegal"],     _WAIT_THATS_ILLEGAL),
    (["crying jordan", "michael jordan crying"],        _CRYING_JORDAN),
    (["leonardo dicaprio", "leo dicaprio cheers"],      _LEO_CHEERS),
    # classic impact-style memes
    (["one does not simply", "boromir"],                _CLASSIC_TOP_BOTTOM),
    (["roll safe", "think about it"],                   _CLASSIC_TOP_BOTTOM),
    (["hide the pain", "harold"],                       _CLASSIC_TOP_BOTTOM),
    (["mocking spongebob", "spongebob mocking"],        _CLASSIC_TOP_BOTTOM),
    (["pikachu", "surprised pikachu"],                  _CLASSIC_TOP_BOTTOM),
    (["disaster girl"],                                 _CLASSIC_TOP_BOTTOM),
    (["is this a pigeon", "is this"],                   _CLASSIC_TOP_BOTTOM),
    (["grumpy cat", "no grumpy"],                       _CLASSIC_TOP_BOTTOM),
    (["success kid"],                                   _CLASSIC_TOP_BOTTOM),
    (["bad luck brian"],                                _CLASSIC_TOP_BOTTOM),
    (["good guy greg"],                                 _CLASSIC_TOP_BOTTOM),
    (["scumbag steve"],                                 _CLASSIC_TOP_BOTTOM),
    (["ancient aliens"],                                _CLASSIC_TOP_BOTTOM),
    (["futurama fry", "not sure if"],                   _CLASSIC_TOP_BOTTOM),
    (["doge"],                                          _CLASSIC_TOP_BOTTOM),
    (["forever alone"],                                 _CLASSIC_TOP_BOTTOM),
    (["y u no"],                                        _CLASSIC_TOP_BOTTOM),
    (["overly attached girlfriend"],                    _CLASSIC_TOP_BOTTOM),
    (["creepy condescending wonka"],                    _CLASSIC_TOP_BOTTOM),
    (["confession bear"],                               _CLASSIC_TOP_BOTTOM),
    (["first world problems"],                          _CLASSIC_TOP_BOTTOM),
    (["politically incorrect", "unpopular opinion"],    _CLASSIC_TOP_BOTTOM),
    (["matrix morpheus", "what if i told you"],         _CLASSIC_TOP_BOTTOM),
    (["third world skeptical kid", "skeptical kid"],    _CLASSIC_TOP_BOTTOM),
    (["blinking guy", "blinking white guy"],            _CLASSIC_TOP_BOTTOM),
    (["epic handshake"],                                _CLASSIC_TOP_BOTTOM),
    (["two guys on a bench"],                           _CLASSIC_TOP_BOTTOM),
    (["back in my day", "old man"],                     _CLASSIC_TOP_BOTTOM),
    (["laughing men in suits"],                         _CLASSIC_TOP_BOTTOM),
    (["oprah you get"],                                 _CLASSIC_TOP_BOTTOM),
    (["the most interesting man"],                      _CLASSIC_TOP_BOTTOM),
    (["ain't nobody got time"],                         _CLASSIC_TOP_BOTTOM),
    (["i should buy a boat"],                           _CLASSIC_TOP_BOTTOM),
    (["philosoraptor"],                                 _CLASSIC_TOP_BOTTOM),
    (["tuxedo winnie", "tuxedo pooh"],                  _DRAKE),
    (["uno draw", "draw 25"],                           [
        {"label": "Option",  "x": 0.52, "y": 0.04, "w": 0.44, "h": 0.42, "pos": "center"},
        {"label": "Or draw", "x": 0.0,  "y": 0.62, "w": 1.0,  "h": 0.33, "pos": "center"},
    ]),
]

ID_LAYOUTS = {
    "181913649": _DRAKE,
    "87743020":  _TWO_BUTTONS,
    "112126428": _DISTRACTED_BF,
    "93895088":  _EXPANDING_BRAIN,
    "131940431": _GRU_PLAN,
    "129242436": _CHANGE_MY_MIND,
    "188390779": _WOMAN_CAT,
    "101470":    _SPIDERMAN,
    "9440985":   _BATMAN_SLAP,
    "91538330":  _BERNIE,
    "55311130":  _THIS_IS_FINE,
    "252600902": _ALWAYS_HAS_BEEN,
    "124822590": _LEFT_EXIT,
    "89370399":  _CLASSIC_TOP_BOTTOM,
    "27813981":  _CLASSIC_TOP_BOTTOM,
    "102156234": _CLASSIC_TOP_BOTTOM,
    "61579":     _CLASSIC_TOP_BOTTOM,
    "119139145": _CLASSIC_TOP_BOTTOM,
    "161865971": _CLASSIC_TOP_BOTTOM,
    "217743513": _CLASSIC_TOP_BOTTOM,
    "4087833":   _CLASSIC_TOP_BOTTOM,
    "135256802": _CLASSIC_TOP_BOTTOM,
    "322841258": _CLASSIC_TOP_BOTTOM,
    "247375501": _BUFF_DOGE_CHEEMS,
    "301733230": _TRADE_OFFER,
    "226297822": _PANIK_KALM,
    "438680":    _CLASSIC_TOP_BOTTOM,  # Batman Slapping Robin alt
    "370867422": _CLASSIC_TOP_BOTTOM,  # Crying Jordan
    "3218037":   _CLASSIC_TOP_BOTTOM,  # Leo Cheers
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


# ── Structural pixel analysis ─────────────────────────────────────────────────

def detect_zones_from_pixels(img: Image.Image):
    w, h = img.size
    arr  = np.array(img.convert('RGB'), dtype=np.float32)

    BRIGHT = 215
    MIN_COL_FRAC = 0.20
    MIN_ROW_FRAC = 0.15

    col_brightness = arr.mean(axis=(0, 2))
    row_brightness = arr.mean(axis=(1, 2))

    bright_cols = col_brightness > BRIGHT
    bright_rows = row_brightness > BRIGHT

    col_runs = _find_runs(bright_cols, MIN_COL_FRAC, w)
    row_runs = _find_runs(bright_rows, MIN_ROW_FRAC, h)

    zones = []

    if col_runs and not row_runs:
        for x0, x1 in col_runs:
            col_arr   = arr[:, x0:x1, :]
            col_r_bri = col_arr.mean(axis=(1, 2))
            col_b_rows= col_r_bri > BRIGHT
            sub_rows  = _find_runs(col_b_rows, 0.25, h)
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
        top_bri  = float(arr[:int(h*0.18), :, :].mean())
        bot_bri  = float(arr[int(h*0.82):, :, :].mean())
        mid_bri  = float(arr[int(h*0.2):int(h*0.8), :, :].mean())
        has_top  = top_bri > BRIGHT and top_bri > mid_bri + 20
        has_bot  = bot_bri > BRIGHT and bot_bri > mid_bri + 20
        if has_top:
            zones.append({"label":"Top text",    "x":0.0,"y":0.0, "w":1.0,"h":0.18,"pos":"center"})
        if has_bot:
            zones.append({"label":"Bottom text", "x":0.0,"y":0.82,"w":1.0,"h":0.18,"pos":"center"})

    return zones if zones else None


def _zone(px, py, pw, ph, img_w, img_h, label):
    pad = 0.01
    return {
        "label": label,
        "x": max(0.0, px/img_w + pad),
        "y": max(0.0, py/img_h + pad),
        "w": min(1.0, pw/img_w - pad*2),
        "h": min(1.0, ph/img_h - pad*2),
        "pos": "center",
    }


def _find_runs(mask, min_frac, total):
    min_len = max(1, int(min_frac * total))
    runs, in_run, start = [], False, 0
    for i, v in enumerate(mask):
        if v and not in_run:
            in_run, start = True, i
        elif not v and in_run:
            in_run = False
            if i - start >= min_len:
                runs.append((start, i))
    if in_run and total - start >= min_len:
        runs.append((start, total))
    return runs


# ── AI fallback ───────────────────────────────────────────────────────────────

def _call_groq_ai(url):
    if not GROQ_API_KEY:
        return None
    prompt = (
        "Return ONLY a JSON array of meme text zones. "
        "Each: {\"label\":str,\"x\":float,\"y\":float,\"w\":float,\"h\":float,\"pos\":\"center\"}. "
        "x,y=top-left corner (0-1 fraction), w,h=size (0-1 fraction). "
        "Zones must cover where TEXT goes, not the photo. No markdown."
    )
    for model in GROQ_VISION_MODELS:
        try:
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": url}},
                    {"type": "text", "text": prompt},
                ]}], "max_tokens": 400, "temperature": 0.1},
                timeout=15,
            )
            r.raise_for_status()
            raw   = re.sub(r"```(?:json)?|```", "", r.json()["choices"][0]["message"]["content"]).strip()
            zones = json.loads(raw)
            valid = [z for z in zones if all(k in z for k in ("x","y","w","h")) and float(z["w"]) >= 0.25]
            if valid:
                return valid
        except Exception as exc:
            print(f"[zones] AI {model}: {exc}")
    return None


# ── Master zone resolver ───────────────────────────────────────────────────────

def resolve_zones(url: str, name: str, img: Image.Image):
    z = match_layout_by_url(url)
    if z:
        print(f"[zones] ID match for '{name}'")
        return z

    z = match_layout_by_name(name)
    if z:
        print(f"[zones] Name match for '{name}'")
        return z

    z = detect_zones_from_pixels(img)
    if z:
        print(f"[zones] Pixel analysis: {len(z)} zones for '{name}'")
        return z

    z = _call_groq_ai(url)
    if z:
        print(f"[zones] AI zones for '{name}'")
        return z

    print(f"[zones] DEFAULT_ZONES for '{name}'")
    return DEFAULT_ZONES


# ── Rendering Engine ───────────────────────────────────────────────────────────

def get_font(size):
    size = max(10, int(size))
    try:
        if os.path.exists(FONT_PATH):
            return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def get_font_size(font):
    return font.size if hasattr(font, 'size') else 12


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines, cur = [], []
    for word in words:
        candidate = ' '.join(cur + [word])
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            cur.append(word)
        else:
            if cur: lines.append(' '.join(cur))
            cur = [word]
    if cur: lines.append(' '.join(cur))
    return lines or ['']


def draw_text_block(draw, text, img_w, img_h, zone, color, preferred_size):
    """
    Render `text` inside the fractional zone rectangle.
    Font is auto-scaled: start at `preferred_size`, shrink until it fits.
    `preferred_size` is already in pixels (relative to the actual image size).
    """
    zx = int(zone.get('x', 0.0) * img_w)
    zy = int(zone.get('y', 0.0) * img_h)
    zw = int(zone.get('w', 1.0) * img_w)
    zh = int(zone.get('h', 1.0) * img_h)
    if zw < 10 or zh < 10:
        return

    pad     = max(4, int(min(zw, zh) * 0.05))
    avail_w = max(1, zw - pad * 2)
    avail_h = max(1, zh - pad * 2)

    # ── Auto-fit: start at preferred size, step down until text fits ──────────
    # Cap the starting size: no bigger than 45 % of zone height (single line)
    max_start = max(10, int(zh * 0.45))
    cur_size  = min(int(preferred_size), max_start)
    final_lines = final_font = None

    while cur_size >= 10:
        font  = get_font(cur_size)
        lines = wrap_text(draw, text, font, avail_w)
        bbox  = draw.textbbox((0, 0), 'Ay', font=font)
        lh    = (bbox[3] - bbox[1]) + max(1, int(cur_size * 0.15))
        if lh * len(lines) <= avail_h:
            final_lines, final_font = lines, font
            break
        cur_size -= 2

    # Absolute fallback
    if final_font is None:
        final_font  = get_font(10)
        final_lines = wrap_text(draw, text, final_font, avail_w)

    # ── Compute layout ────────────────────────────────────────────────────────
    bbox   = draw.textbbox((0, 0), 'Ay', font=final_font)
    fsize  = get_font_size(final_font)
    lh     = (bbox[3] - bbox[1]) + max(1, int(fsize * 0.15))
    total_h = lh * len(final_lines)

    pos = zone.get('pos', 'center')
    if pos == 'top':
        start_y = zy + pad
    elif pos == 'bottom':
        start_y = zy + zh - total_h - pad
    else:
        start_y = zy + (zh - total_h) // 2

    # ── Draw with stroke ──────────────────────────────────────────────────────
    stroke_w = max(1, int(fsize * 0.07))
    curr_y   = start_y

    for line in final_lines:
        lb = draw.textbbox((0, 0), line, font=final_font)
        lw = lb[2] - lb[0]
        cx = zx + (zw - lw) // 2   # center horizontally within zone

        # Black outline
        for ox in range(-stroke_w, stroke_w + 1):
            for oy in range(-stroke_w, stroke_w + 1):
                if ox == 0 and oy == 0:
                    continue
                draw.text((cx + ox, curr_y + oy), line, font=final_font, fill=(0, 0, 0))

        # Main text
        draw.text((cx, curr_y), line, font=final_font, fill=color)
        curr_y += lh


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


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
        img_data = requests.get(url, timeout=10).content
        img      = Image.open(io.BytesIO(img_data)).convert('RGB')
    except Exception as e:
        print(f"[zones] Download failed: {e}")
        return jsonify({'zones': DEFAULT_ZONES, 'fallback': True})

    zones = resolve_zones(url, meme_name, img)
    _zone_cache[url] = {'zones': zones, 'img': img}
    return jsonify({'zones': zones, 'fallback': False})


@app.route('/generate', methods=['POST'])
def generate():
    try:
        data      = request.json or {}
        image_url = data.get('image_url', '').strip()
        texts     = data.get('texts', [])
        # Zones can be overridden from the frontend (they were already resolved there)
        client_zones = data.get('zones', None)
        preferred    = max(10, int(data.get('font_size', 40)))
        c_hex        = data.get('text_color', '#FFFFFF').lstrip('#').zfill(6)
        color        = tuple(int(c_hex[i:i+2], 16) for i in (0, 2, 4))

        # Load image ─────────────────────────────────────────────────────────
        cached = _zone_cache.get(image_url, {})
        if isinstance(cached, dict) and 'img' in cached:
            img   = cached['img'].copy()
            zones = cached['zones']
        else:
            raw  = requests.get(image_url, timeout=10).content
            img  = Image.open(io.BytesIO(raw)).convert('RGB')
            zones = cached.get('zones', DEFAULT_ZONES) if isinstance(cached, dict) else DEFAULT_ZONES

        # If the client sent zones (already resolved), prefer those
        if client_zones and isinstance(client_zones, list) and len(client_zones) > 0:
            zones = client_zones

        img_w, img_h = img.size
        draw = ImageDraw.Draw(img)

        for i, zone in enumerate(zones):
            if i < len(texts) and texts[i].strip():
                # Scale font relative to the actual image size.
                # `preferred` is the slider value (14–80), treated as a % of
                # the shorter image dimension.  This keeps text proportional on
                # both tiny (500 px) and large (1200 px) images.
                short_side    = min(img_w, img_h)
                zone_h_px     = max(1, zone.get('h', 0.2) * img_h)
                # Base size: slider maps 14→3 % and 80→18 % of zone height
                pct           = (preferred - 14) / (80 - 14)   # 0.0 – 1.0
                size_frac     = 0.30 + pct * 0.55              # 0.30 – 0.85 of zone height
                pixel_size    = int(zone_h_px * size_frac)
                # Hard limits: don't go below 14 px or above 1/4 of image short side
                pixel_size    = max(14, min(pixel_size, short_side // 4))

                draw_text_block(
                    draw, texts[i].upper(),
                    img_w, img_h, zone, color, pixel_size
                )

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return jsonify({'image': base64.b64encode(buf.getvalue()).decode()})

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
