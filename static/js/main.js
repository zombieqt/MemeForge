(() => {
  // ── State ──────────────────────────────────────────────────────────────────
  let allMemes       = [];      // local cache of fetched memes
  let filteredMemes  = [];
  let displayedCount = 0;
  const PAGE_SIZE    = 24;
  let apiPage        = 0;       // current page for /api/memes
  let apiHasMore     = true;    // whether server has more memes
  let apiFetching    = false;

  let selectedMeme   = null;
  let selectedUrl    = null;
  let selectedName   = '';
  let currentZones   = [];
  let zoneDetecting  = false;
  let isOcrImport    = false;   // true when zones came from OCR extraction

  let activeGenre    = 'all';
  let searchQuery    = '';

  // ── Zone editor state ──────────────────────────────────────────────────────
  let editorImg     = null;
  let editorCanvas  = null;
  let editorCtx     = null;
  let activeZoneIdx = -1;
  let dragState     = null;
  let zoneCounter   = 0;

  const ZONE_COLORS = ['#ff6b35','#4ade80','#60a5fa','#f59e0b','#e879f9','#fb7185',
                       '#34d399','#f472b6','#a78bfa','#38bdf8'];
  const HANDLE_SIZE = 9;

  // ── Genre keywords ─────────────────────────────────────────────────────────
  const GENRE_KEYWORDS = {
    reaction: ['distracted','surprised pikachu','pikachu','shocked','wait','seriously','oof','cringe','spongebob','mocking','hide the pain','crying','laughing','nobody','society','tuxedo','mask','blinking','this is fine','fine','disaster','rollsafe','roll safe','think about it','facepalm','confused','hold up','bruh','not sure if','futurama','office','reaction','relatable','kermit','tea','guy','when','me'],
    drake:    ['drake','hotline bling','two buttons','left exit','uno draw','draw 25','gru','plan','choose','option','prefer','tuxedo pooh','tuxedo winnie','choice','picking'],
    brain:    ['brain','expanding brain','galaxy brain','big brain','thinking','iq','smart','galaxy','mind','intelligent','sigma','chad','gigachad','alphachad'],
    change:   ['change my mind','unpopular opinion','controversial','opinion','debate','fight me','crowder','hot take'],
    animals:  ['dog','cat','doge','grumpy cat','animal','bird','frog','bear','wolf','lion','fish','shark','monkey','gorilla','penguin','baby yoda','doggo','puppy','kitten','much wow','shiba','corgi','husky','bunny','rabbit','hamster','parrot','owl','fox','deer','cow','pig','duck','chicken','turtle','seal','otter','panda','koala','sloth','llama','capybara','axolotl','vibing cat','business cat','nyan cat'],
    classic:  ['one does not simply','boromir','forever alone','bad luck brian','success kid','first world problems','scumbag steve','insanity wolf','philosoraptor','good guy greg','overly attached','wonka','confession bear','third world skeptical','ancient aliens','y u no','oprah','most interesting man','i should buy a boat','back in my day','laughing men','epic handshake','forever','awkward','socially awkward','actual advice mallard','courage wolf'],
    wholesome:['wholesome','heartwarming','happy','love','cute','dad','mom','family','friend','kids','children','good','kind','care','hug','support','proud','thankful','warm','sweet','adorable','touching','feel good','uplifting','smile','joy','comfort','cozy','baby','toddler','grandma'],
    political:['political','trump','biden','president','government','congress','senator','politician','vote','election','democrat','republican','liberal','conservative','america','policy','law','tax','border','white house','capitol','supreme court','elon','musk','putin','nato','eu','climate'],
    gaming:   ['game','gaming','mario','minecraft','fortnite','among us','player','gamer','level','boss','noob','pro','xbox','playstation','pc','steam','nintendo','league of legends','lol','dota','valorant','overwatch','apex','warzone','cod','halo','zelda','pokemon','dark souls','elden ring','skyrim','fallout','gta','roblox','terraria','stardew','smash','speedrun','fps','rpg','esports','twitch','streamer','git gud','skill issue','tryhard'],
    sports:   ['sport','football','soccer','basketball','baseball','tennis','nba','nfl','mlb','team','player','coach','win','loss','champion','goat','mvp','brady','lebron','messi','ronaldo','jordan','curry','mahomes','kobe','shaq','wrestling','boxing','mma','ufc','golf','hockey','nhl','formula 1','f1','nascar','olympics','world cup','super bowl','finals','playoffs','touchdown','slam dunk','hat trick'],
    money:    ['stonks','money','rich','poor','broke','cash','bank','invest','stock','crypto','bitcoin','ethereum','dogecoin','nft','economy','salary','afford','price','expensive','cheap','free','discount','budget','savings','debt','credit','loan','mortgage','rent','inflation','recession','wall street','robinhood','gamestop','yolo','tendies','to the moon','diamond hands','tax','irs','profit','loss','bankruptcy'],
  };

  // ── Init ───────────────────────────────────────────────────────────────────
  async function init() {
    updateFontSizeLabel();
    buildEditorCanvas();
    bindEvents();
    setupInfiniteScroll();
    await loadNextPage();
  }

  // ── /api/memes pagination ──────────────────────────────────────────────────
  async function loadNextPage(reset = false) {
    if (apiFetching || (!apiHasMore && !reset)) return;
    apiFetching = true;

    if (reset) {
      apiPage    = 0;
      apiHasMore = true;
      allMemes   = [];
      filteredMemes = [];
      displayedCount = 0;
      document.getElementById('template-grid').innerHTML = '';
    }

    setGridLoading(reset && apiPage === 0);

    try {
      const q     = searchQuery ? `&q=${encodeURIComponent(searchQuery)}` : '';
      const res   = await fetch(`/api/memes?page=${apiPage}&per_page=${PAGE_SIZE}${q}`);
      const data  = await res.json();

      const tagged = data.memes.map(m => ({ ...m, genre: detectGenre(m.name) }));
      allMemes.push(...tagged);
      apiHasMore = data.has_more;
      apiPage++;

      document.getElementById('template-count').textContent = `${data.total}+ memes`;

      applyFiltersLocally();
    } catch (e) {
      console.error('Failed to load memes:', e);
      document.getElementById('template-count').textContent = 'Load failed';
    } finally {
      apiFetching = false;
      setGridLoading(false);
    }
  }

  function setupInfiniteScroll() {
    const sentinel = document.getElementById('scroll-sentinel');
    if (!sentinel || !('IntersectionObserver' in window)) return;
    const obs = new IntersectionObserver(entries => {
      if (entries[0].isIntersecting && !apiFetching) {
        // First exhaust local filtered pool, then fetch next server page
        if (displayedCount < filteredMemes.length) {
          renderNextSlice();
        } else if (apiHasMore) {
          loadNextPage();
        }
      }
    }, { rootMargin: '200px' });
    obs.observe(sentinel);
  }

  function detectGenre(name) {
    const lower = name.toLowerCase();
    for (const [g, kws] of Object.entries(GENRE_KEYWORDS))
      if (kws.some(k => lower.includes(k))) return g;
    const words = lower.split(/\W+/);
    for (const [g, kws] of Object.entries(GENRE_KEYWORDS))
      if (kws.some(k => words.includes(k))) return g;
    return 'classic';
  }

  // ── Local filtering (on already-fetched memes) ─────────────────────────────
  function applyFiltersLocally() {
    const q = searchQuery.trim().toLowerCase();
    filteredMemes = allMemes.filter(m => {
      const mg = activeGenre === 'all' || m.genre === activeGenre;
      const ms = !q || m.name.toLowerCase().includes(q);
      return mg && ms;
    });

    // Only reset grid if search/genre changed (not during pagination)
    const grid = document.getElementById('template-grid');
    // Count currently rendered cards
    const rendered = grid.querySelectorAll('.template-card').length;
    if (rendered === 0) {
      displayedCount = 0;
    }

    document.getElementById('grid-empty').style.display =
      filteredMemes.length === 0 ? 'flex' : 'none';

    // Render any new items that weren't yet shown
    renderNextSlice();
  }

  function renderNextSlice() {
    const grid  = document.getElementById('template-grid');
    const slice = filteredMemes.slice(displayedCount, displayedCount + PAGE_SIZE);
    slice.forEach(m => grid.appendChild(createCard(m)));
    displayedCount += slice.length;
    document.getElementById('load-more-wrap').style.display =
      (displayedCount < filteredMemes.length || apiHasMore) ? 'flex' : 'none';
  }

  function resetAndReload() {
    document.getElementById('template-grid').innerHTML = '';
    displayedCount = 0;
    filteredMemes  = [];
    // Re-filter from current allMemes first (instant), then fetch more if needed
    applyFiltersLocally();
    if (filteredMemes.length < PAGE_SIZE && apiHasMore) {
      loadNextPage();
    }
  }

  // ── Card creation ──────────────────────────────────────────────────────────
  function createCard(meme) {
    const card = document.createElement('div');
    card.className = 'template-card';
    const img = document.createElement('img');
    img.src = meme.url; img.alt = meme.name; img.loading = 'lazy';
    // Error fallback
    img.onerror = () => { card.style.display = 'none'; };
    const lbl = document.createElement('span');
    lbl.className = 'template-label'; lbl.textContent = meme.name;
    const bb = document.createElement('span');
    bb.className = 'box-badge';
    bb.textContent = `${meme.boxes || 2} zone${(meme.boxes||2) !== 1 ? 's' : ''}`;
    const gb = document.createElement('span');
    gb.className = 'genre-badge'; gb.textContent = meme.genre || 'classic';
    // Source badge
    const sb = document.createElement('span');
    sb.className = 'source-badge';
    const src = (meme.source || 'imgflip');
    sb.textContent = src.startsWith('reddit/') ? '🟠 ' + src.split('/')[1] : '🟢 imgflip';
    card.append(img, lbl, bb, gb, sb);
    card.addEventListener('click', () => selectTemplate(meme, card));
    return card;
  }

  // ── Template selection ─────────────────────────────────────────────────────
  async function selectTemplate(meme, cardEl) {
    if (zoneDetecting) return;
    selectedMeme = meme; selectedUrl = meme.url; selectedName = meme.name;
    isOcrImport = false;
    document.querySelectorAll('.template-card').forEach(c => c.classList.remove('selected'));
    if (cardEl) cardEl.classList.add('selected');
    document.getElementById('editor-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
    document.getElementById('ocr-badge').style.display = 'none';
    clearError();
    updateThumbBar(meme.url, meme.name);
    await loadZones(meme.url);
  }

  function updateThumbBar(url, name) {
    const wrap  = document.getElementById('selected-thumb-wrap');
    const thumb = document.getElementById('selected-thumb');
    const sname = document.getElementById('selected-name');
    thumb.src = url; sname.textContent = name;
    wrap.style.display = 'flex';
  }

  // ── Zone detection ─────────────────────────────────────────────────────────
  async function loadZones(url) {
    zoneDetecting = true;
    setZoneLoading(true);
    activeZoneIdx = -1;
    try {
      const res  = await fetch('/zones', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_url: url, meme_name: selectedName }),
      });
      const data = await res.json();
      currentZones = (data.zones || []).map(z => ({ ...z, _id: ++zoneCounter }));
      renderAll(!!data.fallback);
    } catch {
      currentZones = [
        { label: 'Top text',    x: 0.0, y: 0.0,  w: 1.0, h: 0.25, pos: 'top',    _id: ++zoneCounter },
        { label: 'Bottom text', x: 0.0, y: 0.75, w: 1.0, h: 0.25, pos: 'bottom', _id: ++zoneCounter },
      ];
      renderAll(true);
    } finally {
      zoneDetecting = false; setZoneLoading(false);
    }
  }

  // ── OCR Import ─────────────────────────────────────────────────────────────
  async function importUrlWithOcr(url) {
    if (!url) { showImportStatus('error', 'Please paste a valid image URL.'); return; }
    setImportLoading(true);
    showImportStatus('info', 'Downloading image and extracting text…');
    try {
      const res  = await fetch('/api/extract-text', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_url: url }),
      });
      const data = await res.json();
      if (!res.ok || data.error) {
        showImportStatus('error', data.error || 'Could not extract text.'); return;
      }

      selectedUrl  = url;
      selectedName = 'Imported Meme';
      selectedMeme = { url, name: 'Imported Meme', boxes: data.zones.length };
      isOcrImport  = true;

      // Build zones — if OCR found text, pre-fill inputs with that text
      currentZones = data.zones.map(z => ({
        label:  z.label || z.text || 'Text zone',
        x: z.x, y: z.y, w: z.w, h: z.h,
        pos: z.pos || 'center',
        _id: ++zoneCounter,
        _prefill: z.text || '',   // original detected text
      }));

      const method = data.method;
      const count  = currentZones.length;
      const msg = method === 'ocr'
        ? `✅ Found ${count} text zone${count!==1?'s':''} with existing text — pre-filled below. Edit to remix!`
        : `ℹ️ No OCR text found — ${count} layout zone${count!==1?'s':''} detected. Start typing!`;

      showImportStatus(method === 'ocr' ? 'success' : 'info', msg);

      document.querySelectorAll('.template-card').forEach(c => c.classList.remove('selected'));
      updateThumbBar(url, 'Imported Meme');

      const ocrBadge = document.getElementById('ocr-badge');
      ocrBadge.style.display = method === 'ocr' ? 'flex' : 'none';

      document.getElementById('editor-section').scrollIntoView({ behavior: 'smooth', block: 'start' });

      // Render inputs with pre-filled text
      renderAll(false);
      // After render, fill input values with detected text
      if (method === 'ocr') {
        currentZones.forEach((zone, i) => {
          const el = document.getElementById(`zone-${i}`);
          if (el && zone._prefill) el.value = zone._prefill;
        });
        redrawCanvas(); // update canvas with the pre-filled text
      }

    } catch (e) {
      showImportStatus('error', `Network error: ${e.message}`);
    } finally {
      setImportLoading(false);
    }
  }

  function setImportLoading(on) {
    document.getElementById('import-btn-label').style.display = on ? 'none' : 'inline';
    document.getElementById('import-spinner').style.display   = on ? 'block' : 'none';
    document.getElementById('import-url-btn').disabled = on;
  }

  function showImportStatus(type, msg) {
    const el = document.getElementById('import-status');
    el.textContent = msg;
    el.className   = `import-status import-status--${type}`;
    el.style.display = 'block';
  }

  // ── Zone loading UI ────────────────────────────────────────────────────────
  function setZoneLoading(on) {
    const tf = document.getElementById('text-fields');
    const badge = document.getElementById('zone-count');
    if (on) {
      tf.innerHTML = `<div class="zone-detecting"><div class="zone-spin-ring"></div><span>Analyzing layout…</span></div>`;
      badge.textContent = '';
      document.getElementById('generate-btn').disabled = true;
    } else {
      document.getElementById('generate-btn').disabled = false;
    }
  }

  function renderAll(isFallback = false) {
    renderTextInputs(isFallback);
    loadEditorImage(selectedUrl);
  }

  // ── Text inputs ────────────────────────────────────────────────────────────
  function renderTextInputs(isFallback = false) {
    const container = document.getElementById('text-fields');
    const badge     = document.getElementById('zone-count');
    container.innerHTML = '';

    if (!currentZones.length) {
      container.innerHTML = '<p class="pick-hint">← Pick a template above</p>';
      badge.textContent = ''; return;
    }

    currentZones.forEach((zone, i) => {
      const group = document.createElement('div');
      group.className = 'field-group zone-field-group';
      group.dataset.idx = i;

      const labelRow = document.createElement('div');
      labelRow.className = 'zone-label-row';

      const dot = document.createElement('button');
      dot.className = 'zone-dot';
      dot.style.background = ZONE_COLORS[i % ZONE_COLORS.length];
      dot.title = 'Focus on canvas';
      dot.addEventListener('click', () => { activeZoneIdx = i; redrawCanvas(); });

      const nameInp = document.createElement('input');
      nameInp.type = 'text'; nameInp.className = 'zone-name-input';
      nameInp.value = zone.label; nameInp.title = 'Zone label';
      nameInp.addEventListener('input', () => {
        currentZones[i].label = nameInp.value || `Zone ${i+1}`;
        redrawCanvas();
      });

      const delBtn = document.createElement('button');
      delBtn.className = 'zone-delete-btn'; delBtn.innerHTML = '✕';
      delBtn.title = 'Delete zone';
      delBtn.addEventListener('click', () => deleteZone(i));

      labelRow.append(dot, nameInp, delBtn);

      const inp = document.createElement('input');
      inp.type = 'text'; inp.id = `zone-${i}`;
      inp.placeholder = zone.label + '…';
      inp.addEventListener('focus', () => { activeZoneIdx = i; redrawCanvas(); });
      inp.addEventListener('input', () => redrawCanvas());

      group.append(labelRow, inp);
      container.appendChild(group);
    });

    // Add zone button
    const addRow = document.createElement('div');
    addRow.className = 'add-zone-row';
    const addBtn = document.createElement('button');
    addBtn.className = 'btn-add-zone'; addBtn.innerHTML = '＋ Add text zone';
    addBtn.addEventListener('click', addZone);
    addRow.appendChild(addBtn);
    container.appendChild(addRow);

    const n = currentZones.length;
    badge.textContent = `${n} zone${n!==1?'s':''} ${isFallback ? '(fallback)' : '✓'}`;
    badge.className   = 'zone-badge' + (isFallback ? ' zone-badge--fallback' : '');
  }

  function deleteZone(idx) {
    currentZones.splice(idx, 1);
    if (activeZoneIdx >= currentZones.length) activeZoneIdx = currentZones.length - 1;
    renderTextInputs(); redrawCanvas();
  }

  function addZone() {
    currentZones.push({ label: `Text ${currentZones.length+1}`, x:0.1, y:0.1, w:0.80, h:0.18, pos:'center', _id:++zoneCounter });
    activeZoneIdx = currentZones.length - 1;
    renderTextInputs(); redrawCanvas();
    const ni = document.getElementById(`zone-${currentZones.length-1}`);
    if (ni) ni.focus();
  }

  // ── Canvas editor ──────────────────────────────────────────────────────────
  function buildEditorCanvas() {
    editorCanvas = document.getElementById('zone-editor-canvas');
    editorCtx    = editorCanvas.getContext('2d');
    editorCanvas.addEventListener('mousedown',  onDown);
    editorCanvas.addEventListener('mousemove',  onMove);
    editorCanvas.addEventListener('mouseup',    onUp);
    editorCanvas.addEventListener('mouseleave', onUp);
    editorCanvas.addEventListener('touchstart', e => { e.preventDefault(); onDown(t2m(e)); }, { passive: false });
    editorCanvas.addEventListener('touchmove',  e => { e.preventDefault(); onMove(t2m(e)); }, { passive: false });
    editorCanvas.addEventListener('touchend',   e => { onUp(e); }, { passive: false });
  }

  function t2m(e) {
    const t = e.touches[0] || e.changedTouches[0];
    return { clientX: t.clientX, clientY: t.clientY };
  }

  function loadEditorImage(url) {
    if (!url) return;
    document.getElementById('canvas-editor-wrap').style.display = 'block';
    document.getElementById('editor-hint').style.display = 'flex';
    document.getElementById('canvas-placeholder').style.display = 'none';

    const tryLoad = (co) => {
      editorImg = new Image();
      if (co) editorImg.crossOrigin = 'anonymous';
      editorImg.onload  = () => { resizeCanvas(); redrawCanvas(); };
      editorImg.onerror = co ? () => tryLoad(false) : null;
      editorImg.src = url;
    };
    tryLoad(true);
  }

  function resizeCanvas() {
    if (!editorImg) return;
    const wrap   = document.getElementById('canvas-editor-wrap');
    const maxW   = wrap.clientWidth;
    const aspect = editorImg.naturalWidth / editorImg.naturalHeight;
    const dispW  = Math.min(maxW, editorImg.naturalWidth, 900);
    const dispH  = Math.round(dispW / aspect);
    editorCanvas.width = dispW; editorCanvas.height = dispH;
    editorCanvas.style.width = dispW + 'px'; editorCanvas.style.height = dispH + 'px';
  }

  function redrawCanvas() {
    if (!editorImg || !editorCtx) return;
    const cw = editorCanvas.width, ch = editorCanvas.height;
    editorCtx.clearRect(0, 0, cw, ch);
    editorCtx.drawImage(editorImg, 0, 0, cw, ch);

    currentZones.forEach((zone, i) => {
      const px = zone.x*cw, py = zone.y*ch, pw = zone.w*cw, ph = zone.h*ch;
      const col    = ZONE_COLORS[i % ZONE_COLORS.length];
      const isAct  = i === activeZoneIdx;

      editorCtx.fillStyle   = col + (isAct ? '2e' : '18');
      editorCtx.fillRect(px, py, pw, ph);
      editorCtx.strokeStyle = col;
      editorCtx.lineWidth   = isAct ? 2.5 : 1.5;
      editorCtx.setLineDash(isAct ? [] : [5, 4]);
      editorCtx.strokeRect(px+0.5, py+0.5, pw-1, ph-1);
      editorCtx.setLineDash([]);

      // Number badge
      const br = Math.max(8, Math.min(13, Math.min(pw, ph)*0.22));
      const bx = px+br+5, by = py+br+5;
      editorCtx.fillStyle = col;
      editorCtx.beginPath(); editorCtx.arc(bx, by, br, 0, Math.PI*2); editorCtx.fill();
      editorCtx.fillStyle = '#fff';
      editorCtx.font = `bold ${Math.max(8, br*1.05)}px Barlow Condensed,sans-serif`;
      editorCtx.textAlign = 'center'; editorCtx.textBaseline = 'middle';
      editorCtx.fillText(i+1, bx, by+0.5);

      // Live text preview
      const tv = (document.getElementById(`zone-${i}`) || {}).value || '';
      if (tv.trim()) {
        const fs = Math.max(10, Math.min(ph*0.28, pw*0.10, 20));
        editorCtx.font = `900 ${fs}px Impact,Arial Black,sans-serif`;
        editorCtx.textAlign = 'center'; editorCtx.textBaseline = 'middle';
        editorCtx.fillStyle = '#000';
        editorCtx.fillText(tv.toUpperCase(), px+pw/2+1, py+ph/2+1, pw-10);
        editorCtx.fillStyle = '#fff';
        editorCtx.fillText(tv.toUpperCase(), px+pw/2, py+ph/2, pw-10);
      }

      // Resize handle on active
      if (isAct) {
        const rx = px+pw, ry = py+ph, hs = HANDLE_SIZE;
        editorCtx.fillStyle = '#fff'; editorCtx.strokeStyle = col; editorCtx.lineWidth = 2;
        editorCtx.beginPath(); editorCtx.roundRect(rx-hs-2, ry-hs-2, hs*2+4, hs*2+4, 3);
        editorCtx.fill(); editorCtx.stroke();
        editorCtx.fillStyle = col; editorCtx.font = 'bold 11px sans-serif';
        editorCtx.textAlign = 'center'; editorCtx.textBaseline = 'middle';
        editorCtx.fillText('⤡', rx, ry);
        editorCtx.strokeStyle = col+'88'; editorCtx.lineWidth = 1;
        editorCtx.setLineDash([2, 3]);
        editorCtx.strokeRect(px+4, py+4, Math.min(pw-8, 26), Math.min(ph-8, 26));
        editorCtx.setLineDash([]);
      }
    });
  }

  function cpos(e) {
    const r = editorCanvas.getBoundingClientRect();
    return { x: (e.clientX-r.left)*(editorCanvas.width/r.width),
             y: (e.clientY-r.top)*(editorCanvas.height/r.height) };
  }

  function isOnHandle(mx, my, zone) {
    const rx = (zone.x+zone.w)*editorCanvas.width, ry = (zone.y+zone.h)*editorCanvas.height;
    return Math.abs(mx-rx) <= HANDLE_SIZE+4 && Math.abs(my-ry) <= HANDLE_SIZE+4;
  }

  function isInZone(mx, my, zone) {
    return mx>=zone.x*editorCanvas.width && mx<=(zone.x+zone.w)*editorCanvas.width &&
           my>=zone.y*editorCanvas.height && my<=(zone.y+zone.h)*editorCanvas.height;
  }

  function onDown(e) {
    if (!currentZones.length) return;
    const { x: mx, y: my } = cpos(e);
    const cw = editorCanvas.width, ch = editorCanvas.height;
    if (activeZoneIdx>=0 && activeZoneIdx<currentZones.length &&
        isOnHandle(mx, my, currentZones[activeZoneIdx])) {
      dragState = { type:'resize', zoneIdx:activeZoneIdx, startX:mx, startY:my, origZone:{...currentZones[activeZoneIdx]} };
      editorCanvas.style.cursor = 'nwse-resize'; return;
    }
    for (let i = currentZones.length-1; i>=0; i--) {
      if (isInZone(mx, my, currentZones[i])) {
        activeZoneIdx = i;
        dragState = { type:'move', zoneIdx:i, startX:mx, startY:my, origZone:{...currentZones[i]} };
        editorCanvas.style.cursor = 'grabbing';
        const inp = document.getElementById(`zone-${i}`); if (inp) inp.focus();
        redrawCanvas(); return;
      }
    }
    activeZoneIdx = -1; redrawCanvas();
  }

  function onMove(e) {
    const { x: mx, y: my } = cpos(e);
    const cw = editorCanvas.width, ch = editorCanvas.height;
    if (!dragState) {
      if (activeZoneIdx>=0 && activeZoneIdx<currentZones.length) {
        const z = currentZones[activeZoneIdx];
        if (isOnHandle(mx,my,z)) { editorCanvas.style.cursor='nwse-resize'; return; }
        if (isInZone(mx,my,z))   { editorCanvas.style.cursor='grab'; return; }
      }
      for (let i=currentZones.length-1;i>=0;i--)
        if (isInZone(mx,my,currentZones[i])) { editorCanvas.style.cursor='grab'; return; }
      editorCanvas.style.cursor = 'crosshair'; return;
    }
    const dx = (mx-dragState.startX)/cw, dy = (my-dragState.startY)/ch;
    const orig = dragState.origZone, z = currentZones[dragState.zoneIdx];
    if (dragState.type==='move') {
      z.x = Math.max(0, Math.min(1-orig.w, orig.x+dx));
      z.y = Math.max(0, Math.min(1-orig.h, orig.y+dy));
    } else {
      z.w = Math.max(0.05, Math.min(1-orig.x, orig.w+dx));
      z.h = Math.max(0.04, Math.min(1-orig.y, orig.h+dy));
    }
    redrawCanvas();
  }

  function onUp() { if (dragState) { dragState=null; editorCanvas.style.cursor='default'; } }

  // ── Bind events ────────────────────────────────────────────────────────────
  function bindEvents() {
    // Search — reset + reload from server
    const si = document.getElementById('search-input');
    const sc = document.getElementById('search-clear');
    let searchDbt;
    si.addEventListener('input', () => {
      searchQuery = si.value;
      sc.style.display = searchQuery ? 'flex' : 'none';
      clearTimeout(searchDbt);
      searchDbt = setTimeout(() => {
        // For short queries try local filter first; reload from server if too few results
        const localFiltered = allMemes.filter(m => m.name.toLowerCase().includes(searchQuery.toLowerCase()));
        if (localFiltered.length >= PAGE_SIZE || !apiHasMore) {
          document.getElementById('template-grid').innerHTML = '';
          displayedCount = 0;
          filteredMemes = localFiltered;
          renderNextSlice();
        } else {
          loadNextPage(true);
        }
      }, 350);
    });
    sc.addEventListener('click', () => {
      si.value = ''; searchQuery = ''; sc.style.display = 'none';
      loadNextPage(true);
    });

    // Genre pills
    document.getElementById('genre-pills').addEventListener('click', e => {
      const p = e.target.closest('.pill'); if (!p) return;
      document.querySelectorAll('.pill').forEach(x => x.classList.remove('active'));
      p.classList.add('active'); activeGenre = p.dataset.genre;
      document.getElementById('template-grid').innerHTML = '';
      displayedCount = 0;
      applyFiltersLocally();
    });

    // Load more button
    document.getElementById('load-more-btn').addEventListener('click', () => {
      if (displayedCount < filteredMemes.length) renderNextSlice();
      else if (apiHasMore) loadNextPage();
    });

    // Import URL button
    document.getElementById('import-url-btn').addEventListener('click', () => {
      const url = document.getElementById('custom-url').value.trim();
      importUrlWithOcr(url);
    });
    document.getElementById('custom-url').addEventListener('keydown', e => {
      if (e.key === 'Enter') {
        const url = document.getElementById('custom-url').value.trim();
        importUrlWithOcr(url);
      }
    });

    // Change template
    document.getElementById('change-template-btn').addEventListener('click', () => {
      document.querySelector('.section').scrollIntoView({ behavior: 'smooth' });
    });

    // Font size
    const fs = document.getElementById('font-size');
    fs.addEventListener('input', () => { updateFontSizeLabel(); updateSliderFill(fs); });

    // Generate + Download
    document.getElementById('generate-btn').addEventListener('click', handleGenerate);
    document.getElementById('download-btn').addEventListener('click', handleDownload);

    window.addEventListener('resize', () => { if (editorImg) { resizeCanvas(); redrawCanvas(); } });
  }

  function updateFontSizeLabel() {
    const s = document.getElementById('font-size');
    document.getElementById('font-size-value').textContent = s.value;
    updateSliderFill(s);
  }

  function updateSliderFill(s) {
    const pct = ((parseFloat(s.value)-parseFloat(s.min))/(parseFloat(s.max)-parseFloat(s.min)))*100;
    s.style.setProperty('--fill-pct', `${pct}%`);
  }

  // ── Generate ──────────────────────────────────────────────────────────────
  async function handleGenerate() {
    clearError();
    if (!selectedUrl)  { showError('Pick a template first.'); return; }
    if (zoneDetecting) { showError('Still analyzing, please wait…'); return; }
    const texts = currentZones.map((_,i) => {
      const el = document.getElementById(`zone-${i}`); return el ? el.value.trim() : '';
    });
    if (!texts.some(t => t)) { showError('Enter text in at least one field.'); return; }
    setLoading(true);
    try {
      const res  = await fetch('/generate', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_url: selectedUrl, texts, zones: currentZones,
          font_size: parseInt(document.getElementById('font-size').value, 10),
          text_color: document.getElementById('text-color').value,
        }),
      });
      const data = await res.json();
      if (!res.ok || data.error) { showError(data.error || 'Error generating meme.'); return; }
      displayMeme(data.image);
    } catch { showError('Network error — is the server running?'); }
    finally { setLoading(false); }
  }

  function displayMeme(b64) {
    const p = document.getElementById('meme-preview');
    const ph = document.getElementById('preview-placeholder');
    const dl = document.getElementById('download-btn');
    p.src = `data:image/png;base64,${b64}`; p.dataset.base64 = b64;
    p.style.display = 'block'; ph.style.display = 'none';
    dl.disabled = false; dl.classList.add('ready');
    p.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  function handleDownload() {
    const b64 = document.getElementById('meme-preview').dataset.base64; if (!b64) return;
    const bytes = atob(b64), ab = new ArrayBuffer(bytes.length), ia = new Uint8Array(ab);
    for (let i=0;i<bytes.length;i++) ia[i] = bytes.charCodeAt(i);
    const url = URL.createObjectURL(new Blob([ab],{type:'image/png'}));
    const a = Object.assign(document.createElement('a'),{href:url,download:'meme.png'});
    document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(url);
  }

  // ── UI helpers ─────────────────────────────────────────────────────────────
  function setGridLoading(on) {
    if (on) document.getElementById('template-grid').innerHTML =
      `<div class="grid-loading"><div class="zone-spin-ring" style="width:28px;height:28px;border-width:3px"></div><span>Loading memes…</span></div>`;
  }

  function setLoading(on) {
    const btn = document.getElementById('generate-btn'), sp = document.getElementById('spinner');
    btn.disabled = on; btn.textContent = on ? 'Generating…' : 'Generate Meme';
    sp.style.display = on ? 'flex' : 'none';
  }

  function showError(msg) {
    const el = document.getElementById('error-msg'); el.textContent = msg; el.style.display = 'block';
  }
  function clearError() {
    const el = document.getElementById('error-msg'); el.textContent = ''; el.style.display = 'none';
  }

  document.addEventListener('DOMContentLoaded', init);
})();
