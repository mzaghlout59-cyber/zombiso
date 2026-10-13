// Zombiso AI City as a solar system (three.js). Raphael is the Sun; every agent lives on
// a real planet or moon, placed where that planet really is today.
//
// Planet positions come from NASA JPL's "Keplerian Elements for Approximate Positions of
// the Major Planets" (E. M. Standish, JPL Solar System Dynamics, Table 1, valid 1800-2050):
// https://ssd.jpl.nasa.gov/planets/approx_pos.html
// Distances are compressed (r^0.45) and sizes exaggerated so everything fits on screen;
// directions, orbit shapes and tilts are real.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";

// [a (AU), e, I (deg), L (deg), long. perihelion (deg), long. ascending node (deg)] at J2000,
// then their rates per Julian century. Source: JPL, Table 1 (1800 AD - 2050 AD).
const ELEMENTS = {
  mercury: [[0.38709927, 0.20563593, 7.00497902, 252.25032350, 77.45779628, 48.33076593],
            [0.00000037, 0.00001906, -0.00594749, 149472.67411175, 0.16047689, -0.12534081]],
  venus:   [[0.72333566, 0.00677672, 3.39467605, 181.97909950, 131.60246718, 76.67984255],
            [0.00000390, -0.00004107, -0.00078890, 58517.81538729, 0.00268329, -0.27769418]],
  earth:   [[1.00000261, 0.01671123, -0.00001531, 100.46457166, 102.93768193, 0.0],
            [0.00000562, -0.00004392, -0.01294668, 35999.37244981, 0.32327364, 0.0]],
  mars:    [[1.52371034, 0.09339410, 1.84969142, -4.55343205, -23.94362959, 49.55953891],
            [0.00001847, 0.00007882, -0.00813131, 19140.30268499, 0.44441088, -0.29257343]],
  jupiter: [[5.20288700, 0.04838624, 1.30439695, 34.39644051, 14.72847983, 100.47390909],
            [-0.00011607, -0.00013253, -0.00183714, 3034.74612775, 0.21252668, 0.20469106]],
  saturn:  [[9.53667594, 0.05386179, 2.48599187, 49.95424423, 92.59887831, 113.66242448],
            [-0.00125060, -0.00050991, 0.00193609, 1222.49362201, -0.41897216, -0.28867794]],
  uranus:  [[19.18916464, 0.04725744, 0.77263783, 313.23810451, 170.95427630, 74.01692503],
            [-0.00196176, -0.00004397, -0.00242939, 428.48202785, 0.40805281, 0.04240589]],
  neptune: [[30.06992276, 0.00859048, 1.77004347, -55.12002969, 44.96476227, 131.78422574],
            [0.00026291, 0.00005105, 0.00035372, 218.45945325, -0.32241464, -0.00508664]],
};
// Mean radii in km (NASA planetary fact sheets) - drives the (exaggerated) display size.
const RADIUS_KM = { mercury: 2440, venus: 6052, earth: 6371, mars: 3390,
                    jupiter: 69911, saturn: 58232, uranus: 25362, neptune: 24622 };
const LOOK = {  // procedural surface: [base color, band/feature color, style]
  mercury: ["#9b9389", "#6d665e", "rock"], venus: ["#e9cf8f", "#c9a25a", "haze"],
  earth: ["#2a6fd6", "#3f9b4a", "earth"], mars: ["#c1502e", "#7a2b17", "rock"],
  jupiter: ["#d9b58a", "#a8693f", "bands"], saturn: ["#e6d29a", "#b8975b", "bands"],
  uranus: ["#9fe3ec", "#7cc8d6", "bands"], neptune: ["#3f6fe8", "#2a49b5", "bands"],
};
// Which agent lives where. Moons: real ones, with their real orbital periods (days).
const HOMES = {
  Research: "mercury", Vault: "venus", Axiom: "earth", Aegis: "mars", Sage: "jupiter",
};
const MOONS = {
  mars: [["Ledgerkeeper", "Phobos", 0.32], ["Scorekeeper", "Deimos", 1.26]],
  jupiter: [["Scout", "Io", 1.77], ["Pulse", "Europa", 3.55], ["Lens", "Ganymede", 7.15], ["News", "Callisto", 16.69]],
  earth: [[null, "Moon", 27.32]],
};
const STOCK_PLANETS = ["saturn", "uranus", "neptune"];  // the watchlist's first three stocks
const DAYS_PER_SECOND = 2;  // the solar system's own clock: starts at today, runs 2 days/second

