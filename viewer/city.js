// Zombiso AI City viewer: replays a run's events.jsonl as a living 2D city.
// State comes only from events (apply); animation is a separate layer (animate),
// so scrubbing can rebuild state instantly without replaying effects.
(() => {
  "use strict";

  const W = 1200, H = 720;
  const TICK_MS = 1400;            // one city tick at 1x speed
  const SPARK_POINTS = 60;         // price history shown per exchange
  const FLOAT_LIFE = 1800;         // ms a floating label stays up
  const canvas = document.getElementById("city");
  const ctx = canvas.getContext("2d");
  const $ = (id) => document.getElementById(id);

  // Cyber palette: near-black blues lit by neon.
  const C = {
    road: "#071026", panel: "rgba(6,12,30,0.88)", panelHi: "rgba(10,20,48,0.92)",
    stroke: "#1d3666", text: "#dff8ff", muted: "#6f88bd", gold: "#ffcf4a",
    green: "#2bffa3", red: "#ff3d6e", amber: "#ffb020", violet: "#b56bff", gray: "#5b6d96",
    white: "#ecfbff", cyan: "#00e5ff", magenta: "#ff2bd6",
  };
  // Each kind of building has its own neon.
  const NEON = { squad: C.cyan, commander: C.magenta, hq: C.gold, gate: C.cyan, tower: C.violet, bank: C.gold };
  const TITLE_FONT = '"Orbitron", "Segoe UI", system-ui, sans-serif';
  const MONO_FONT = '"Share Tech Mono", "Consolas", monospace';

  // ---------- the city map (logical 1200x720) ----------
  const PLACES = {
    Scout:        { x: 150,  y: 95,  w: 96,  h: 52, title: "Scout", sub: "trend", kind: "squad" },
    News:         { x: 260,  y: 95,  w: 96,  h: 52, title: "News", sub: "headlines", kind: "squad" },
    Pulse:        { x: 370,  y: 95,  w: 96,  h: 52, title: "Pulse", sub: "crowd mood", kind: "squad" },
    Lens:         { x: 480,  y: 95,  w: 96,  h: 52, title: "Lens", sub: "patterns", kind: "squad" },
    Sage:         { x: 315,  y: 228, w: 140, h: 66, title: "Sage", sub: "weighs signals", kind: "commander" },
    Axiom:        { x: 640,  y: 95,  w: 150, h: 56, title: "Axiom", sub: "strategist", kind: "commander" },
    Raphael:      { x: 640,  y: 245, w: 180, h: 92, title: "Raphael", sub: "headquarters", kind: "hq" },
    Aegis:        { x: 930,  y: 245, w: 130, h: 92, title: "Aegis", sub: "risk gate", kind: "gate" },
    Ledgerkeeper: { x: 870,  y: 95,  w: 110, h: 52, title: "Ledgerkeeper", sub: "exposure", kind: "squad" },
    Scorekeeper:  { x: 995,  y: 95,  w: 110, h: 52, title: "Scorekeeper", sub: "win rate", kind: "squad" },
    Ultron:       { x: 1125, y: 200, w: 70,  h: 170, title: "Ultron", sub: "auditor", kind: "tower" },
    Vault:        { x: 110,  y: 300, w: 130, h: 64, title: "Treasury", sub: "the vault", kind: "bank" },
    Research:     { x: 110,  y: 205, w: 120, h: 52, title: "Research", sub: "bureau", kind: "squad" },
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
  // Who gets scored on the survival board, and how their reading votes (same as core/trial.py).
  const VOTERS = {
    MarketResearch: ["Scout", "trend", { up: "buy", down: "sell" }],
    Sentiment: ["Pulse", "crowd_mood", { bullish: "buy", bearish: "sell" }],
    Charts: ["Lens", "pattern", { breakout: "buy", breakdown: "sell" }],
    NewsResearch: ["News", "sentiment", { positive: "buy", negative: "sell" }],
  };
  const SCORED = ["Scout", "Pulse", "Lens", "News", "Axiom"];
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
  const skyline = makeSkyline();  // distant towers behind the city, generated once
  let mode3d = false;  // 3D view on? (renderer lives in viewer/city3d.js)

  function freshFx() { return { particles: [], glows: {}, floats: [], banner: null, eyeTarget: null, pulse: 0 }; }

  function makeStars() {
    const s = []; let seed = 7;
    const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    for (let i = 0; i < 90; i++) s.push({ x: rnd() * W, y: rnd() * 380, r: rnd() * 1.4 + 0.3, tw: rnd() * 6 });
    return s;
  }

  function makeSkyline() {
    const towers = []; let seed = 42;
    const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    for (let x = -10; x < W + 10;) {
      const w = 18 + rnd() * 46, h = 50 + rnd() * rnd() * 230;
      towers.push({ x, w, h, neon: rnd() < 0.5 ? C.cyan : rnd() < 0.5 ? C.magenta : C.violet,
                    lit: Array.from({ length: Math.floor(h / 9) * Math.floor(w / 8) }, () => rnd() < 0.22),
                    blink: rnd() * 6 });
      x += w + 2 + rnd() * 8;
    }
    return towers;
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
             wins: 0, losses: 0, decisions: {}, feed: [], seenDay: -1, book: null, score: null,
             startEquity: meta.start_equity || meta.account_size || 10000,
             briefing: null, newsSeen: {},
             // live agent scoring for this run: readings this tick, votes per open trade, results
             reports: {}, votes: {}, live: Object.fromEntries(SCORED.map((n) => [n, { right: 0, wrong: 0 }])) };
  }

  const amount = (v) => Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const money = (v) => (v < 0 ? "-$" : "$") + amount(v);
  const signed = (v) => (v >= 0 ? "+" : "-") + "$" + amount(v);

  function pushFeed(s, tick, text, cls) {
    s.feed.unshift({ tick, text, cls });
    if (s.feed.length > 200) s.feed.pop();
  }

  // ---------- state: pure replay of one event ----------
  function apply(e, s) {
    switch (e.kind) {
      case "treasury":
        s.startEquity = e.equity;
        break;
      case "briefing": {
        s.briefing = e;
        const biases = Object.entries(e.bias || {}).map(([k, v]) => `${k} ${v}`).join(", ");
        pushFeed(s, e.tick, e.status === "active" ? `Research briefing: ${biases}` : "No research briefing today", "day");
        break;
      }
      case "agent_report":
        if (VOTERS[e.agent]) s.reports[`${e.symbol}|${e.agent}`] = e.result || {};
        if (e.agent === "PortfolioManager") s.book = e.result;
        if (e.agent === "PerformanceAnalyst") s.score = e.result;
        if (e.agent === "NewsResearch" && e.result && e.result.status === "active"
            && s.newsSeen[e.symbol] !== e.result.top) {
          s.newsSeen[e.symbol] = e.result.top;
          pushFeed(s, e.tick, `News ${e.symbol} ${e.result.sentiment}: ${e.result.top}`,
                   e.result.sentiment === "negative" ? "loss" : e.result.sentiment === "positive" ? "win" : "");
        }
        break;
      case "tick":
        s.reports = {};
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
      case "trade_opened": {
        const v = { Axiom: "buy" };
        for (const [agent, [name, field, rule]] of Object.entries(VOTERS)) {
          const vote = rule[(s.reports[`${e.symbol}|${agent}`] || {})[field]];
          if (vote) v[name] = vote;
        }
        s.votes[e.trade_id] = v;
        s.open[e.trade_id] = e; s.trades++;
        pushFeed(s, e.tick, `Opened #${e.trade_id} ${e.symbol}: ${e.size} @ ${e.entry.toFixed(2)}, stop ${e.stop_loss.toFixed(2)}`, "open");
        break;
      }
      case "trade_closed": {
        delete s.open[e.trade_id];
        for (const [name, vote] of Object.entries(s.votes[e.trade_id] || {})) {
          const right = vote === "buy" ? e.pnl > 0 : e.pnl <= 0;
          s.live[name][right ? "right" : "wrong"]++;
        }
        delete s.votes[e.trade_id];
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

  function vaultPath(ex) {
    const cx = ex.x + ex.w / 2, v = PLACES.Vault;
    return [{ x: cx, y: 385 }, { x: v.x, y: 385 }, { x: v.x, y: v.y + v.h / 2 }];
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
    } else if (e.kind === "briefing") {
      glow("Research", e.status === "active" ? C.violet : C.gray, now, 1500);
      travel(center("Research"), center("Sage"), C.violet, now, { slow: 2, size: 6 });
    } else if (e.kind === "trade_opened") {
      const path = aegisToExchange(e.symbol);
      if (path) travel(center("Aegis"), path, C.gold, now, { slow: 1.8, size: 7 });
      glow(`ex:${e.symbol}`, C.gold, now, 1200);
      const ex = exchangeOf(e.symbol);
      if (ex) float(ex.x + ex.w / 2, ex.y + 30, `OPEN ${e.size} @ ${e.entry.toFixed(2)}`, C.gold, now);
    } else if (e.kind === "trade_closed") {
      const ex = exchangeOf(e.symbol);
      const tag = { take_profit: "TARGET", stop_loss: "STOP", end_of_day: "BELL" }[e.reason] || "CLOSE";
      const color = e.pnl >= 0 ? C.green : C.red;
      if (ex) {
        float(ex.x + ex.w / 2, ex.y + 60, `${tag} ${signed(e.pnl)}`, color, now);
        travel({ x: ex.x + ex.w / 2, y: ex.y }, vaultPath(ex), color, now, { slow: 1.6, size: 6 });
      }
      glow("Vault", color, now, 1200);
      glow(`ex:${e.symbol}`, color, now, 1200);
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

  // ---------- survival board ----------
  let trialScores = null;  // finished trial days, from /trial/scores.json

  // An agent's record: finished trial days (market runs only) plus this run so far.
  function survival(name) {
    const min = { votes: trialScores ? trialScores.min_votes : 10, acc: trialScores ? trialScores.min_accuracy : 50 };
    let right = state.live[name].right, wrong = state.live[name].wrong;
    const inTrial = trialScores && meta.source === "alpaca";
    if (inTrial) {
      const past = trialScores.agents[name] || { right: 0, wrong: 0 };
      if (trialScores.runs.includes(runId)) { right = 0; wrong = 0; }  // today already counted
      right += past.right; wrong += past.wrong;
    }
    const votes = right + wrong, acc = votes ? Math.round((right / votes) * 100) : null;
    const status = votes < min.votes ? "early" : acc < min.acc ? "dying" : acc < min.acc + 10 ? "risk" : "safe";
    return { right, votes, acc, status, inTrial };
  }
  const STATUS = {
    safe: ["Safe", C.green], risk: ["At risk", C.amber], dying: ["Dying", C.red], early: ["Too early", C.gray],
  };

  let boardShown = "";
  function renderBoard() {
    const rows = SCORED.map((n) => ({ name: n, ...survival(n) }))
      .sort((a, b) => (b.acc ?? -1) - (a.acc ?? -1));
    const key = JSON.stringify(rows);
    if (key === boardShown) return;
    boardShown = key;
    const first = rows[0];
    $("board-title").textContent = first.inTrial
      ? `Survival board · trial day ${Math.min(trialScores.days_done + (trialScores.runs.includes(runId) ? 0 : 1), trialScores.days_total)} of ${trialScores.days_total}`
      : "Survival board · this practice run";
    const ol = $("board"); ol.textContent = "";
    for (const r of rows) {
      const [label, color] = STATUS[r.status];
      const li = document.createElement("li");
      li.className = `agent ${r.status}`;
      li.innerHTML = `<span class="who"></span><span class="bar"><i></i></span><span class="score"></span><span class="tag"></span>`;
      li.querySelector(".who").textContent = (r.status === "dying" ? "☠ " : "") + r.name;
      li.querySelector(".bar i").style.width = `${r.acc ?? 0}%`;
      li.querySelector(".bar i").style.background = color;
      li.querySelector(".score").textContent = r.votes ? `${r.acc}% · ${r.right}/${r.votes}` : "no votes yet";
      const tag = li.querySelector(".tag");
      tag.textContent = label; tag.style.color = color;
      ol.append(li);
    }
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

  let briefingShown;
  function renderBriefing() {
    const b = state.briefing;
    if (b === briefingShown) return;
    briefingShown = b;
    const section = $("briefing-section");
    section.hidden = !b;
    if (!b) return;
    $("briefing-summary").textContent = b.status === "active" ? b.summary : "No briefing today (Claude unavailable).";
    const ul = $("briefing-list"); ul.textContent = "";
    for (const row of b.symbols || []) {
      const li = document.createElement("li");
      const tag = document.createElement("b");
      tag.textContent = `${row.symbol} ${row.bias}`;
      tag.className = row.bias === "bullish" ? "pos" : row.bias === "bearish" ? "neg" : "";
      li.append(tag, document.createTextNode(`: ${row.levels}`));
      ul.append(li);
    }
  }

  let ultronShown = null;
  function updateHud() {
    if (!state) return;
    $("h-tick").textContent = state.tick;
    $("h-day").textContent = state.day + 1;
    setNum("h-pnl", state.realized, money);
    $("h-equity").textContent = "$" + (state.startEquity + state.realized)
      .toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const today = state.dayPnl[state.day] || 0;
    setNum("h-today", today, money);
    const bar = $("h-today-bar");
    const frac = Math.min(1, Math.abs(today) / meta.max_daily_loss);
    bar.style.width = (frac * 100).toFixed(1) + "%";
    bar.style.background = today < 0 ? (frac > 0.75 ? C.red : C.amber) : C.green;
    $("h-pos").textContent = `${Object.keys(state.open).length}/${meta.max_open_positions}`;
    $("h-trades").textContent = `${state.trades} (${state.wins}W ${state.losses}L)`;
    $("b-report").hidden = !audit;  // the report is written when the run finishes
    const mode = $("mode");
    const market = meta.source === "alpaca" ? "Market" : "Sim";
    mode.textContent = `${market} · ${isLive() ? "Live" : "Replay"}`;
    mode.classList.toggle("live", isLive());

    renderBooks();
    renderBriefing();
    renderBoard();

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

  function pruneFx(now) {
    fx.particles = fx.particles.filter((p) => now - p.t0 < p.dur);
    fx.floats = fx.floats.filter((f) => now - f.t0 < FLOAT_LIFE);
  }

  function draw(now) {
    pruneFx(now);
    if (mode3d) {
      const r3 = current3d();
      if (r3 && state) r3.render(now);
      return;
    }
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

  const HORIZON = 395;  // where the city's floor meets the sky

  function drawSky(now, ph, light) {
    // Always night in a cyber city; daytime only warms the sky toward a violet dusk.
    const sky = ctx.createLinearGradient(0, 0, 0, HORIZON);
    sky.addColorStop(0, mix([2, 4, 14], [10, 6, 30], light));
    sky.addColorStop(1, mix([16, 10, 44], [52, 18, 78], light));
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, W, HORIZON);
    for (const s of stars) {
      ctx.globalAlpha = (0.35 + 0.35 * Math.sin(now / 900 + s.tw)) * (1 - light * 0.6);
      ctx.fillStyle = C.white;
      ctx.fillRect(s.x, s.y * 0.7, s.r, s.r);
    }
    ctx.globalAlpha = 1;

    // distant skyline: dark towers, scattered lit windows, a neon tip on each
    for (const t of skyline) {
      const top = HORIZON - t.h;
      ctx.fillStyle = "#060b1d";
      ctx.fillRect(t.x, top, t.w, t.h);
      const cols = Math.floor(t.w / 8);
      t.lit.forEach((on, i) => {
        if (!on) return;
        const c = i % cols, r = Math.floor(i / cols);
        ctx.fillStyle = (i + Math.floor(now / 1700 + t.blink)) % 9 === 0 ? "rgba(255,43,214,.55)" : "rgba(0,229,255,.32)";
        ctx.fillRect(t.x + 3 + c * 8, top + 6 + r * 9, 3, 2);
      });
      ctx.fillStyle = t.neon;
      ctx.globalAlpha = 0.55 + 0.45 * Math.sin(now / 700 + t.blink);
      ctx.fillRect(t.x, top, t.w, 1.5);
      ctx.globalAlpha = 1;
    }

    // horizon glow
    const glow = ctx.createLinearGradient(0, HORIZON - 60, 0, HORIZON + 30);
    glow.addColorStop(0, "rgba(255,43,214,0)");
    glow.addColorStop(0.7, "rgba(255,43,214,.22)");
    glow.addColorStop(1, "rgba(0,229,255,.05)");
    ctx.fillStyle = glow;
    ctx.fillRect(0, HORIZON - 60, W, 90);

    // floor: a neon perspective grid scrolling toward the viewer
    ctx.fillStyle = "#03060f";
    ctx.fillRect(0, HORIZON, W, H - HORIZON);
    ctx.save();
    ctx.beginPath(); ctx.rect(0, HORIZON, W, H - HORIZON); ctx.clip();
    ctx.strokeStyle = "rgba(0,229,255,.22)"; ctx.lineWidth = 1;
    const vx = W / 2;
    for (let i = -24; i <= 24; i++) {  // rays from the vanishing point
      ctx.beginPath(); ctx.moveTo(vx + i * 6, HORIZON); ctx.lineTo(vx + i * 110, H); ctx.stroke();
    }
    const scroll = (now / 4000) % 1;
    for (let k = 0; k < 14; k++) {  // horizontal lines, bunching up toward the horizon
      const d = (k + scroll) / 14;
      const y = HORIZON + (H - HORIZON) * d * d;
      ctx.globalAlpha = 0.15 + 0.6 * d;
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    }
    ctx.restore();
    ctx.globalAlpha = 1;
  }

  // A road is a dark conduit with a thin neon core and energy pulses flowing along it.
  function road(pts, width, now) {
    ctx.lineCap = "round"; ctx.lineJoin = "round";
    ctx.beginPath(); pts.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)));
    ctx.strokeStyle = C.road; ctx.lineWidth = width;
    ctx.stroke();
    ctx.save();
    ctx.shadowColor = C.cyan; ctx.shadowBlur = 6;
    ctx.strokeStyle = "rgba(0,229,255,.28)"; ctx.lineWidth = 1;
    ctx.stroke();
    ctx.strokeStyle = "rgba(0,229,255,.85)"; ctx.lineWidth = 1.6;
    ctx.setLineDash([2, 22]); ctx.lineDashOffset = -now / 35;
    ctx.stroke();
    ctx.restore();
  }

  // Every road as [points, width]; shared by the 2D and 3D views.
  function roadPaths() {
    const roads = ["Scout", "News", "Pulse", "Lens", "Research"].map((s) => [[center(s), center("Sage")], 8]);
    roads.push([[center("Sage"), center("Raphael")], 10], [[center("Axiom"), center("Raphael")], 10],
               [[center("Raphael"), center("Aegis")], 12],
               [[center("Ledgerkeeper"), center("Aegis")], 5], [[center("Scorekeeper"), center("Aegis")], 5]);
    const first = exchanges()[0];  // the vault joins the exchange road at the first exchange
    if (first) roads.push([[center("Vault"), { x: PLACES.Vault.x, y: 385 }, { x: first.x + first.w / 2, y: 385 }], 8]);
    for (const ex of exchanges()) roads.push([[center("Aegis"), ...aegisToExchange(ex.sym)], 10]);
    return roads;
  }

  function drawRoads(now) {
    for (const [pts, width] of roadPaths()) road(pts, width, now);
    // Ultron's scanning beam to headquarters, passing above Aegis's roof
    const flick = Math.max(0, 1 - (now - fx.pulse) / 400);
    ctx.save();
    ctx.shadowColor = C.violet; ctx.shadowBlur = 10;
    ctx.strokeStyle = `rgba(181,107,255,${0.3 + 0.5 * flick})`;
    ctx.lineWidth = 1.5; ctx.setLineDash([3, 6]); ctx.lineDashOffset = now / 60;
    ctx.beginPath(); ctx.moveTo(1090, 140); ctx.lineTo(730, 210); ctx.stroke();
    ctx.restore();
  }

  // Stroke the current path in neon: a soft glow plus a crisp core line.
  function neonStroke(color, amt = 0.6, width = 1.4) {
    ctx.save();
    ctx.shadowColor = color; ctx.shadowBlur = 6 + 16 * amt;
    ctx.strokeStyle = color; ctx.lineWidth = width; ctx.globalAlpha = Math.min(1, 0.45 + amt * 0.6);
    ctx.stroke();
    ctx.restore();
  }

  // A holographic panel: dark glass, neon edge, HUD brackets on the corners.
  function panel(x, y, w, h, color, amt, fill = C.panel) {
    ctx.beginPath(); ctx.rect(x, y, w, h);
    ctx.fillStyle = fill; ctx.fill();
    neonStroke(color, amt * 0.7, 1);
    const L = Math.min(10, w / 5, h / 4);
    ctx.beginPath();
    for (const [cx, cy, dx, dy] of [[x, y, 1, 1], [x + w, y, -1, 1], [x, y + h, 1, -1], [x + w, y + h, -1, -1]]) {
      ctx.moveTo(cx + dx * L, cy); ctx.lineTo(cx, cy); ctx.lineTo(cx, cy + dy * L);
    }
    neonStroke(color, amt, 2);
    // faint top highlight, like light catching glass
    ctx.fillStyle = "rgba(255,255,255,.04)";
    ctx.fillRect(x + 1, y + 1, w - 2, Math.min(10, h / 4));
  }

  // maxWidth squeezes text that would not fit (e.g. long names on small buildings).
  function text(t, x, y, size, color, weight = 400, align = "center", family = MONO_FONT, glow = 0, maxWidth) {
    ctx.font = `${weight} ${size}px ${family}`;
    ctx.fillStyle = color; ctx.textAlign = align; ctx.textBaseline = "middle";
    if (glow) { ctx.save(); ctx.shadowColor = color; ctx.shadowBlur = glow; }
    if (maxWidth) ctx.fillText(t, x, y, maxWidth); else ctx.fillText(t, x, y);
    if (glow) ctx.restore();
  }

  function title(t, x, y, size, color, glow = 8, maxWidth) {
    ctx.letterSpacing = "1.5px";
    text(t.toUpperCase(), x, y, size, color, 700, "center", TITLE_FONT, glow, maxWidth);
    ctx.letterSpacing = "0px";
  }

  // Headquarters' windows: a grid of flickering neon lights.
  function drawWindows(p, now) {
    const top = p.y - p.h / 2 + 62;
    const cols = Math.floor((p.w - 20) / 14), rows = Math.floor((p.h - 68) / 9);
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
      const seed = r * 7 + c * 3;
      if (seed % 5 === 0) continue;
      const on = (seed + Math.floor(now / 900)) % 11 !== 0;
      ctx.fillStyle = on ? (seed % 4 ? "rgba(255,207,74,.7)" : "rgba(0,229,255,.7)") : "rgba(255,255,255,.06)";
      ctx.fillRect(p.x - p.w / 2 + 12 + c * 14, top + r * 9, 8, 3);
    }
  }

  function drawPlace(name, now) {
    const p = PLACES[name];
    const g = fx.glows[name];
    const active = g && now < g.until;
    const k = active ? Math.min(1, (g.until - now) / 700) : 0;
    const neon = active ? g.color : NEON[p.kind];
    const amt = active ? 0.7 + k : 0.45 + 0.12 * Math.sin(now / 900 + p.x);  // idle buildings breathe
    const x = p.x - p.w / 2, y = p.y - p.h / 2;

    if (p.kind === "gate") {  // Aegis: an energy shield
      ctx.beginPath();
      ctx.moveTo(x, y); ctx.lineTo(x + p.w, y); ctx.lineTo(x + p.w, y + p.h * 0.55);
      ctx.quadraticCurveTo(x + p.w, y + p.h * 0.85, p.x, y + p.h);
      ctx.quadraticCurveTo(x, y + p.h * 0.85, x, y + p.h * 0.55); ctx.closePath();
      ctx.fillStyle = C.panelHi; ctx.fill();
      neonStroke(neon, amt, 2);
      ctx.save(); ctx.clip();  // a hex-like scan sweeping down the shield
      const sy = y + ((now / 18) % (p.h + 20)) - 10;
      ctx.fillStyle = "rgba(0,229,255,.10)"; ctx.fillRect(x, sy, p.w, 6);
      ctx.restore();
    } else if (p.kind === "tower") {  // Ultron: a spire with an eye on top
      ctx.beginPath();
      ctx.moveTo(p.x - 10, y + p.h); ctx.lineTo(p.x - 6, y + 46); ctx.lineTo(p.x + 6, y + 46); ctx.lineTo(p.x + 10, y + p.h);
      ctx.closePath(); ctx.fillStyle = C.panel; ctx.fill(); neonStroke(neon, amt, 1.4);
      for (let i = 0; i < 6; i++) {  // energy rising up the spire
        const ry = y + p.h - ((now / 12 + i * 22) % (p.h - 46));
        ctx.fillStyle = "rgba(181,107,255,.6)"; ctx.fillRect(p.x - 4, ry, 8, 1.5);
      }
      ctx.beginPath(); ctx.ellipse(p.x, y + 25, p.w / 2, 22, 0, 0, Math.PI * 2);
      ctx.fillStyle = C.panelHi; ctx.fill(); neonStroke(C.violet, amt, 1.6);
    } else if (p.kind === "bank") {  // Treasury: a neon temple
      ctx.beginPath();
      ctx.moveTo(x - 6, y + 14); ctx.lineTo(p.x, y - 10); ctx.lineTo(x + p.w + 6, y + 14); ctx.closePath();
      ctx.fillStyle = C.panelHi; ctx.fill(); neonStroke(neon, amt, 1.6);
      panel(x, y + 14, p.w, p.h - 14, neon, amt);
      ctx.beginPath();
      for (let i = 1; i < 5; i++) { const cx = x + (p.w / 5) * i; ctx.moveTo(cx, y + 18); ctx.lineTo(cx, y + p.h - 4); }
      ctx.strokeStyle = "rgba(255,207,74,.18)"; ctx.lineWidth = 3; ctx.stroke();
    } else {
      panel(x, y, p.w, p.h, neon, amt, p.kind === "hq" ? C.panelHi : C.panel);
    }

    if (p.kind === "hq") {
      drawWindows(p, now);
      // a holographic ring spinning above headquarters, and an antenna beacon
      ctx.save();
      ctx.beginPath(); ctx.ellipse(p.x, y - 14, p.w * 0.42, 9, 0, 0, Math.PI * 2);
      ctx.setLineDash([10, 6]); ctx.lineDashOffset = -now / 25;
      neonStroke(C.gold, 0.8, 1.6);
      ctx.restore();
      ctx.fillStyle = C.gold; ctx.globalAlpha = 0.5 + 0.5 * Math.sin(now / 300);
      ctx.beginPath(); ctx.arc(p.x, y - 30, 3, 0, Math.PI * 2); ctx.fill(); ctx.globalAlpha = 1;
    }

    if (p.kind === "tower") {
      drawUltronEye(p, now);
      title(p.title, p.x, y + p.h + 14, 12, C.violet);
      text(p.sub.toUpperCase(), p.x, y + p.h + 30, 10, C.muted);
      return;
    }
    const ty = p.kind === "gate" ? p.y - 14 : p.kind === "bank" ? p.y : p.y - (p.h > 60 ? 12 : 8);
    const life = SCORED.includes(name) ? survival(name) : null;
    if (life) {  // segmented health bar under the building: how often this agent has been right
      const segs = 10, bw = p.w - 12, bx = p.x - bw / 2, by = y + p.h + 6, sw = bw / segs;
      const filled = Math.round(((life.acc ?? 0) / 100) * segs);
      const color = STATUS[life.status][1];
      for (let i = 0; i < segs; i++) {
        ctx.fillStyle = i < filled ? color : "rgba(255,255,255,.07)";
        if (i < filled) { ctx.save(); ctx.shadowColor = color; ctx.shadowBlur = 6; }
        ctx.fillRect(bx + i * sw + 1, by, sw - 2, 4);
        if (i < filled) ctx.restore();
      }
    }
    const dying = life && life.status === "dying";
    title((dying ? "☠ " : "") + p.title, p.x, ty, p.kind === "squad" ? 11 : 14, dying ? C.red : C.text,
          active ? 14 : 6, p.w - 12);
    let sub = p.sub;
    if (p.kind === "bank" && state) sub = money(state.startEquity + state.realized);
    text(sub.toUpperCase(), p.x, ty + 17, 10, p.kind === "bank" ? C.gold : C.muted, 400, "center", MONO_FONT, 0, p.w - 10);
  }

  function drawUltronEye(p, now) {
    const cx = p.x, cy = p.y - p.h / 2 + 25;
    const done = audit && P >= groups.length;
    const iris = done ? (audit.ok ? C.green : C.red) : C.violet;
    ctx.fillStyle = "#04050c";
    ctx.beginPath(); ctx.ellipse(cx, cy, 24, 13, 0, 0, Math.PI * 2); ctx.fill();
    const t = fx.eyeTarget || { x: cx, y: cy + 100 };
    const a = Math.atan2(t.y - cy, t.x - cx);
    const px = cx + Math.cos(a) * 9, py = cy + Math.sin(a) * 5;
    ctx.save(); ctx.shadowColor = iris; ctx.shadowBlur = 20;
    ctx.fillStyle = iris; ctx.beginPath(); ctx.arc(px, py, 7, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
    ctx.fillStyle = "#04050c"; ctx.beginPath(); ctx.arc(px, py, 2.5, 0, Math.PI * 2); ctx.fill();
    // a slow radar ring pulsing out from the eye
    const r = 14 + ((now / 30) % 40);
    ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.strokeStyle = iris; ctx.globalAlpha = Math.max(0, 1 - (r - 14) / 40) * 0.5; ctx.lineWidth = 1; ctx.stroke();
    ctx.globalAlpha = 1;
  }

  function drawExchange(ex) {
    const { sym, x, y, w, h } = ex;
    const now = performance.now();
    const pos = Object.values(state.open).find((t) => t.symbol === sym);
    const g = fx.glows[`ex:${sym}`];
    panel(x, y, w, h, pos ? C.gold : C.cyan, pos ? 0.75 : 0.4);
    const prices = (state.prices[sym] || []).slice(-SPARK_POINTS);
    const lastP = prices[prices.length - 1];
    const firstP = (state.prices[sym] || [])[0];
    ctx.letterSpacing = "2px";
    text(sym, x + 16, y + 22, 17, C.cyan, 900, "left", TITLE_FONT, 10);
    ctx.letterSpacing = "0px";
    if (lastP != null) {
      const ch = firstP ? (lastP / firstP - 1) * 100 : 0;
      text(lastP.toFixed(2), x + w - 16, y + 18, 17, C.white, 400, "right", MONO_FONT, 6);
      text(`${ch >= 0 ? "▲ +" : "▼ "}${ch.toFixed(2)}%`, x + w - 16, y + 37, 11, ch >= 0 ? C.green : C.red, 400, "right");
    }
    const dec = state.decisions[sym];
    const status = pos ? `HOLDING ${pos.size} @ ${pos.entry.toFixed(2)}` :
      dec ? (dec.action === "buy" ? (dec.executed ? "BOUGHT" : "BUY BLOCKED") : "SCANNING FOR A SETUP") : "STANDBY";
    text(status, x + 16, y + 42, 10, pos ? C.gold : C.muted, 400, "left");
    if (g && now < g.until) { panel(x, y, w, h, g.color, 1.4, "rgba(0,0,0,0)"); }

    const gx = x + 14, gy = y + 60, gw = w - 28 - (pos ? 54 : 0), gh = h - 76;
    if (prices.length < 2) { text("AWAITING PRICE FEED", x + w / 2, gy + gh / 2, 11, C.muted); return; }
    let lo = Math.min(...prices), hi = Math.max(...prices);
    let target = null;
    if (pos) {
      target = pos.entry + (pos.entry - pos.stop_loss) * meta.take_profit_rr;
      lo = Math.min(lo, pos.stop_loss); hi = Math.max(hi, target);
    }
    const pad = (hi - lo) * 0.08 || 1; lo -= pad; hi += pad;
    const Y = (v) => gy + gh - ((v - lo) / (hi - lo)) * gh;
    const X = (i) => gx + (i / (SPARK_POINTS - 1)) * gw;

    ctx.strokeStyle = "rgba(0,229,255,.08)"; ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) { const yy = gy + (gh * i) / 4; ctx.beginPath(); ctx.moveTo(gx, yy); ctx.lineTo(gx + gw, yy); ctx.stroke(); }
    for (let i = 0; i <= 6; i++) { const xx = gx + (gw * i) / 6; ctx.beginPath(); ctx.moveTo(xx, gy); ctx.lineTo(xx, gy + gh); ctx.stroke(); }

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
    const lineColor = up ? C.green : C.red;
    const li = prices.length - 1;
    // glowing area under the price line
    const fill = ctx.createLinearGradient(0, gy, 0, gy + gh);
    fill.addColorStop(0, up ? "rgba(43,255,163,.28)" : "rgba(255,61,110,.28)");
    fill.addColorStop(1, "rgba(0,0,0,0)");
    ctx.beginPath(); prices.forEach((v, i) => (i ? ctx.lineTo(X(i), Y(v)) : ctx.moveTo(X(i), Y(v))));
    ctx.lineTo(X(li), gy + gh); ctx.lineTo(X(0), gy + gh); ctx.closePath();
    ctx.fillStyle = fill; ctx.fill();
    ctx.beginPath(); prices.forEach((v, i) => (i ? ctx.lineTo(X(i), Y(v)) : ctx.moveTo(X(i), Y(v))));
    ctx.lineJoin = "round";
    neonStroke(lineColor, 0.9, 2);
    // the live price: a pulsing beacon
    const beacon = pos ? C.gold : C.white;
    ctx.save(); ctx.shadowColor = beacon; ctx.shadowBlur = 14;
    ctx.fillStyle = beacon;
    ctx.beginPath(); ctx.arc(X(li), Y(prices[li]), 3.5, 0, Math.PI * 2); ctx.fill(); ctx.restore();
    const pr = 4 + ((now / 25) % 14);
    ctx.beginPath(); ctx.arc(X(li), Y(prices[li]), pr, 0, Math.PI * 2);
    ctx.strokeStyle = beacon; ctx.globalAlpha = 1 - (pr - 4) / 14; ctx.lineWidth = 1; ctx.stroke();
    ctx.globalAlpha = 1;
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

  const ease = (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);

  // Signals are light trails: a bright head with a fading tail, added like light.
  function drawParticles(now) {
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    for (const p of fx.particles) {
      const e = ease((now - p.t0) / p.dur);
      ctx.beginPath();
      for (let k = 0; k <= 10; k++) {
        const q = pointOn(p.pts, Math.max(0, e - k * 0.025));
        k ? ctx.lineTo(q.x, q.y) : ctx.moveTo(q.x, q.y);
      }
      ctx.shadowColor = p.color; ctx.shadowBlur = 14;
      ctx.strokeStyle = p.color; ctx.globalAlpha = 0.55; ctx.lineWidth = p.size * 0.9; ctx.lineCap = "round";
      ctx.stroke();
      const head = pointOn(p.pts, e);
      ctx.globalAlpha = 1; ctx.fillStyle = "#ffffff";
      ctx.beginPath(); ctx.arc(head.x, head.y, p.size * 0.55, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = p.color;
      ctx.beginPath(); ctx.arc(head.x, head.y, p.size, 0, Math.PI * 2); ctx.fill();
    }
    ctx.restore();
  }

  function drawFloats(now) {
    for (const f of fx.floats) {
      const t = (now - f.t0) / FLOAT_LIFE;
      ctx.globalAlpha = 1 - t * t;
      ctx.letterSpacing = "1px";
      text(f.text, f.x, f.y - t * 34, 13, f.color, 700, "center", TITLE_FONT, 12);
      ctx.letterSpacing = "0px";
    }
    ctx.globalAlpha = 1;
  }

  // "DAY 2": a glitching holographic banner, with the color channels split apart.
  function drawBanner(now) {
    if (!fx.banner) return;
    const t = (now - fx.banner.t0) / 2200;
    if (t >= 1) { fx.banner = null; return; }
    const a = Math.sin(t * Math.PI);
    const jitter = Math.random() < 0.15 ? (Math.random() - 0.5) * 10 : 0;
    const label = fx.banner.text.toUpperCase();
    ctx.letterSpacing = "8px";
    ctx.globalAlpha = a * 0.6;
    text(label, W / 2 - 3 + jitter, HORIZON, 46, C.magenta, 900, "center", TITLE_FONT);
    text(label, W / 2 + 3 - jitter, HORIZON, 46, C.cyan, 900, "center", TITLE_FONT);
    ctx.globalAlpha = a;
    text(label, W / 2, HORIZON, 46, C.white, 900, "center", TITLE_FONT, 20);
    ctx.letterSpacing = "0px";
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
    bookShown = scoreShown = briefingShown = undefined;
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
        trialScores = await getJSON("/trial/scores.json");
      }
    } catch (err) {
      console.warn("poll failed", err);
    } finally {
      setTimeout(poll, audit ? 2500 : 700);
    }
  }

  // ---------- 3D view, loaded on first use ----------
  const handles = {
    W, H, C, NEON, PLACES, SPARK_POINTS, FLOAT_LIFE,
    exchanges, center, roadPaths, pointOn, ease, dayPhase, money, SCORED, STATUS, survival,
    get state() { return state; }, get fx() { return fx; }, get meta() { return meta; },
    get audit() { return audit; }, get done() { return !!audit && P >= groups.length; },
  };
  let module3d = null, renderer3d = null, renderer3dRun = null;
  async function setView(mode) {
    const btn = $("b-view");
    if (mode === "3d" && !module3d) {
      btn.textContent = "Loading 3D...";
      try {
        module3d = await import("./city3d.js");  // pulls three.js from the CDN on first use
      } catch (err) {
        console.warn("3D view unavailable", err);
        btn.textContent = "3D unavailable (offline?)";
        return;
      }
    }
    mode3d = mode === "3d";
    $("city").hidden = mode3d;
    $("city3d").hidden = !mode3d;
    btn.textContent = mode3d ? "2D view" : "3D view";
    try { localStorage.setItem("zcity-view", mode); } catch { /* storage blocked: fine */ }
  }

  // The 3D scene is built once the run's data is in, and rebuilt when a new run starts
  // (a new run can have a different watchlist, so different exchanges).
  function current3d() {
    if (!mode3d || !module3d || !meta) return null;
    if (!renderer3d || renderer3dRun !== runId) {
      if (renderer3d) renderer3d.dispose();
      renderer3d = module3d.create($("city3d"), handles);
      renderer3dRun = runId;
    }
    return renderer3d;
  }
  $("b-view").addEventListener("click", () => setView(mode3d ? "2d" : "3d"));
  try { if (localStorage.getItem("zcity-view") === "3d") setView("3d"); } catch { /* ignore */ }

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
