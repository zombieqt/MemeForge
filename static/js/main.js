(() => {
  // ── State ──────────────────────────────────────────────────────────────────
  let allMemes       = [];
  let filteredMemes  = [];
  let displayedCount = 0;
  const PAGE_SIZE    = 24;

  let selectedMeme   = null;
  let selectedUrl    = null;
  let selectedName   = '';
  let currentZones   = [];   // [{label, x, y, w, h, pos, _id}]  0-1 fractions
  let zoneDetecting  = false;

  let activeGenre    = 'all';
  let searchQuery    = '';

  // ── Zone editor state ──────────────────────────────────────────────────────
  let editorImg      = null;
  let editorCanvas   = null;
  let editorCtx      = null;
  let activeZoneIdx  = -1;
  let dragState      = null;  // {type:'move'|'resize', zoneIdx, startX, startY, origZone}
  let zoneCounter    = 0;

  const ZONE_COLORS = ['#ff6b35','#4ade80','#60a5fa','#f59e0b','#e879f9','#fb7185',
                       '#34d399','#f472b6','#a78bfa','#38bdf8'];
  const HANDLE_SIZE = 9;  // px half-size of resize handle

  // ── Genre keywords ─────────────────────────────────────────────────────────
  const GENRE_KEYWORDS = {
    reaction: ['distracted','surprised pikachu','pikachu','shocked','wait','what','seriously','oof','cringe','spongebob','mocking','hide the pain','hide pain','crying','laughing','nobody','society','tuxedo','mask','blinking','this is fine','fine','disaster','rollsafe','roll safe','think about it','facepalm','confused','ight imma','hold up','bruh','wait what','no no no','that would be great','office','michael scott','not sure if','futurama','toby','dwight','kevin','jim','pam','the office','say the line','surprised','shocked pikachu','guy','when','me','i can has','reaction','relatable','every time','always','somehow','literally','it\'s always','every single time','none of my business','kermit','tea'],
    drake: ['drake','hotline bling','two buttons','exit 12','left exit','uno draw','draw 25','or draw','gru','plan','choose','option','prefer','tuxedo pooh','tuxedo winnie','switch','vs','versus','better','instead','rather','over','not this','yes this','no yes','choice','options','picking','drake format'],
    brain: ['brain','expanding brain','galaxy brain','big brain','thinking','iq','smart','galaxy','universe brain','mind','intelligent','sigma','chad','vs virgin','based','gigachad','alphachad','sigma grindset','0 iq','200 iq','300 iq','1000 iq','smoothbrain','wrinkled brain','no thoughts','big think'],
    change: ['change my mind','unpopular opinion','controversial','opinion','debate','fight me','crowder','change my','my mind','hot take','actually','fight me on this','prove me wrong','i said what i said'],
    animals: ['dog','cat','doge','grumpy cat','grumpy','animal','bird','frog','bear','wolf','lion','fish','shark','monkey','gorilla','penguin','baby yoda','grogu','doggo','puppy','kitten','much wow','such','wow','shiba','akita','corgi','labrador','golden','retriever','pug','husky','bunny','rabbit','hamster','guinea pig','parrot','owl','fox','deer','horse','cow','pig','goat','duck','chicken','turtle','snail','spider','bug','insect','bee','butterfly','platypus','seal','otter','panda','koala','sloth','alpaca','llama','capybara','axolotl','vibing cat','dancing','business cat','ceiling cat','longcat','nyan cat'],
    classic: ['one does not simply','boromir','forever alone','bad luck brian','success kid','first world problems','scumbag steve','insanity wolf','10 guy','philosoraptor','good guy greg','overly attached girlfriend','creepy condescending wonka','confession bear','third world skeptical kid','skeptical kid','ancient aliens','y u no','oprah','most interesting man','ain\'t nobody','i should buy a boat','back in my day','laughing men','epic handshake','two guys bench','le me','forever','awkward','socially awkward','actual advice mallard','courage wolf','ermahgerd','all the things','redditor','advice','throwback','vintage meme','classic meme','old school'],
    wholesome: ['wholesome','heartwarming','happy','love','cute','dad','mom','family','friend','kids','children','good','kind','care','hug','together','support','proud','blessing','gratitude','thankful','warm','sweet','adorable','heartfelt','touching','inspirational','feel good','uplifting','positive','smile','laugh','joy','comfort','cozy','golden retriever','puppy eyes','baby','toddler','grandmother','grandpa','grandma','wholesome 100'],
    political: ['political','trump','biden','president','government','congress','senator','politician','vote','election','democrat','republican','liberal','conservative','america','policy','law','bill','legislation','tax','border','immigration','left','right','center','progressive','moderate','extreme','party','white house','capitol','supreme court','irs','fbi','cia','nsa','fda','elon','musk','putin','zelensky','boris','nato','un','eu','climate','green new','inflation','economy','budget','debt','deficit','stimulus','relief'],
    gaming: ['game','gaming','mario','minecraft','fortnite','among us','player','gamer','level','boss','noob','pro','xbox','playstation','pc','steam','nintendo','league of legends','lol','dota','valorant','overwatch','apex','warzone','cod','call of duty','halo','zelda','pokemon','final fantasy','dark souls','elden ring','skyrim','fallout','gta','grand theft auto','roblox','fnaf','terraria','stardew','animal crossing','smash','melee','speedrun','glitch','fps','rpg','mmo','pvp','pve','esports','twitch','streamer','gg','ez','git gud','skill issue','tryhard','sweaty','toxic'],
    sports: ['sport','football','soccer','basketball','baseball','tennis','nba','nfl','mlb','team','player','coach','win','loss','champion','goat','mvp','brady','lebron','messi','ronaldo','jordan','curry','mahomes','manning','kobe','shaq','magic','bird','wrestling','boxing','mma','ufc','golf','hockey','nhl','formula 1','f1','nascar','swimming','olympics','world cup','super bowl','finals','playoffs','touchdown','home run','slam dunk','hat trick','penalty','red card','referee','umpire','draft','trade'],
    money: ['stonks','money','rich','poor','broke','cash','bank','invest','stock','crypto','bitcoin','ethereum','dogecoin','nft','economy','salary','afford','price','expensive','cheap','free','discount','sale','deal','coupon','budget','savings','debt','credit','loan','mortgage','rent','housing','inflation','recession','market','wall street','ape','wsb','robinhood','gamestop','amc','yolo','tendies','to the moon','diamond hands','paper hands','tax','irs','write off','expense','revenue','profit','loss','bankruptcy'],
  };

  // ── Supplemental memes ─────────────────────────────────────────────────────
  const SUPPLEMENTAL_MEMES = [
    { id:'s-1',  name:'Surprised Pikachu',               url:'https://i.imgflip.com/2kbn1e.jpg',  width:1893,height:1893,boxes:1,genre:'reaction' },
    { id:'s-2',  name:'Bernie I Am Once Again Asking',   url:'https://i.imgflip.com/3lmzyx.jpg',  width:960, height:720, boxes:1,genre:'classic'  },
    { id:'s-3',  name:'Buff Doge vs. Cheems',            url:'https://i.imgflip.com/43a45p.png',  width:937, height:431, boxes:4,genre:'animals'  },
    { id:'s-4',  name:'Who Would Win',                   url:'https://i.imgflip.com/1g8my4.jpg',  width:800, height:478, boxes:2,genre:'reaction' },
    { id:'s-5',  name:'This Is Fine Dog',                url:'https://i.imgflip.com/wxica.jpg',   width:1106,height:552, boxes:2,genre:'reaction' },
    { id:'s-6',  name:"Gru's Plan (4 Panels)",           url:'https://i.imgflip.com/26jxvz.jpg',  width:1440,height:1433,boxes:4,genre:'drake'    },
    { id:'s-7',  name:'Always Has Been Astronaut',       url:'https://i.imgflip.com/46e43q.png',  width:1104,height:621, boxes:2,genre:'reaction' },
    { id:'s-8',  name:'Left Exit 12 Off Ramp',           url:'https://i.imgflip.com/22bdq6.jpg',  width:804, height:767, boxes:2,genre:'drake'    },
    { id:'s-9',  name:'Am I The Only One Around Here',   url:'https://i.imgflip.com/1bh8.jpg',    width:500, height:375, boxes:1,genre:'reaction' },
    { id:'s-10', name:'Futurama Fry / Not Sure If',      url:'https://i.imgflip.com/6ys.jpg',     width:400, height:300, boxes:2,genre:'classic'  },
    { id:'s-11', name:'Ancient Aliens Guy',              url:'https://i.imgflip.com/xgq9k.jpg',   width:720, height:480, boxes:2,genre:'classic'  },
    { id:'s-12', name:'Third World Skeptical Kid',       url:'https://i.imgflip.com/4t0m5.jpg',   width:500, height:375, boxes:2,genre:'classic'  },
    { id:'s-13', name:'Oprah You Get A Car',             url:'https://i.imgflip.com/1bhf.jpg',    width:500, height:375, boxes:2,genre:'classic'  },
    { id:'s-14', name:'Philosoraptor',                   url:'https://i.imgflip.com/rq5n.jpg',    width:500, height:500, boxes:2,genre:'classic'  },
    { id:'s-15', name:'Confession Bear',                 url:'https://i.imgflip.com/1bgw.jpg',    width:500, height:375, boxes:2,genre:'classic'  },
    { id:'s-16', name:'Matrix Morpheus / What If I Told You', url:'https://i.imgflip.com/2fm6x.jpg', width:625,height:350,boxes:2,genre:'classic'},
    { id:'s-18', name:'Disaster Girl',                   url:'https://i.imgflip.com/23ls.jpg',    width:500, height:375, boxes:2,genre:'classic'  },
    { id:'s-20', name:'Patrick Star Not My Problem',     url:'https://i.imgflip.com/1bf2j.jpg',   width:500, height:375, boxes:2,genre:'reaction' },
    { id:'s-24', name:'Crying MJ Michael Jordan',        url:'https://i.imgflip.com/9vct.jpg',    width:500, height:492, boxes:2,genre:'sports'   },
    { id:'s-25', name:'Leo DiCaprio Cheers',             url:'https://i.imgflip.com/3m1ykh.png',  width:491, height:335, boxes:1,genre:'reaction' },
    { id:'s-26', name:'Success Kid Fist Pump',           url:'https://i.imgflip.com/1bhk.jpg',    width:500, height:500, boxes:2,genre:'classic'  },
    { id:'s-27', name:'First World Problems',            url:'https://i.imgflip.com/1bgs.jpg',    width:500, height:500, boxes:2,genre:'classic'  },
    { id:'s-28', name:'Good Guy Greg',                   url:'https://i.imgflip.com/6cy.jpg',     width:500, height:500, boxes:2,genre:'classic'  },
    { id:'s-29', name:'Scumbag Steve',                   url:'https://i.imgflip.com/1biz.jpg',    width:500, height:500, boxes:2,genre:'classic'  },
    { id:'s-30', name:'Business Cat',                    url:'https://i.imgflip.com/6bz.jpg',     width:500, height:500, boxes:2,genre:'animals'  },
    { id:'s-31', name:'Actual Advice Mallard Duck',      url:'https://i.imgflip.com/1biw.jpg',    width:500, height:500, boxes:2,genre:'animals'  },
    { id:'s-32', name:'Bad Luck Brian',                  url:'https://i.imgflip.com/1bip.jpg',    width:500, height:500, boxes:2,genre:'classic'  },
    { id:'s-33', name:'Forever Alone',                   url:'https://i.imgflip.com/1bhg.jpg',    width:500, height:500, boxes:2,genre:'classic'  },
    { id:'s-34', name:'Y U No Guy',                      url:'https://i.imgflip.com/1bhs.jpg',    width:500, height:500, boxes:2,genre:'classic'  },
    { id:'s-35', name:'Courage Wolf',                    url:'https://i.imgflip.com/1bgv.jpg',    width:500, height:500, boxes:2,genre:'animals'  },
  ];

  // ── Init ───────────────────────────────────────────────────────────────────
  async function init() {
    updateFontSizeLabel();
    buildEditorCanvas();
    bindEvents();
    await fetchMemes();
  }

  // ── Fetch memes ────────────────────────────────────────────────────────────
  async function fetchMemes() {
    setGridLoading(true);
    try {
      const res  = await fetch('https://api.imgflip.com/get_memes');
      const data = await res.json();
      if (data.success) {
        const apiMemes = data.data.memes.map(m => ({
          id:m.id,name:m.name,url:m.url,
          width:m.width,height:m.height,
          boxes:m.box_count,genre:detectGenre(m.name),
        }));
        const nameSet = new Set(apiMemes.map(m=>m.name.toLowerCase()));
        const extras  = SUPPLEMENTAL_MEMES.filter(m=>!nameSet.has(m.name.toLowerCase()));
        allMemes = [...apiMemes,...extras];
        document.getElementById('template-count').textContent=`${allMemes.length} templates`;
      }
    } catch {
      allMemes = SUPPLEMENTAL_MEMES;
      document.getElementById('template-count').textContent=`${allMemes.length} templates (offline)`;
    } finally {
      setGridLoading(false);
      applyFilters();
    }
  }

  function detectGenre(name) {
    const lower = name.toLowerCase();
    for (const [g,kws] of Object.entries(GENRE_KEYWORDS))
      if (kws.some(k=>lower.includes(k))) return g;
    const words = lower.split(/\W+/);
    for (const [g,kws] of Object.entries(GENRE_KEYWORDS))
      if (kws.some(k=>words.includes(k))) return g;
    return 'classic';
  }

  // ── Filtering ──────────────────────────────────────────────────────────────
  function applyFilters() {
    const q = searchQuery.trim().toLowerCase();
    filteredMemes = allMemes.filter(m=>{
      const mg = activeGenre==='all'||m.genre===activeGenre;
      const ms = !q||m.name.toLowerCase().includes(q);
      return mg&&ms;
    });
    displayedCount = 0;
    document.getElementById('template-grid').innerHTML='';
    document.getElementById('grid-empty').style.display=filteredMemes.length===0?'flex':'none';
    loadMoreMemes();
  }

  function loadMoreMemes() {
    const grid  = document.getElementById('template-grid');
    const slice = filteredMemes.slice(displayedCount,displayedCount+PAGE_SIZE);
    slice.forEach(m=>grid.appendChild(createCard(m)));
    displayedCount += slice.length;
    document.getElementById('load-more-wrap').style.display =
      displayedCount<filteredMemes.length?'flex':'none';
  }

  // ── Card creation ──────────────────────────────────────────────────────────
  function createCard(meme) {
    const card = document.createElement('div');
    card.className = 'template-card';
    const img = document.createElement('img');
    img.src=meme.url; img.alt=meme.name; img.loading='lazy';
    const lbl = document.createElement('span');
    lbl.className='template-label'; lbl.textContent=meme.name;
    const bb = document.createElement('span');
    bb.className='box-badge'; bb.textContent=`${meme.boxes} zone${meme.boxes!==1?'s':''}`;
    const gb = document.createElement('span');
    gb.className='genre-badge'; gb.textContent=meme.genre;
    card.append(img,lbl,bb,gb);
    card.addEventListener('click',()=>selectTemplate(meme,card));
    return card;
  }

  // ── Template selection ─────────────────────────────────────────────────────
  async function selectTemplate(meme,cardEl) {
    if (zoneDetecting) return;
    selectedMeme=meme; selectedUrl=meme.url; selectedName=meme.name;
    document.querySelectorAll('.template-card').forEach(c=>c.classList.remove('selected'));
    if (cardEl) cardEl.classList.add('selected');
    document.getElementById('editor-section').scrollIntoView({behavior:'smooth',block:'start'});
    clearError();
    await loadZones(meme.url);
  }

  // ── Zone detection ─────────────────────────────────────────────────────────
  async function loadZones(url) {
    zoneDetecting = true;
    setZoneLoading(true);
    activeZoneIdx = -1;
    try {
      const res  = await fetch('/zones',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({image_url:url,meme_name:selectedName}),
      });
      const data = await res.json();
      currentZones = (data.zones||[]).map((z,i)=>({...z,_id:++zoneCounter}));
      renderAll(!!data.fallback);
    } catch {
      currentZones = [
        {label:'Top text',   x:0.0,y:0.0, w:1.0,h:0.25,pos:'top',   _id:++zoneCounter},
        {label:'Bottom text',x:0.0,y:0.75,w:1.0,h:0.25,pos:'bottom',_id:++zoneCounter},
      ];
      renderAll(true);
    } finally {
      zoneDetecting=false; setZoneLoading(false);
    }
  }

  function setZoneLoading(on) {
    const tf = document.getElementById('text-fields');
    const badge = document.getElementById('zone-count');
    if (on) {
      tf.innerHTML=`<div class="zone-detecting"><div class="zone-spin-ring"></div><span>Analyzing meme layout…</span></div>`;
      badge.textContent='';
      document.getElementById('generate-btn').disabled=true;
    } else {
      document.getElementById('generate-btn').disabled=false;
    }
  }

  // ── Render all UI after zone changes ──────────────────────────────────────
  function renderAll(isFallback=false) {
    renderTextInputs(isFallback);
    loadEditorImage(selectedUrl);
  }

  // ── Text input sidebar ─────────────────────────────────────────────────────
  function renderTextInputs(isFallback=false) {
    const container = document.getElementById('text-fields');
    const badge     = document.getElementById('zone-count');
    container.innerHTML='';

    if (!currentZones.length) {
      container.innerHTML='<p class="pick-hint">← Pick a template above</p>';
      badge.textContent=''; return;
    }

    currentZones.forEach((zone,i)=>{
      const group = document.createElement('div');
      group.className='field-group zone-field-group';
      group.dataset.idx=i;

      // ── zone header row ──────────────────────────────────────────────────
      const labelRow = document.createElement('div');
      labelRow.className='zone-label-row';

      const dot = document.createElement('button');
      dot.className='zone-dot';
      dot.style.background=ZONE_COLORS[i%ZONE_COLORS.length];
      dot.title='Focus zone on canvas';
      dot.addEventListener('click',()=>{ activeZoneIdx=i; redrawCanvas(); });

      const nameInp = document.createElement('input');
      nameInp.type='text'; nameInp.className='zone-name-input';
      nameInp.value=zone.label; nameInp.title='Zone name (editable)';
      nameInp.addEventListener('input',()=>{
        currentZones[i].label=nameInp.value||`Zone ${i+1}`;
        redrawCanvas();
      });

      const delBtn = document.createElement('button');
      delBtn.className='zone-delete-btn'; delBtn.innerHTML='✕';
      delBtn.title='Delete this zone';
      delBtn.addEventListener('click',()=>deleteZone(i));

      labelRow.append(dot,nameInp,delBtn);

      // ── text input ───────────────────────────────────────────────────────
      const inp = document.createElement('input');
      inp.type='text'; inp.id=`zone-${i}`; inp.placeholder=`${zone.label}…`;
      inp.addEventListener('focus',()=>{ activeZoneIdx=i; redrawCanvas(); });
      inp.addEventListener('input',()=>redrawCanvas());

      group.append(labelRow,inp);
      container.appendChild(group);
    });

    // Add zone row
    const addRow = document.createElement('div');
    addRow.className='add-zone-row';
    const addBtn = document.createElement('button');
    addBtn.className='btn-add-zone'; addBtn.innerHTML='＋ Add text zone';
    addBtn.addEventListener('click',addZone);
    addRow.appendChild(addBtn);
    container.appendChild(addRow);

    const n=currentZones.length;
    badge.textContent=`${n} zone${n!==1?'s':''} ${isFallback?'(fallback)':'✓'}`;
    badge.className='zone-badge'+(isFallback?' zone-badge--fallback':'');
  }

  function deleteZone(idx) {
    currentZones.splice(idx,1);
    if (activeZoneIdx>=currentZones.length) activeZoneIdx=currentZones.length-1;
    renderTextInputs();
    redrawCanvas();
  }

  function addZone() {
    currentZones.push({
      label:`Text ${currentZones.length+1}`,
      x:0.1,y:0.1,w:0.80,h:0.18,
      pos:'center',_id:++zoneCounter,
    });
    activeZoneIdx=currentZones.length-1;
    renderTextInputs();
    redrawCanvas();
    const ni=document.getElementById(`zone-${currentZones.length-1}`);
    if (ni) ni.focus();
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // ── Canvas Editor ────────────────────────────────────────────────────────────
  // ─────────────────────────────────────────────────────────────────────────────

  function buildEditorCanvas() {
    editorCanvas = document.getElementById('zone-editor-canvas');
    editorCtx    = editorCanvas.getContext('2d');

    // Mouse
    editorCanvas.addEventListener('mousedown', onDown);
    editorCanvas.addEventListener('mousemove', onMove);
    editorCanvas.addEventListener('mouseup',   onUp);
    editorCanvas.addEventListener('mouseleave',onUp);

    // Touch
    editorCanvas.addEventListener('touchstart', e=>{ e.preventDefault(); onDown(t2m(e)); },{passive:false});
    editorCanvas.addEventListener('touchmove',  e=>{ e.preventDefault(); onMove(t2m(e)); },{passive:false});
    editorCanvas.addEventListener('touchend',   e=>{ onUp(e); },{passive:false});
  }

  function t2m(e) {
    const t=e.touches[0]||e.changedTouches[0];
    return {clientX:t.clientX,clientY:t.clientY};
  }

  function loadEditorImage(url) {
    if (!url) return;
    const wrap = document.getElementById('canvas-editor-wrap');
    wrap.style.display='block';
    document.getElementById('editor-hint').style.display='flex';

    const tryLoad=(crossOrigin)=>{
      editorImg=new Image();
      if (crossOrigin) editorImg.crossOrigin='anonymous';
      editorImg.onload=()=>{ resizeCanvas(); redrawCanvas(); };
      editorImg.onerror=crossOrigin?()=>tryLoad(false):null;
      editorImg.src=url;
    };
    tryLoad(true);
  }

  function resizeCanvas() {
    if (!editorImg) return;
    const wrap   = document.getElementById('canvas-editor-wrap');
    const maxW   = wrap.clientWidth;
    const aspect = editorImg.naturalWidth/editorImg.naturalHeight;
    const dispW  = Math.min(maxW,editorImg.naturalWidth,900);
    const dispH  = Math.round(dispW/aspect);
    editorCanvas.width=dispW; editorCanvas.height=dispH;
    editorCanvas.style.width=dispW+'px'; editorCanvas.style.height=dispH+'px';
  }

  function redrawCanvas() {
    if (!editorImg||!editorCtx) return;
    const cw=editorCanvas.width, ch=editorCanvas.height;
    editorCtx.clearRect(0,0,cw,ch);
    editorCtx.drawImage(editorImg,0,0,cw,ch);

    currentZones.forEach((zone,i)=>{
      const px=zone.x*cw, py=zone.y*ch, pw=zone.w*cw, ph=zone.h*ch;
      const col=ZONE_COLORS[i%ZONE_COLORS.length];
      const isAct=i===activeZoneIdx;

      // Semi-transparent fill
      editorCtx.fillStyle=col+(isAct?'2e':'18');
      editorCtx.fillRect(px,py,pw,ph);

      // Border
      editorCtx.strokeStyle=col;
      editorCtx.lineWidth=isAct?2.5:1.5;
      editorCtx.setLineDash(isAct?[]:[5,4]);
      editorCtx.strokeRect(px+0.5,py+0.5,pw-1,ph-1);
      editorCtx.setLineDash([]);

      // Number badge circle
      const br=Math.max(8,Math.min(13,Math.min(pw,ph)*0.22));
      const bx=px+br+5, by=py+br+5;
      editorCtx.fillStyle=col;
      editorCtx.beginPath();
      editorCtx.arc(bx,by,br,0,Math.PI*2);
      editorCtx.fill();
      editorCtx.fillStyle='#fff';
      editorCtx.font=`bold ${Math.max(8,br*1.05)}px Barlow Condensed,sans-serif`;
      editorCtx.textAlign='center'; editorCtx.textBaseline='middle';
      editorCtx.fillText(i+1,bx,by+0.5);

      // Live text preview inside zone
      const textEl=document.getElementById(`zone-${i}`);
      const tv=textEl?textEl.value.trim():'';
      if (tv) {
        const fs=Math.max(10,Math.min(ph*0.28,pw*0.10,20));
        editorCtx.font=`900 ${fs}px Impact,Arial Black,sans-serif`;
        editorCtx.textAlign='center'; editorCtx.textBaseline='middle';
        const cx2=px+pw/2, cy2=py+ph/2;
        editorCtx.fillStyle='#000';
        editorCtx.fillText(tv.toUpperCase(),cx2+1,cy2+1,pw-10);
        editorCtx.fillStyle='#fff';
        editorCtx.fillText(tv.toUpperCase(),cx2,cy2,pw-10);
      }

      // Resize handle — always visible on active, faint on hover-target
      if (isAct) {
        const rx=px+pw, ry=py+ph;
        const hs=HANDLE_SIZE;
        editorCtx.fillStyle='#fff';
        editorCtx.strokeStyle=col;
        editorCtx.lineWidth=2;
        editorCtx.beginPath();
        editorCtx.roundRect(rx-hs-2,ry-hs-2,hs*2+4,hs*2+4,3);
        editorCtx.fill(); editorCtx.stroke();
        editorCtx.fillStyle=col;
        editorCtx.font=`bold 11px sans-serif`;
        editorCtx.textAlign='center'; editorCtx.textBaseline='middle';
        editorCtx.fillText('⤡',rx,ry);

        // Drag handle indicator top-left
        editorCtx.strokeStyle=col+'88';
        editorCtx.lineWidth=1;
        editorCtx.setLineDash([2,3]);
        editorCtx.strokeRect(px+4,py+4,Math.min(pw-8,26),Math.min(ph-8,26));
        editorCtx.setLineDash([]);
      }
    });
  }

  // ── Canvas hit-test helpers ────────────────────────────────────────────────
  function cpos(e) {
    const r=editorCanvas.getBoundingClientRect();
    const sx=editorCanvas.width/r.width, sy=editorCanvas.height/r.height;
    return {x:(e.clientX-r.left)*sx, y:(e.clientY-r.top)*sy};
  }

  function isOnHandle(mx,my,zone) {
    const cw=editorCanvas.width, ch=editorCanvas.height;
    const rx=(zone.x+zone.w)*cw, ry=(zone.y+zone.h)*ch;
    return Math.abs(mx-rx)<=HANDLE_SIZE+4 && Math.abs(my-ry)<=HANDLE_SIZE+4;
  }

  function isInZone(mx,my,zone) {
    const cw=editorCanvas.width, ch=editorCanvas.height;
    return mx>=zone.x*cw && mx<=(zone.x+zone.w)*cw &&
           my>=zone.y*ch && my<=(zone.y+zone.h)*ch;
  }

  // ── Canvas event handlers ──────────────────────────────────────────────────
  function onDown(e) {
    if (!currentZones.length) return;
    const {x:mx,y:my}=cpos(e);
    const cw=editorCanvas.width, ch=editorCanvas.height;

    // Check resize handle of active zone first
    if (activeZoneIdx>=0 && activeZoneIdx<currentZones.length) {
      const z=currentZones[activeZoneIdx];
      if (isOnHandle(mx,my,z)) {
        dragState={type:'resize',zoneIdx:activeZoneIdx,
          startX:mx,startY:my,origZone:{...z}};
        editorCanvas.style.cursor='nwse-resize';
        return;
      }
    }
    // Hit-test zones top-to-bottom (last = top-most)
    for (let i=currentZones.length-1;i>=0;i--) {
      if (isInZone(mx,my,currentZones[i])) {
        activeZoneIdx=i;
        dragState={type:'move',zoneIdx:i,
          startX:mx,startY:my,origZone:{...currentZones[i]}};
        editorCanvas.style.cursor='grabbing';
        const inp=document.getElementById(`zone-${i}`);
        if (inp) inp.focus();
        redrawCanvas();
        return;
      }
    }
    activeZoneIdx=-1; redrawCanvas();
  }

  function onMove(e) {
    const {x:mx,y:my}=cpos(e);
    const cw=editorCanvas.width, ch=editorCanvas.height;

    if (!dragState) {
      // Cursor hint
      if (activeZoneIdx>=0 && activeZoneIdx<currentZones.length) {
        const z=currentZones[activeZoneIdx];
        if (isOnHandle(mx,my,z)) { editorCanvas.style.cursor='nwse-resize'; return; }
        if (isInZone(mx,my,z))   { editorCanvas.style.cursor='grab'; return; }
      }
      for (let i=currentZones.length-1;i>=0;i--)
        if (isInZone(mx,my,currentZones[i])) { editorCanvas.style.cursor='grab'; return; }
      editorCanvas.style.cursor='crosshair';
      return;
    }

    const dx=(mx-dragState.startX)/cw;
    const dy=(my-dragState.startY)/ch;
    const orig=dragState.origZone;
    const z=currentZones[dragState.zoneIdx];

    if (dragState.type==='move') {
      z.x=Math.max(0,Math.min(1-orig.w, orig.x+dx));
      z.y=Math.max(0,Math.min(1-orig.h, orig.y+dy));
    } else {
      z.w=Math.max(0.05,Math.min(1-orig.x, orig.w+dx));
      z.h=Math.max(0.04,Math.min(1-orig.y, orig.h+dy));
    }
    redrawCanvas();
  }

  function onUp() {
    if (dragState) { dragState=null; editorCanvas.style.cursor='default'; }
  }

  // ── Events ────────────────────────────────────────────────────────────────
  function bindEvents() {
    const si=document.getElementById('search-input');
    const sc=document.getElementById('search-clear');
    si.addEventListener('input',()=>{
      searchQuery=si.value; sc.style.display=searchQuery?'flex':'none'; applyFilters();
    });
    sc.addEventListener('click',()=>{
      si.value=''; searchQuery=''; sc.style.display='none'; applyFilters();
    });

    document.getElementById('genre-pills').addEventListener('click',e=>{
      const p=e.target.closest('.pill'); if(!p) return;
      document.querySelectorAll('.pill').forEach(x=>x.classList.remove('active'));
      p.classList.add('active'); activeGenre=p.dataset.genre; applyFilters();
    });

    document.getElementById('load-more-btn').addEventListener('click',loadMoreMemes);

    const ci=document.getElementById('custom-url');
    let dbt;
    ci.addEventListener('input',()=>{
      clearTimeout(dbt);
      const v=ci.value.trim();
      if (v) {
        selectedUrl=v; selectedName='Custom Image';
        selectedMeme={url:v,name:'Custom Image',boxes:2};
        document.querySelectorAll('.template-card').forEach(c=>c.classList.remove('selected'));
        dbt=setTimeout(()=>loadZones(v),800);
      } else { selectedUrl=null; selectedMeme=null; }
      clearError();
    });

    document.getElementById('change-template-btn').addEventListener('click',()=>{
      document.querySelector('.section').scrollIntoView({behavior:'smooth'});
    });

    const fs=document.getElementById('font-size');
    fs.addEventListener('input',()=>{ updateFontSizeLabel(); updateSliderFill(fs); });

    document.getElementById('generate-btn').addEventListener('click',handleGenerate);
    document.getElementById('download-btn').addEventListener('click',handleDownload);

    window.addEventListener('resize',()=>{ if(editorImg){ resizeCanvas(); redrawCanvas(); } });
  }

  function updateFontSizeLabel() {
    const s=document.getElementById('font-size');
    document.getElementById('font-size-value').textContent=s.value;
    updateSliderFill(s);
  }

  function updateSliderFill(s) {
    const pct=((parseFloat(s.value)-parseFloat(s.min))/(parseFloat(s.max)-parseFloat(s.min)))*100;
    s.style.setProperty('--fill-pct',`${pct}%`);
  }

  // ── Generate ──────────────────────────────────────────────────────────────
  async function handleGenerate() {
    clearError();
    if (!selectedUrl)  { showError('Pick a template first.'); return; }
    if (zoneDetecting) { showError('Still analyzing, please wait…'); return; }

    const texts=currentZones.map((_,i)=>{
      const el=document.getElementById(`zone-${i}`);
      return el?el.value.trim():'';
    });
    if (!texts.some(t=>t)) { showError('Enter text in at least one field.'); return; }

    setLoading(true);
    try {
      const res=await fetch('/generate',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          image_url:selectedUrl, texts, zones:currentZones,
          font_size:parseInt(document.getElementById('font-size').value,10),
          text_color:document.getElementById('text-color').value,
        }),
      });
      const data=await res.json();
      if (!res.ok||data.error) { showError(data.error||'Error generating meme.'); return; }
      displayMeme(data.image);
    } catch { showError('Network error — is the server running?'); }
    finally { setLoading(false); }
  }

  function displayMeme(b64) {
    const p=document.getElementById('meme-preview');
    const ph=document.getElementById('preview-placeholder');
    const dl=document.getElementById('download-btn');
    p.src=`data:image/png;base64,${b64}`; p.dataset.base64=b64;
    p.style.display='block'; ph.style.display='none';
    dl.disabled=false; dl.classList.add('ready');
    p.scrollIntoView({behavior:'smooth',block:'center'});
  }

  function handleDownload() {
    const b64=document.getElementById('meme-preview').dataset.base64;
    if (!b64) return;
    const bytes=atob(b64),ab=new ArrayBuffer(bytes.length),ia=new Uint8Array(ab);
    for (let i=0;i<bytes.length;i++) ia[i]=bytes.charCodeAt(i);
    const url=URL.createObjectURL(new Blob([ab],{type:'image/png'}));
    const a=Object.assign(document.createElement('a'),{href:url,download:'meme.png'});
    document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(url);
  }

  // ── UI helpers ─────────────────────────────────────────────────────────────
  function setGridLoading(on) {
    if (on) document.getElementById('template-grid').innerHTML=
      `<div class="grid-loading"><div class="zone-spin-ring" style="width:28px;height:28px;border-width:3px"></div><span>Loading memes…</span></div>`;
  }

  function setLoading(on) {
    const btn=document.getElementById('generate-btn'),sp=document.getElementById('spinner');
    btn.disabled=on; btn.textContent=on?'Generating…':'Generate Meme';
    sp.style.display=on?'flex':'none';
  }

  function showError(msg) {
    const el=document.getElementById('error-msg'); el.textContent=msg; el.style.display='block';
  }
  function clearError() {
    const el=document.getElementById('error-msg'); el.textContent=''; el.style.display='none';
  }

  document.addEventListener('DOMContentLoaded',init);
})();