const AU_SCALE = 175;
const scaleR = (au) => AU_SCALE * Math.pow(au, 0.45);  // inner planets get room, Neptune still fits
const rad = (d) => (d * Math.PI) / 180;

// Heliocentric ecliptic position (AU) of a planet at Julian date jd, per JPL's method.
function planetAU(name, jd, meanAnomalyDeg) {
  const [e0, rate] = ELEMENTS[name];
  const T = (jd - 2451545.0) / 36525;
  const [a, e, I, L, peri, node] = e0.map((v, i) => v + rate[i] * T);
  const w = peri - node;
  let M = meanAnomalyDeg ?? (L - peri);
  M = ((M + 180) % 360 + 360) % 360 - 180;
  const Mr = rad(M);
  let E = Mr + e * Math.sin(Mr);
  for (let k = 0; k < 8; k++) E -= (E - e * Math.sin(E) - Mr) / (1 - e * Math.cos(E));  // Kepler's equation
  const xp = a * (Math.cos(E) - e), yp = a * Math.sqrt(1 - e * e) * Math.sin(E);
  const [cw, sw, cO, sO, cI, sI] = [Math.cos(rad(w)), Math.sin(rad(w)), Math.cos(rad(node)),
                                    Math.sin(rad(node)), Math.cos(rad(I)), Math.sin(rad(I))];
  return {
    x: (cw * cO - sw * sO * cI) * xp + (-sw * cO - cw * sO * cI) * yp,
    y: (cw * sO + sw * cO * cI) * xp + (-sw * sO + cw * cO * cI) * yp,
    z: (sw * sI) * xp + (cw * sI) * yp,
  };
}

// Ecliptic AU -> scene: the ecliptic is the horizontal plane; distances compressed.
function toScene(p, out = new THREE.Vector3()) {
  const r = Math.hypot(p.x, p.y, p.z) || 1;
  const k = scaleR(r) / r;
  return out.set(p.x * k, p.z * k, -p.y * k);
}

