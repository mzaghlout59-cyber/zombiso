// Zombiso AI City viewer: replays a run's events.jsonl as a living 2D city.
// State comes only from events (apply); animation is a separate layer (animate),
// so scrubbing can rebuild state instantly without replaying effects.
(() => {
  "use strict";

  const W = 1200, H = 720;
  const TICK_MS = 1400;            // one city tick at 1x speed
  const SPARK_POINTS = 60;         // price history shown per exchange
  const canvas = document.getElementById("city");
  const ctx = canvas.getContext("2d");
  const $ = (id) => document.getElementById(id);

  const C = {
    road: "#16203a", roadLine: "#24345a", panel: "#101a30", panelHi: "#18264a",
    stroke: "#2b3b63", text: "#dfe6f5", muted: "#7f8cab", gold: "#f2b84b",
    green: "#4cd497", red: "#ff6b6b", amber: "#ffb347", violet: "#a78bfa", gray: "#6b7794",
    white: "#e8eefc",
  };

  // ---------- the city map (logical 1200x720) ----------
  const PLACES = {
    Scout:        { x: 150,  y: 95,  w: 96,  h: 52, title: "Scout", sub: "trend", kind: "squad" },
    News:         { x: 260,  y: 95,  w: 96,  h: 52, title: "News", sub: "headlines", kind: "squad", stub: true },
    Pulse:        { x: 370,  y: 95,  w: 96,  h: 52, title: "Pulse", sub: "crowd mood", kind: "squad" },
    Lens:         { x: 480,  y: 95,  w: 96,  h: 52, title: "Lens", sub: "patterns", kind: "squad" },
    Sage:         { x: 315,  y: 228, w: 140, h: 66, title: "Sage", sub: "weighs signals", kind: "commander" },
    Axiom:        { x: 640,  y: 95,  w: 150, h: 56, title: "Axiom", sub: "strategist", kind: "commander" },
    Raphael:      { x: 640,  y: 245, w: 180, h: 92, title: "Raphael", sub: "headquarters", kind: "hq" },
    Aegis:        { x: 930,  y: 245, w: 130, h: 92, title: "Aegis", sub: "risk gate", kind: "gate" },
    Ledgerkeeper: { x: 870,  y: 95,  w: 110, h: 52, title: "Ledgerkeeper", sub: "exposure", kind: "squad" },
    Scorekeeper:  { x: 995,  y: 95,  w: 110, h: 52, title: "Scorekeeper", sub: "win rate", kind: "squad" },
    Ultron:       { x: 1125, y: 200, w: 70,  h: 170, title: "Ultron", sub: "auditor", kind: "tower" },
  };
  const AGENT_ALIAS = {
    MarketResearch: "Scout", NewsResearch: "News", Sentiment: "Pulse",
    Charts: "Lens", Strategist: "Axiom", Aegis: "Aegis",
    PortfolioManager: "Ledgerkeeper", PerformanceAnalyst: "Scorekeeper",
  };
  const ROUTE = { Scout: "Sage", News: "Sage", Pulse: "Sage", Lens: "Sage", Axiom: "Raphael",
                  Ledgerkeeper: "Aegis", Scorekeeper: "Aegis" };
  const READING = { Scout: "trend", News: "sentiment", Pulse: "crowd_mood", Lens: "pattern", Axiom: "signal" };
  const VOTE_COLOR = {
    up: C.green, bullish: C.green, breakout: C.green, positive: C.green, buy: C.gold,
    down: C.red, bearish: C.red, breakdown: C.red, negative: C.red,
  };
  const DEFAULT_META = {
    run_id: "unknown", cycles_per_day: 20, watchlist: null, max_open_positions: 3,
    max_daily_loss: 100, max_risk_per_trade: 25, take_profit_rr: 2,
  };

  // ---------- run data + playback state ----------
  let meta = null, runId = null, audit = null;
  let events = [], groups = [], evPos = [];
  let state = null, applied = 0, P = 0, playing = true, speed = 1, dragging = false;
  let fx = freshFx();
  let stars = makeStars();

  function freshFx() { return { particles: [], glows: {}, floats: [], banner: null, eyeTarget: null, pulse: 0 }; }

  function makeStars() {
    const s = []; let seed = 7;
    const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    for (let i = 0; i < 90; i++) s.push({ x: rnd() * W, y: rnd() * 380, r: rnd() * 1.4 + 0.3, tw: rnd() * 6 });
    return s;
  }

  function exchanges() {
    const syms = meta.watchlist || [];
    const n = Math.max(syms.length, 1), gap = 30, left = 60, right = 1140;
    const w = (right - left - gap * (n - 1)) / n;
    return syms.map((sym, i) => ({ sym, x: left + i * (w + gap), y: 430, w, h: 230 }));
  }
  function exchangeOf(sym) { return exchanges().find((x) => x.sym === sym); }

  // Group events by tick; each event gets a fractional position inside its tick.
  function indexEvents() {
    groups = []; evPos = new Array(events.length);
    let i = 0;
    while (i < events.length) {
      const t = events[i].tick; let j = i;
      while (j < events.length && events[j].tick === t) j++;
      const g = groups.length;
      groups.push({ tick: t, start: i, end: j });
      for (let k = i; k < j; k++) evPos[k] = g + (k - i + 1) / (j - i + 1);
      i = j;
    }
  }

  function freshState() {
    const prices = {};
    (meta.watchlist || []).forEach((s) => (prices[s] = []));
    return { tick: 0, day: 0, prices, open: {}, realized: 0, dayPnl: {}, trades: 0,
             wins: 0, losses: 0, decisions: {}, feed: [], seenDay: -1, book: null, score: null };
  }

  const money = (v) => (v < 0 ? "-$" : "$") + Math.abs(v).toFixed(2);
  const signed = (v) => (v >= 0 ? "+" : "-") + "$" + Math.abs(v).toFixed(2);

  function pushFeed(s, tick, text, cls) {
    s.feed.unshift({ tick, text, cls });
    if (s.feed.length > 200) s.feed.pop();
  }

  // ---------- state: pure replay of one event ----------
  function apply(e, s) {
    switch (e.kind) {
      case "agent_report":
        if (e.agent === "PortfolioManager") s.book = e.result;
        if (e.agent === "PerformanceAnalyst") s.score = e.result;
        break;
      case "tick":
        s.tick = e.tick;
        if (e.day !== s.seenDay) { pushFeed(s, e.tick, `Day ${e.day + 1} begins`, "day"); s.seenDay = e.day; }
        s.day = e.day;
        for (const [sym, p] of Object.entries(e.prices || {})) (s.prices[sym] ||= []).push(p);
        break;
      case "decision":
        s.decisions[e.symbol] = e;
        if (e.action === "buy" && !e.executed) {
          if (!e.approved) pushFeed(s, e.tick, `Aegis denied ${e.symbol}: ${e.risk_reason}`, "deny");
          else pushFeed(s, e.tick, `${e.symbol} skipped: Sage confidence ${e.confidence}`, "deny");
        }
        break;
      case "trade_opened":
        s.open[e.trade_id] = e; s.trades++;
        pushFeed(s, e.tick, `Opened #${e.trade_id} ${e.symbol}: ${e.size} @ ${e.entry.toFixed(2)}, stop ${e.stop_loss.toFixed(2)}`, "open");
        break;
      case "trade_closed": {
        delete s.open[e.trade_id];
        s.realized += e.pnl;
        s.dayPnl[e.day] = (s.dayPnl[e.day] || 0) + e.pnl;
        if (e.pnl >= 0) s.wins++; else s.losses++;
        const why = { take_profit: "target hit", stop_loss: "stopped out", end_of_day: "closed at the bell" }[e.reason] || e.reason;
        pushFeed(s, e.tick, `Closed #${e.trade_id} ${e.symbol}, ${why}: ${signed(e.pnl)}`, e.pnl >= 0 ? "win" : "loss");
        break;
      }
    }
  }

  // ---------- animation: effects for one event ----------
  function center(name) { const p = PLACES[name]; return { x: p.x, y: p.y }; }
  function travel(from, to, color, now, opts = {}) {
    const pts = Array.isArray(to) ? [from, ...to] : [from, to];
    const dur = Math.max(160, Math.min(900, (TICK_MS / speed) * 0.4)) * (opts.slow || 1);
    fx.particles.push({ pts, color, t0: now, dur, size: opts.size || 4.5 });
    fx.eyeTarget = pts[pts.length - 1];
  }
  function glow(name, color, now, ms = 700) { fx.glows[name] = { color, until: now + ms }; }
  function float(x, y, text, color, now) { fx.floats.push({ x, y, text, color, t0: now }); }
  function aegisToExchange(sym) {
    const ex = exchangeOf(sym); if (!ex) return null;
    const cx = ex.x + ex.w / 2;
    return [{ x: 930, y: 385 }, { x: cx, y: 385 }, { x: cx, y: ex.y }];
  }

  function animate(e, now) {
    fx.pulse = now;
    if (e.kind === "agent_report") {
      const who = AGENT_ALIAS[e.agent]; if (!who) return;
      if (who === "Aegis") { glow("Aegis", e.result && e.result.approved ? C.green : C.red, now); return; }
      const r = e.result || {};
      let color;
      if (who === "Ledgerkeeper") color = r.positions ? C.amber : C.gray;
      else if (who === "Scorekeeper") color = !r.closed ? C.gray : r.pnl >= 0 ? C.green : C.red;
      else color = VOTE_COLOR[r[READING[who]]] || C.gray;
      glow(who, color, now);
      if (ROUTE[who]) travel(center(who), center(ROUTE[who]), color, now);
    } else if (e.kind === "decision") {
      const conf = e.confidence || 0;
      const color = e.action === "buy" ? (conf >= 0.5 ? C.green : conf > 0 ? C.amber : C.gray) : C.gray;
      glow("Sage", color, now);
      travel(center("Sage"), center("Raphael"), color, now);
      if (e.action === "buy") {
        travel(center("Raphael"), center("Aegis"), C.gold, now, { slow: 1.2 });
        glow("Raphael", C.gold, now);
        const ex = exchangeOf(e.symbol);
        if (!e.approved) float(930, 185, `DENIED ${e.symbol}`, C.red, now);
        else if (!e.executed) float(930, 185, `${e.symbol}: low confidence`, C.amber, now);
      }
    } else if (e.kind === "trade_opened") {
      const path = aegisToExchange(e.symbol);
      if (path) travel(center("Aegis"), path, C.gold, now, { slow: 1.8, size: 7 });
      const ex = exchangeOf(e.symbol);
      if (ex) float(ex.x + ex.w / 2, ex.y + 30, `OPEN ${e.size} @ ${e.entry.toFixed(2)}`, C.gold, now);
    } else if (e.kind === "trade_closed") {
      const ex = exchangeOf(e.symbol);
      const tag = { take_profit: "TARGET", stop_loss: "STOP", end_of_day: "BELL" }[e.reason] || "CLOSE";
      if (ex) float(ex.x + ex.w / 2, ex.y + 60, `${tag} ${signed(e.pnl)}`, e.pnl >= 0 ? C.green : C.red, now);
    } else if (e.kind === "tick") {
      if (e.day !== (state.prevBannerDay ?? -1)) {
        fx.banner = { text: `Day ${e.day + 1}`, t0: now };
        state.prevBannerDay = e.day;
      }
    }
  }

  // ---------- playback ----------
  function isLive() { return !audit; }

  function seek(g) {
    state = freshState(); applied = 0; fx = freshFx();
    P = Math.max(0, Math.min(g, groups.length));
    while (applied < events.length && evPos[applied] <= P) apply(events[applied++], state);
    state.prevBannerDay = state.day;
    renderFeed(true);
  }

  let last = performance.now();
  function frame(now) {
    const dt = Math.min(now - last, 100); last = now;
    if (playing && events.length) {
      const lag = groups.length - P;
      const boost = isLive() && lag > 3 ? lag / 3 : 1; // live: don't fall far behind the city
      P = Math.min(P + (dt * speed * boost) / TICK_MS, groups.length);
      let any = false;
      while (applied < events.length && evPos[applied] <= P) {
        const e = events[applied++]; apply(e, state); animate(e, now); any = true;
      }
      if (any) renderFeed(false);
      if (P >= groups.length && !isLive()) setPlaying(false);
    }
    updateHud();
    draw(now);
    requestAnimationFrame(frame);
  }

  function setPlaying(on) {
    playing = on;
    $("b-play").textContent = on ? "Pause" : "Play";
  }

  // ---------- HUD + side panels ----------
  let feedShown = null;
  function renderFeed(force) {
    if (!force && feedShown === state.feed[0]) return;
    feedShown = state.feed[0];
    const ol = $("feed"); ol.textContent = "";
    for (const f of state.feed.slice(0, 80)) {
      const li = document.createElement("li"); li.className = f.cls || "";
      const t = document.createElement("span"); t.className = "t"; t.textContent = `t${f.tick}`;
      li.append(t, document.createTextNode(f.text)); ol.append(li);
    }
  }

  function setNum(id, v, fmt) {
    const el = $(id); el.textContent = fmt(v);
    el.classList.toggle("pos", v > 0); el.classList.toggle("neg", v < 0);
  }

  let bookShown, scoreShown;
  function renderBooks() {
    const b = state.book, s = state.score;
    if (b === bookShown && s === scoreShown) return;
    bookShown = b; scoreShown = s;
    const pct = (v) => (v == null ? "-" : `${(v * 100).toFixed(0)}%`);
    const val = (v, f) => (v == null ? "-" : f(v));
    const rows = [
      ["Open exposure", b ? `${money(b.exposure)} (${b.exposure_pct}%)` : "-"],
      ["Capital at risk", b ? `${money(b.at_risk)} (${b.at_risk_pct}%)` : "-"],
      ["Win rate", s ? `${pct(s.win_rate)} of ${s.closed}` : "-"],
      ["Avg win / loss", s ? `${val(s.avg_win, money)} / ${val(s.avg_loss, money)}` : "-"],
      ["Profit factor", s ? val(s.profit_factor, (v) => v.toFixed(2)) : "-"],
      ["Loss streak", s ? `${s.loss_streak} now, ${s.max_loss_streak} max` : "-"],
    ];
    const dl = $("books"); dl.textContent = "";
    for (const [k, v] of rows) {
      const dt = document.createElement("dt"); dt.textContent = k;
      const dd = document.createElement("dd"); dd.textContent = v;
      dl.append(dt, dd);
    }
  }

  let ultronShown = null;
  function updateHud() {
    if (!state) return;
    $("h-tick").textContent = state.tick;
    $("h-day").textContent = state.day + 1;
    setNum("h-pnl", state.realized, money);
    const today = state.dayPnl[state.day] || 0;
    setNum("h-today", today, money);
    const bar = $("h-today-bar");
    const frac = Math.min(1, Math.abs(today) / meta.max_daily_loss);
    bar.style.width = (frac * 100).toFixed(1) + "%";
    bar.style.background = today < 0 ? (frac > 0.75 ? C.red : C.amber) : C.green;
    $("h-pos").textContent = `${Object.keys(state.open).length}/${meta.max_open_positions}`;
    $("h-trades").textContent = `${state.trades} (${state.wins}W ${state.losses}L)`;
    const mode = $("mode");
    const market = meta.source === "alpaca" ? "Market" : "Sim";
    mode.textContent = `${market} · ${isLive() ? "Live" : "Replay"}`;
    mode.classList.toggle("live", isLive());

    renderBooks();

    const scrub = $("scrub");
    scrub.max = groups.length;
    if (!dragging) scrub.value = Math.floor(P);
    $("scrub-label").textContent = `tick ${state.tick} / ${groups.length ? groups[groups.length - 1].tick : 0}`;

    // Ultron gives his verdict only once playback reaches the end of a finished run.
    const done = audit && P >= groups.length;
    const key = done ? "done" : `w${Math.floor(applied / 25)}`;
    if (key === ultronShown) return;
    ultronShown = key;
    const v = $("u-verdict"), notes = $("u-notes");
    notes.textContent = "";
    v.className = "verdict";
    if (!done) {
      v.textContent = `Watching: ${applied} events checked`;
      return;
    }
    const s = audit.stats;
    if (audit.ok) { v.textContent = "Clean audit"; v.classList.add("clean"); }
    else { v.textContent = `${audit.violations.length} violation(s)`; v.classList.add("bad"); }
    const add = (text, cls) => { const li = document.createElement("li"); li.textContent = text; if (cls) li.className = cls; notes.append(li); };
    add(`${s.events} events, ${s.opened} opened, ${s.closed} closed, realized ${money(s.realized_pnl)}`);
    audit.violations.forEach((x) => add(`tick ${x.tick ?? "-"}: ${x.message}`, "bad"));
    audit.warnings.forEach((x) => add(`tick ${x.tick}: ${x.message}`, "warn"));
  }

  // ---------- drawing ----------
  let scale = 1;
  function resize() {
    const stage = $("stage");
    const sw = stage.clientWidth, sh = stage.clientHeight;
    scale = Math.max(0.2, Math.min(sw / W, sh / H));
    const dpr = window.devicePixelRatio || 1;
    canvas.style.width = W * scale + "px"; canvas.style.height = H * scale + "px";
    canvas.width = Math.round(W * scale * dpr); canvas.height = Math.round(H * scale * dpr);
    ctx.setTransform(scale * dpr, 0, 0, scale * dpr, 0, 0);
  }

  const lerp = (a, b, t) => a + (b - a) * t;
  function mix(c1, c2, t) { return `rgb(${c1.map((v, i) => Math.round(lerp(v, c2[i], t))).join(",")})`; }

  function dayPhase() {
    if (!state || !state.tick) return 0.25;
    const cpd = meta.cycles_per_day;
    return (((state.tick - 1) % cpd) + (P % 1)) / cpd;
  }

  function draw(now) {
    ctx.clearRect(0, 0, W, H);
    if (!meta || !state) return;
    const ph = dayPhase();
    const light = Math.sin(ph * Math.PI); // 0 at dawn/dusk, 1 at noon
    drawSky(now, ph, light);
    drawRoads(now);
    for (const ex of exchanges()) drawExchange(ex);
    for (const name of Object.keys(PLACES)) drawPlace(name, now, light);
    drawParticles(now);
    drawFloats(now);
    drawBanner(now);
  }

  function drawSky(now, ph, light) {
    ctx.fillStyle = mix([6, 9, 20], [26, 44, 82], light);
    ctx.fillRect(0, 0, W, H);
    ctx.globalAlpha = Math.max(0, 1 - light * 1.6);
    for (const s of stars) {
      ctx.fillStyle = C.white;
      ctx.globalAlpha = Math.max(0, 1 - light * 1.6) * (0.5 + 0.5 * Math.sin(now / 900 + s.tw));
      ctx.beginPath(); ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2); ctx.fill();
    }
    ctx.globalAlpha = 1;
    // sun by day, moon by night, crossing the sky once per city day
    // rises from behind the ground line at dawn, sets behind it at dusk
    const x = 40 + ph * (W - 80), y = 420 - light * 380;
    ctx.fillStyle = "rgba(255,210,120,0.16)";
    ctx.beginPath(); ctx.arc(x, y, 26, 0, Math.PI * 2); ctx.fill();
    // ground
    ctx.fillStyle = mix([8, 12, 24], [16, 26, 48], light);
    ctx.fillRect(0, 395, W, H - 395);
  }

  function road(pts, width = 8) {
    ctx.lineCap = "round"; ctx.lineJoin = "round";
    ctx.strokeStyle = C.road; ctx.lineWidth = width;
    ctx.beginPath(); pts.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y))); ctx.stroke();
    ctx.strokeStyle = C.roadLine; ctx.lineWidth = 1; ctx.setLineDash([6, 8]);
    ctx.stroke(); ctx.setLineDash([]);
  }

  function drawRoads(now) {
    for (const s of ["Scout", "News", "Pulse", "Lens"]) road([center(s), center("Sage")]);
    road([center("Sage"), center("Raphael")], 10);
    road([center("Axiom"), center("Raphael")], 10);
    road([center("Raphael"), center("Aegis")], 12);
    road([center("Ledgerkeeper"), center("Aegis")], 5);
    road([center("Scorekeeper"), center("Aegis")], 5);
    for (const ex of exchanges()) road([center("Aegis"), ...aegisToExchange(ex.sym)], 10);
    // Ultron's line of sight to headquarters
    const flick = Math.max(0, 1 - (now - fx.pulse) / 400);
    ctx.strokeStyle = `rgba(167,139,250,${0.25 + 0.5 * flick})`;
    ctx.lineWidth = 1.5; ctx.setLineDash([3, 6]);
    // passes above Aegis's roof on its way to headquarters
    ctx.beginPath(); ctx.moveTo(1090, 140); ctx.lineTo(730, 210); ctx.stroke(); ctx.setLineDash([]);
  }

  function box(x, y, w, h, r, fill, stroke, lw = 1.5) {
    ctx.beginPath(); ctx.roundRect(x, y, w, h, r);
    ctx.fillStyle = fill; ctx.fill();
    ctx.strokeStyle = stroke; ctx.lineWidth = lw; ctx.stroke();
  }

  function text(t, x, y, size, color, weight = 400, align = "center") {
    ctx.font = `${weight} ${size}px "Segoe UI", system-ui, sans-serif`;
    ctx.fillStyle = color; ctx.textAlign = align; ctx.textBaseline = "middle";
    ctx.fillText(t, x, y);
  }

  function drawWindows(p, light) {
    const alpha = Math.max(0, 0.75 - light);
    if (alpha <= 0.02) return;
    // windows sit below the title and subtitle
    const top = p.y - p.h / 2 + 64;
    const cols = Math.floor((p.w - 20) / 14), rows = Math.floor((p.h - 70) / 10);
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
      if ((r * 7 + c * 3 + p.x) % 5 === 0) continue;
      ctx.fillStyle = `rgba(255,214,140,${alpha * 0.55})`;
      ctx.fillRect(p.x - p.w / 2 + 12 + c * 14, top + r * 10, 7, 5);
    }
  }

  function drawPlace(name, now, light) {
    const p = PLACES[name];
    const g = fx.glows[name];
    const active = g && now < g.until;
    const k = active ? (g.until - now) / 700 : 0;
    const x = p.x - p.w / 2, y = p.y - p.h / 2;
    ctx.save();
    if (active) { ctx.shadowColor = g.color; ctx.shadowBlur = 28 * k; }
    const dim = p.idle || p.stub;
    if (p.kind === "gate") {
      ctx.beginPath();
      ctx.moveTo(x, y); ctx.lineTo(x + p.w, y); ctx.lineTo(x + p.w, y + p.h * 0.55);
      ctx.quadraticCurveTo(x + p.w, y + p.h * 0.85, p.x, y + p.h);
      ctx.quadraticCurveTo(x, y + p.h * 0.85, x, y + p.h * 0.55); ctx.closePath();
      ctx.fillStyle = C.panelHi; ctx.fill();
      ctx.strokeStyle = active ? g.color : C.stroke; ctx.lineWidth = active ? 3 : 1.5; ctx.stroke();
    } else if (p.kind === "tower") {
      box(x + 12, y + 40, p.w - 24, p.h - 40, 4, C.panel, active ? g.color : C.stroke);
      box(x, y, p.w, 50, 10, C.panelHi, C.violet, 1.5);
    } else {
      box(x, y, p.w, p.h, p.kind === "squad" ? 8 : 10, p.kind === "hq" ? C.panelHi : C.panel,
          active ? g.color : (p.kind === "hq" ? C.gold : C.stroke), active ? 3 : (p.kind === "hq" ? 2 : 1.5));
    }
    ctx.restore();
    if (p.kind === "hq") drawWindows(p, light);

    const titleColor = dim ? C.muted : C.text;
    if (p.kind === "tower") {
      drawUltronEye(p, now);
      text(p.title, p.x, y + p.h + 14, 13, C.violet, 600);
      text(p.sub, p.x, y + p.h + 30, 11, C.muted);
      return;
    }
    const ty = p.kind === "gate" ? p.y - 14 : p.y - (p.h > 60 ? 12 : 8);
    text(p.title, p.x, ty, p.kind === "squad" ? 13 : 16, titleColor, 600);
    let sub = p.sub;
    if (p.stub) sub += " (stub)";
    text(sub, p.x, ty + 18, 11, C.muted);
  }

  function drawUltronEye(p, now) {
    const cx = p.x, cy = p.y - p.h / 2 + 25;
    const done = audit && P >= groups.length;
    const iris = done ? (audit.ok ? C.green : C.red) : C.violet;
    ctx.fillStyle = "#0a0f1d";
    ctx.beginPath(); ctx.ellipse(cx, cy, 24, 14, 0, 0, Math.PI * 2); ctx.fill();
    const t = fx.eyeTarget || { x: cx, y: cy + 100 };
    const a = Math.atan2(t.y - cy, t.x - cx);
    const px = cx + Math.cos(a) * 9, py = cy + Math.sin(a) * 5;
    ctx.save(); ctx.shadowColor = iris; ctx.shadowBlur = 14;
    ctx.fillStyle = iris; ctx.beginPath(); ctx.arc(px, py, 7, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
    ctx.fillStyle = "#05070e"; ctx.beginPath(); ctx.arc(px, py, 3, 0, Math.PI * 2); ctx.fill();
  }

  function drawExchange(ex) {
    const { sym, x, y, w, h } = ex;
    box(x, y, w, h, 12, C.panel, C.stroke);
    const prices = (state.prices[sym] || []).slice(-SPARK_POINTS);
    const lastP = prices[prices.length - 1];
    const firstP = (state.prices[sym] || [])[0];
    text(sym, x + 16, y + 22, 16, C.text, 700, "left");
    if (lastP != null) {
      const ch = firstP ? (lastP / firstP - 1) * 100 : 0;
      text(lastP.toFixed(2), x + w - 16, y + 18, 15, C.text, 600, "right");
      text(`${ch >= 0 ? "+" : ""}${ch.toFixed(2)}% this run`, x + w - 16, y + 36, 11, ch >= 0 ? C.green : C.red, 400, "right");
    }
    const pos = Object.values(state.open).find((t) => t.symbol === sym);
    const dec = state.decisions[sym];
    const status = pos ? `holding ${pos.size} @ ${pos.entry.toFixed(2)}` :
      dec ? (dec.action === "buy" ? (dec.executed ? "bought" : "buy blocked") : "waiting for a setup") : "waiting";
    text(status, x + 16, y + 42, 11, pos ? C.gold : C.muted, 400, "left");

    const gx = x + 14, gy = y + 60, gw = w - 28 - (pos ? 54 : 0), gh = h - 76;
    if (prices.length < 2) { text("waiting for prices", x + w / 2, gy + gh / 2, 12, C.muted); return; }
    let lo = Math.min(...prices), hi = Math.max(...prices);
    let target = null;
    if (pos) {
      target = pos.entry + (pos.entry - pos.stop_loss) * meta.take_profit_rr;
      lo = Math.min(lo, pos.stop_loss); hi = Math.max(hi, target);
    }
    const pad = (hi - lo) * 0.08 || 1; lo -= pad; hi += pad;
    const Y = (v) => gy + gh - ((v - lo) / (hi - lo)) * gh;
    const X = (i) => gx + (i / (SPARK_POINTS - 1)) * gw;

    ctx.strokeStyle = "#1a2643"; ctx.lineWidth = 1;
    for (let i = 0; i <= 3; i++) { const yy = gy + (gh * i) / 3; ctx.beginPath(); ctx.moveTo(gx, yy); ctx.lineTo(gx + gw, yy); ctx.stroke(); }

    if (pos) {
      const level = (v, color, label, dash) => {
        ctx.strokeStyle = color; ctx.lineWidth = 1.2; ctx.setLineDash(dash);
        ctx.beginPath(); ctx.moveTo(gx, Y(v)); ctx.lineTo(gx + gw, Y(v)); ctx.stroke(); ctx.setLineDash([]);
        text(label, gx + gw + 6, Y(v), 10, color, 600, "left");
      };
      ctx.fillStyle = "rgba(76,212,151,0.07)"; ctx.fillRect(gx, Y(target), gw, Y(pos.entry) - Y(target));
      ctx.fillStyle = "rgba(255,107,107,0.08)"; ctx.fillRect(gx, Y(pos.entry), gw, Y(pos.stop_loss) - Y(pos.entry));
      level(target, C.green, "target", [4, 4]);
      level(pos.entry, C.white, "entry", [2, 3]);
      level(pos.stop_loss, C.red, "stop", [4, 4]);
    }

    const up = prices[prices.length - 1] >= prices[0];
    ctx.strokeStyle = up ? C.green : C.red; ctx.lineWidth = 2;
    ctx.beginPath(); prices.forEach((v, i) => (i ? ctx.lineTo(X(i), Y(v)) : ctx.moveTo(X(i), Y(v)))); ctx.stroke();
    const li = prices.length - 1;
    ctx.save(); ctx.shadowColor = pos ? C.gold : C.white; ctx.shadowBlur = 10;
    ctx.fillStyle = pos ? C.gold : C.white;
    ctx.beginPath(); ctx.arc(X(li), Y(prices[li]), 4, 0, Math.PI * 2); ctx.fill(); ctx.restore();
  }

  function pointOn(pts, t) {
    const segs = []; let total = 0;
    for (let i = 1; i < pts.length; i++) { const d = Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y); segs.push(d); total += d; }
    let dist = t * total;
    for (let i = 0; i < segs.length; i++) {
      if (dist <= segs[i] || i === segs.length - 1) {
        const f = segs[i] ? Math.min(1, dist / segs[i]) : 1;
        return { x: lerp(pts[i].x, pts[i + 1].x, f), y: lerp(pts[i].y, pts[i + 1].y, f) };
      }
      dist -= segs[i];
    }
    return pts[pts.length - 1];
  }

  function drawParticles(now) {
    fx.particles = fx.particles.filter((p) => now - p.t0 < p.dur);
    for (const p of fx.particles) {
      const t = (now - p.t0) / p.dur;
      const e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
      ctx.save(); ctx.shadowColor = p.color; ctx.shadowBlur = 16; ctx.fillStyle = p.color;
      for (let k = 3; k >= 0; k--) {
        const q = pointOn(p.pts, Math.max(0, e - k * 0.04));
        ctx.globalAlpha = k ? 0.18 * (4 - k) : 1;
        ctx.beginPath(); ctx.arc(q.x, q.y, p.size * (k ? 0.7 : 1), 0, Math.PI * 2); ctx.fill();
      }
      ctx.restore();
    }
  }

  function drawFloats(now) {
    const LIFE = 1800;
    fx.floats = fx.floats.filter((f) => now - f.t0 < LIFE);
    for (const f of fx.floats) {
      const t = (now - f.t0) / LIFE;
      ctx.globalAlpha = 1 - t * t;
      text(f.text, f.x, f.y - t * 34, 14, f.color, 700);
    }
    ctx.globalAlpha = 1;
  }

  function drawBanner(now) {
    if (!fx.banner) return;
    const t = (now - fx.banner.t0) / 2200;
    if (t >= 1) { fx.banner = null; return; }
    ctx.globalAlpha = Math.sin(t * Math.PI) * 0.9;
    text(fx.banner.text, W / 2, 395, 44, C.white, 700);
    ctx.globalAlpha = 1;
  }

  // ---------- loading + live follow ----------
  async function getText(url) {
    const r = await fetch(url, { cache: "no-store" });
    return r.ok ? r.text() : null;
  }
  async function getJSON(url) {
    const t = await getText(url);
    try { return t ? JSON.parse(t) : null; } catch { return null; }
  }

  function resetRun(m) {
    meta = { ...DEFAULT_META, ...m };
    runId = meta.run_id; audit = null; events = []; groups = []; evPos = [];
    state = freshState(); applied = 0; P = 0; fx = freshFx(); feedShown = null; ultronShown = null;
    bookShown = scoreShown = undefined;
    renderFeed(true); setPlaying(true);
  }

  async function poll() {
    try {
      const text = await getText("/run/events.jsonl");
      $("empty").hidden = text != null;
      if (text != null) {
        let m = await getJSON("/run/meta.json");
        if (!m) { // runs from before meta.json existed: infer what we can
          const firstTick = text.split("\n").find((l) => l.includes('"kind": "tick"'));
          m = { run_id: "legacy", watchlist: firstTick ? Object.keys(JSON.parse(firstTick).prices) : [] };
        }
        if (m.run_id !== runId) resetRun(m);
        const lines = text.split("\n").filter(Boolean);
        if (lines.length > events.length) {
          for (const l of lines.slice(events.length)) {
            try { events.push(JSON.parse(l)); } catch { break; } // partial last line: retry next poll
          }
          indexEvents();
        }
        if (!audit) audit = await getJSON("/run/audit.json");
      }
    } catch (err) {
      console.warn("poll failed", err);
    } finally {
      setTimeout(poll, audit ? 2500 : 700);
    }
  }

  // ---------- controls ----------
  $("b-play").addEventListener("click", () => {
    if (!playing && P >= groups.length && !isLive()) seek(0);
    setPlaying(!playing);
  });
  $("b-step").addEventListener("click", () => { setPlaying(false); stepTick(); });
  $("speed").addEventListener("change", (e) => (speed = parseFloat(e.target.value)));
  const scrub = $("scrub");
  scrub.addEventListener("input", () => { dragging = true; seek(parseInt(scrub.value, 10)); });
  scrub.addEventListener("change", () => (dragging = false));
  window.addEventListener("keydown", (e) => {
    if (e.target.tagName === "SELECT" || e.target.tagName === "INPUT") return;
    if (e.code === "Space") { e.preventDefault(); $("b-play").click(); }
    if (e.code === "ArrowRight") { e.preventDefault(); $("b-step").click(); }
  });

  function stepTick() {
    const target = Math.min(Math.floor(P) + 1, groups.length);
    const now = performance.now();
    P = target;
    while (applied < events.length && evPos[applied] <= P) { const e = events[applied++]; apply(e, state); animate(e, now); }
    renderFeed(false);
  }

  new ResizeObserver(resize).observe($("stage")); // also catches layout changes, not just window resizes
  resize();
  poll();
  requestAnimationFrame(frame);
})();