function planetTexture(name) {
  const [base, feature, style] = LOOK[name];
  const c = document.createElement("canvas");
  c.width = 256; c.height = 128;
  const g = c.getContext("2d");
  g.fillStyle = base; g.fillRect(0, 0, 256, 128);
  let seed = name.length * 977;
  const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  if (style === "bands") {
    for (let y = 0; y < 128; y += 3 + rnd() * 6) {
      g.fillStyle = feature; g.globalAlpha = 0.15 + rnd() * 0.45;
      g.fillRect(0, y, 256, 2 + rnd() * 6);
    }
    if (name === "jupiter") { g.globalAlpha = 0.9; g.fillStyle = "#b5523a"; g.beginPath(); g.ellipse(170, 80, 16, 8, 0, 0, 7); g.fill(); }
  } else if (style === "earth") {
    for (let i = 0; i < 26; i++) {
      g.fillStyle = feature; g.globalAlpha = 0.85;
      g.beginPath(); g.ellipse(rnd() * 256, 20 + rnd() * 88, 8 + rnd() * 26, 5 + rnd() * 14, rnd() * 3, 0, 7); g.fill();
    }
    for (let i = 0; i < 40; i++) {  // clouds
      g.fillStyle = "#ffffff"; g.globalAlpha = 0.35;
      g.fillRect(rnd() * 256, rnd() * 128, 10 + rnd() * 30, 2 + rnd() * 3);
    }
  } else {
    for (let i = 0; i < 260; i++) {  // craters / dust / haze swirls
      g.fillStyle = rnd() < 0.5 ? feature : "#ffffff"; g.globalAlpha = style === "haze" ? 0.08 : 0.18;
      g.beginPath(); g.arc(rnd() * 256, rnd() * 128, 1 + rnd() * (style === "haze" ? 14 : 5), 0, 7); g.fill();
    }
  }
  g.globalAlpha = 1;
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function glowSprite(color, size) {
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const g = c.getContext("2d");
  const grad = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  grad.addColorStop(0, "rgba(255,255,255,1)");
  grad.addColorStop(0.2, color);
  grad.addColorStop(1, "rgba(0,0,0,0)");
  g.fillStyle = grad; g.fillRect(0, 0, 128, 128);
  const s = new THREE.Sprite(new THREE.SpriteMaterial({
    map: new THREE.CanvasTexture(c), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  }));
  s.scale.set(size, size, 1);
  return s;
}

export function create(container, Z) {
  const { C } = Z;
  const startJD = Date.now() / 86400000 + 2440587.5;  // today, as a Julian date
  const t0 = performance.now();
  const jdNow = (now) => startJD + ((now - t0) / 1000) * DAYS_PER_SECOND;

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  container.append(renderer.domElement);
  const overlay = document.createElement("canvas");
  overlay.className = "overlay";
  container.append(overlay);
  const octx = overlay.getContext("2d");

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x010108);
  const camera = new THREE.PerspectiveCamera(45, 1, 1, 20000);
  camera.position.set(0, 720, 1180);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.minDistance = 150;
  controls.maxDistance = 4500;

  scene.add(new THREE.AmbientLight(0x30354f, 0.55));
  const sunLight = new THREE.PointLight(0xfff1d0, 3.2, 0, 0);
  scene.add(sunLight);

  // ---------- the sky: a starfield with a Milky Way band ----------
  {
    const n = 7000, pos = new Float32Array(n * 3), col = new Float32Array(n * 3);
    let seed = 11;
    const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    const tint = new THREE.Color();
    for (let i = 0; i < n; i++) {
      const band = i < n * 0.55;  // most stars crowd into a tilted band, like the Milky Way
      let u = rnd() * 2 - 1, th = rnd() * Math.PI * 2;
      if (band) u = (rnd() - 0.5) * 0.25;
      const s = Math.sqrt(1 - u * u), R = 6000 + rnd() * 3000;
      const v = new THREE.Vector3(Math.cos(th) * s, u, Math.sin(th) * s).applyAxisAngle(new THREE.Vector3(1, 0, 0.3).normalize(), 1.05);
      pos.set([v.x * R, v.y * R, v.z * R], i * 3);
      tint.setHSL(0.55 + rnd() * 0.15, 0.4, 0.55 + rnd() * 0.45);
      col.set([tint.r, tint.g, tint.b], i * 3);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    geo.setAttribute("color", new THREE.BufferAttribute(col, 3));
    const dot = document.createElement("canvas");  // round, soft stars instead of square points
    dot.width = dot.height = 32;
    const dg = dot.getContext("2d"), grad = dg.createRadialGradient(16, 16, 0, 16, 16, 16);
    grad.addColorStop(0, "rgba(255,255,255,1)"); grad.addColorStop(0.4, "rgba(255,255,255,.5)"); grad.addColorStop(1, "rgba(255,255,255,0)");
    dg.fillStyle = grad; dg.fillRect(0, 0, 32, 32);
    scene.add(new THREE.Points(geo, new THREE.PointsMaterial({ size: 22, map: new THREE.CanvasTexture(dot), vertexColors: true,
                                                               sizeAttenuation: true, transparent: true, opacity: 0.9,
                                                               depthWrite: false, blending: THREE.AdditiveBlending })));
  }

  // ---------- the Sun: Raphael ----------
  const sunTex = (() => {
    const c = document.createElement("canvas");
    c.width = 256; c.height = 128;
    const g = c.getContext("2d");
    g.fillStyle = "#ffb52e"; g.fillRect(0, 0, 256, 128);
    let seed = 5;
    const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    for (let i = 0; i < 900; i++) {  // granulation
      g.fillStyle = rnd() < 0.5 ? "#fff1a8" : "#ff7a1a"; g.globalAlpha = 0.25;
      g.beginPath(); g.arc(rnd() * 256, rnd() * 128, 1 + rnd() * 4, 0, 7); g.fill();
    }
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
    return t;
  })();
  const sun = new THREE.Mesh(new THREE.SphereGeometry(36, 48, 32), new THREE.MeshBasicMaterial({ map: sunTex }));
  const corona = glowSprite("rgba(255,150,30,0.55)", 170);
  scene.add(sun, corona);

  // ---------- planets, their orbits and moons ----------
  const bodies = {};  // planet name -> { mesh, pos (Vector3), size, ... }
  const jd0 = jdNow(performance.now());
  for (const name of Object.keys(ELEMENTS)) {
    const size = 4 + 18 * Math.sqrt(RADIUS_KM[name] / 69911);
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(size, 40, 24),
      new THREE.MeshStandardMaterial({ map: planetTexture(name), roughness: 0.9, metalness: 0,
                                       emissive: new THREE.Color(0x000000) }));
    scene.add(mesh);
    if (name === "saturn") {  // Saturn's rings, tilted 26.7 degrees like the real ones
      const ring = new THREE.Mesh(new THREE.RingGeometry(size * 1.35, size * 2.3, 96),
        new THREE.MeshBasicMaterial({ color: 0xe9d7a6, side: THREE.DoubleSide, transparent: true, opacity: 0.55 }));
      ring.rotation.x = rad(90 - 26.7);
      mesh.add(ring);
    }
    // the full orbit, sampled from the same elements
    const pts = [];
    for (let m = 0; m <= 360; m += 2) pts.push(toScene(planetAU(name, jd0, m)));
    const orbit = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineBasicMaterial({ color: 0x5c7cff, transparent: true, opacity: 0.22 }));
    scene.add(orbit);
    const moons = (MOONS[name] || []).map(([agent, moonName, period], i) => {
      const m = new THREE.Mesh(new THREE.SphereGeometry(agent ? 2.6 : 2.2, 16, 12),
        new THREE.MeshStandardMaterial({ color: agent ? 0xcfd8ff : 0xbbbbbb, emissive: new THREE.Color(0x000000) }));
      scene.add(m);
      return { mesh: m, agent, moonName, period, dist: size + 9 + i * 6, phase: i * 1.7 };
    });
    bodies[name] = { name, mesh, size, moons, pos: new THREE.Vector3(), glowUntil: 0 };
  }

  // ---------- Ultron: a distant watching star ----------
  const ultron = glowSprite("rgba(181,107,255,0.95)", 220);
  ultron.position.set(-2600, 1500, -3400);
  const ultronCore = new THREE.Mesh(new THREE.SphereGeometry(16, 20, 14), new THREE.MeshBasicMaterial({ color: 0xe8d4ff }));
  ultronCore.position.copy(ultron.position);
  scene.add(ultron, ultronCore);

  // ---------- who sits where ----------
  const stockSymbols = () => (Z.meta.watchlist || []);
  function stockBody(sym) {
    const i = stockSymbols().indexOf(sym);
    return STOCK_PLANETS[i] ? bodies[STOCK_PLANETS[i]] : null;  // a 4th+ stock has no planet of its own
  }
  function bodyPos(key) {
    if (key === "sun") return sun.position;
    if (key === "ultron") return ultron.position;
    if (key.startsWith("moon:")) {
      const [, planet, agent] = key.split(":");
      const m = bodies[planet].moons.find((x) => x.agent === agent);
      return m ? m.mesh.position : bodies[planet].pos;
    }
    if (key.startsWith("stock:")) { const b = stockBody(key.slice(6)); return b ? b.pos : sun.position; }
    return bodies[key] ? bodies[key].pos : sun.position;
  }
  function placeKey(name) {
    if (name === "Raphael") return "sun";
    if (name === "Ultron") return "ultron";
    if (HOMES[name]) return HOMES[name];
    for (const [planet, list] of Object.entries(MOONS))
      if (list.some(([agent]) => agent === name)) return `moon:${planet}:${name}`;
    return "sun";
  }
  // The 2D city's signal paths start and end at buildings; map each end to its body.
  function anchors() {
    const out = Object.keys(Z.PLACES).map((n) => ({ key: placeKey(n), ...Z.center(n) }));
    for (const ex of Z.exchanges()) {
      out.push({ key: `stock:${ex.sym}`, x: ex.x + ex.w / 2, y: ex.y });
      out.push({ key: `stock:${ex.sym}`, x: ex.x + ex.w / 2, y: ex.y + ex.h / 2 });
    }
    return out;
  }
  const anchorList = anchors();
  const nearest = (p) => anchorList.reduce((best, a) =>
    (Math.hypot(a.x - p.x, a.y - p.y) < Math.hypot(best.x - p.x, best.y - p.y) ? a : best)).key;

  // ---------- signals: comets arcing between bodies ----------
  const orbGeo = new THREE.SphereGeometry(1, 12, 10);
  const comets = Array.from({ length: 200 }, () => {
    const m = new THREE.Mesh(orbGeo, new THREE.MeshBasicMaterial({ color: 0xffffff }));
    m.visible = false; scene.add(m);
    return m;
  });
  const tails = Array.from({ length: 200 }, () => {
    const l = new THREE.Line(new THREE.BufferGeometry().setFromPoints(Array.from({ length: 12 }, () => new THREE.Vector3())),
      new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.6 }));
    l.visible = false; scene.add(l);
    return l;
  });

  // ---------- bloom ----------
  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  const bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), 0.7, 0.45, 0.55);
  composer.addPass(bloom);
  composer.addPass(new OutputPass());

  function resize() {
    const w = container.clientWidth, h = container.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    composer.setSize(w, h); bloom.setSize(w, h);
    renderer.domElement.style.width = w + "px"; renderer.domElement.style.height = h + "px";
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    overlay.width = w * dpr; overlay.height = h * dpr;
    overlay.style.width = w + "px"; overlay.style.height = h + "px";
    octx.setTransform(dpr, 0, 0, dpr, 0, 0);
    camera.aspect = w / h; camera.updateProjectionMatrix();
  }
  const ro = new ResizeObserver(resize);
  ro.observe(container);
  resize();

  const vec = new THREE.Vector3(), a = new THREE.Vector3(), b = new THREE.Vector3(), mid = new THREE.Vector3();
  function toScreen(p) {
    vec.copy(p).project(camera);
    if (vec.z > 1) return null;
    return { x: (vec.x + 1) / 2 * container.clientWidth, y: (1 - vec.y) / 2 * container.clientHeight };
  }
  // Labels are queued, then laid out so they never sit on top of each other: each one that
  // would overlap an already-placed label slides down until it finds free space.
  let queue = [];
  const fontFor = (i, size) => `${i ? 400 : 700} ${size}px ${i ? '"Share Tech Mono", monospace' : '"Orbitron", "Segoe UI", sans-serif'}`;
  function label(lines, p, dy, color) {
    const s = toScreen(p);
    if (!s) return;
    let w = 0;
    lines.forEach(([text, size], i) => { octx.font = fontFor(i, size); w = Math.max(w, octx.measureText(text).width); });
    queue.push({ lines, x: s.x, y: s.y + dy, w: w + 8, h: lines.length * 14, color });
  }
  function flushLabels() {
    const placed = [];
    for (const l of queue) {
      let y = l.y;
      for (let tries = 0; tries < 12; tries++) {
        const hit = placed.find((p) => Math.abs(p.x - l.x) < (p.w + l.w) / 2 && y < p.y + p.h && y + l.h > p.y);
        if (!hit) break;
        y = hit.y + hit.h + 1;
      }
      placed.push({ x: l.x, y, w: l.w, h: l.h });
      octx.textAlign = "center"; octx.textBaseline = "top";
      l.lines.forEach(([text, size, col], i) => {
        octx.font = fontFor(i, size);
        octx.lineWidth = 3; octx.strokeStyle = "rgba(1,1,8,0.9)";
        octx.strokeText(text, l.x, y + i * 14);
        octx.fillStyle = col || l.color; octx.fillText(text, l.x, y + i * 14);
      });
    }
    queue = [];
  }
  function agentColor(agent, fallback) {
    if (!agent || !Z.SCORED.includes(agent)) return fallback;
    return Z.STATUS[Z.survival(agent).status][1];
  }
  function agentTitle(agent) {
    if (!Z.SCORED.includes(agent)) return agent;
    const life = Z.survival(agent);
    return `${life.status === "dying" ? "☠ " : ""}${agent}${life.acc != null ? ` ${life.acc}%` : ""}`;
  }

  function render(now) {
    const state = Z.state, fx = Z.fx;
    controls.update();
    const jd = jdNow(now);

    // the Sun breathes, and brightens through the city's day
    const light = Math.sin(Z.dayPhase() * Math.PI);
    const g = fx.glows.Raphael, flare = g && now < g.until ? 1.25 : 1;
    sun.rotation.y = now / 9000;
    corona.scale.setScalar((165 + 15 * Math.sin(now / 600)) * flare);
    sunLight.intensity = (2.4 + light * 1.2) * flare;

    // planets at their real positions (time running from today)
    for (const body of Object.values(bodies)) {
      toScene(planetAU(body.name, jd), body.pos);
      body.mesh.position.copy(body.pos);
      body.mesh.rotation.y = now / 2500;
      const agent = Object.keys(HOMES).find((k) => HOMES[k] === body.name);
      const gl = fx.glows[agent] || fx.glows[`ex:${stockSymbols()[STOCK_PLANETS.indexOf(body.name)]}`];
      const on = gl && now < gl.until;
      body.mesh.material.emissive.set(on ? gl.color : (agent && Z.SCORED.includes(agent) && Z.survival(agent).status === "dying" ? C.red : 0x000000));
      body.mesh.material.emissiveIntensity = on ? 0.6 * Math.min(1, (gl.until - now) / 700) + 0.15 : 0.25;
      for (const m of body.moons) {
        const ang = m.phase + ((jd - startJD) / m.period) * Math.PI * 2 * 0.25;  // slowed so moons stay readable
        m.mesh.position.set(body.pos.x + Math.cos(ang) * m.dist, body.pos.y + Math.sin(ang) * 2, body.pos.z + Math.sin(ang) * m.dist);
        const mg = m.agent && fx.glows[m.agent];
        const mon = mg && now < mg.until;
        m.mesh.material.emissive.set(mon ? mg.color : 0x000000);
        m.mesh.material.emissiveIntensity = mon ? 0.9 : 0;
      }
    }

    // Ultron's star: pulses, and takes the verdict's color at the end of a run
    const iris = Z.done ? (Z.audit.ok ? C.green : C.red) : C.violet;
    ultron.material.color.set(iris);
    ultronCore.material.color.set(iris);
    ultron.scale.setScalar(200 + 40 * Math.sin(now / 500));

    // comets: each city signal flies between the bodies of its sender and receiver
    let n = 0;
    for (const p of fx.particles) {
      if (n >= comets.length) break;
      const t = Math.min(1, (now - p.t0) / p.dur), e = Z.ease(t);
      a.copy(bodyPos(nearest(p.pts[0])));
      b.copy(bodyPos(nearest(p.pts[p.pts.length - 1])));
      mid.addVectors(a, b).multiplyScalar(0.5);
      mid.y += 40 + a.distanceTo(b) * 0.22;  // arc above the orbital plane
      const at = (u, out) => out.set(0, 0, 0)
        .addScaledVector(a, (1 - u) * (1 - u)).addScaledVector(mid, 2 * (1 - u) * u).addScaledVector(b, u * u);
      const head = comets[n], tail = tails[n];
      at(e, head.position);
      head.material.color.set(p.color);
      head.scale.setScalar(p.size * 0.9);
      head.visible = true;
      const arr = tail.geometry.attributes.position;
      for (let k = 0; k < 12; k++) { at(Math.max(0, e - k * 0.025), vec); arr.setXYZ(k, vec.x, vec.y, vec.z); }
      arr.needsUpdate = true;
      tail.material.color.set(p.color);
      tail.visible = true;
      n++;
    }
    for (let k = n; k < comets.length; k++) { comets[k].visible = false; tails[k].visible = false; }

    composer.render();

    // labels: agent names over their worlds, real names underneath
    const w = container.clientWidth, h = container.clientHeight;
    octx.clearRect(0, 0, w, h);
    label([["RAPHAEL", 14, C.gold], ["the Sun", 11, C.muted]], sun.position, -52, C.gold);
    for (const [agent, planet] of Object.entries(HOMES)) {
      const body = bodies[planet];
      const title = agent === "Vault" ? `TREASURY ${Z.money(state.startEquity + state.realized)}` : agentTitle(agent).toUpperCase();
      label([[title, 12], [planet[0].toUpperCase() + planet.slice(1), 10, C.muted]], body.pos, -body.size - 16,
            agentColor(agent, C.text));
    }
    // moon names only when you've zoomed in on them; otherwise they'd crowd their planet
    for (const body of Object.values(bodies)) for (const m of body.moons) {
      if (!m.agent || camera.position.distanceTo(m.mesh.position) > 700) continue;
      label([[agentTitle(m.agent), 10], [m.moonName, 9, C.muted]], m.mesh.position, -10, agentColor(m.agent, C.cyan));
    }
    stockSymbols().slice(0, 3).forEach((sym, i) => {
      const body = bodies[STOCK_PLANETS[i]];
      const prices = state.prices[sym] || [];
      const last = prices[prices.length - 1];
      const held = Object.values(state.open).some((t) => t.symbol === sym);
      label([[`${sym}${last != null ? " " + last.toFixed(2) : ""}`, 13, held ? C.gold : C.green],
             [STOCK_PLANETS[i][0].toUpperCase() + STOCK_PLANETS[i].slice(1) + (held ? " · holding" : ""), 10, C.muted]],
            body.pos, -body.size - 18, C.green);
    });
    label([["ULTRON", 13, iris], ["watching from afar", 10, C.muted]], ultron.position, 34, iris);
    flushLabels();

    const date = new Date((jd - 2440587.5) * 86400000).toISOString().slice(0, 10);
    octx.textAlign = "left"; octx.font = '400 11px "Share Tech Mono", monospace';
    octx.fillStyle = C.muted;
    octx.fillText(`Planet positions: NASA JPL orbital elements · ${date}`, 12, h - 14);
  }

  function dispose() {
    ro.disconnect();
    composer.dispose();
    controls.dispose();
    renderer.dispose();
    container.textContent = "";
  }

  return { render, resize, dispose };
}
