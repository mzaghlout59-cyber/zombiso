// Zombiso AI City in 3D (three.js). Reads the same state and effects as the 2D view
// through the handles city.js passes in (Z), so both views always show the same city.
// The 2D map's (x, y) becomes the ground plane: world X = x - 600, world Z = y - 360.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";

const HEIGHT = { squad: 45, commander: 85, hq: 140, gate: 80, tower: 230, bank: 55 };
const MAX_PARTICLES = 300;
const GLASS = 0x070d22;  // dark glass the neon edges sit on

export function create(container, Z) {
  const { C } = Z;
  const wx = (x) => x - Z.W / 2, wz = (y) => y - Z.H / 2;

  // ---------- renderer, camera, controls ----------
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  container.append(renderer.domElement);
  const overlay = document.createElement("canvas");
  overlay.className = "overlay";
  container.append(overlay);
  const octx = overlay.getContext("2d");

  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog(0x0a0620, 1200, 3000);
  const camera = new THREE.PerspectiveCamera(42, 1, 10, 6000);
  camera.position.set(0, 640, 780);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 0, -20);  // between the buildings (back) and the exchanges (front)
  controls.enableDamping = true;
  controls.maxPolarAngle = Math.PI * 0.47;   // never go under the ground
  controls.minDistance = 300;
  controls.maxDistance = 2600;

  // ---------- light: dim moonlight; the neon does the rest ----------
  const hemi = new THREE.HemisphereLight(0x6f7dff, 0x05020f, 0.5);
  const sun = new THREE.DirectionalLight(0xb9a6ff, 0.6);
  scene.add(hemi, sun, new THREE.AmbientLight(0x1a2050, 0.6));

  // glowing edges around any mesh: the core of the cyber look
  function neonEdges(geometry, color, opacity = 0.9) {
    return new THREE.LineSegments(new THREE.EdgesGeometry(geometry, 20),
      new THREE.LineBasicMaterial({ color, transparent: true, opacity }));
  }

  // ---------- ground: black glass under a neon grid ----------
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(4000, 3000),
    new THREE.MeshStandardMaterial({ color: 0x020409, roughness: 0.35, metalness: 0.6 }));
  ground.rotation.x = -Math.PI / 2;
  scene.add(ground);
  const grid = new THREE.GridHelper(4000, 100, 0x00e5ff, 0x00e5ff);
  grid.material.transparent = true; grid.material.opacity = 0.16;
  grid.position.y = 0.3;
  scene.add(grid);

  // roads: dark lanes with a glowing cyan line down the middle
  const roadMat = new THREE.MeshStandardMaterial({ color: 0x061024, roughness: 0.6, metalness: 0.4 });
  const laneMat = new THREE.MeshBasicMaterial({ color: 0x00e5ff, transparent: true, opacity: 0.75 });
  for (const [pts, width] of Z.roadPaths()) {
    for (let i = 1; i < pts.length; i++) {
      const a = pts[i - 1], b = pts[i];
      const len = Math.hypot(b.x - a.x, b.y - a.y);
      if (len < 1) continue;
      const angle = -Math.atan2(b.y - a.y, b.x - a.x);
      const seg = new THREE.Mesh(new THREE.BoxGeometry(len + width, 1, width * 1.6), roadMat);
      seg.position.set(wx((a.x + b.x) / 2), 0.6, wz((a.y + b.y) / 2));
      seg.rotation.y = angle;
      const lane = new THREE.Mesh(new THREE.BoxGeometry(len, 0.4, 1.2), laneMat);
      lane.position.set(seg.position.x, 1.4, seg.position.z);
      lane.rotation.y = angle;
      scene.add(seg, lane);
    }
  }

  // ---------- skyline: a ring of dark towers with neon crowns around the city ----------
  {
    let seed = 7;
    const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    const spots = [];
    while (spots.length < 140) {
      const x = (rnd() - 0.5) * 3600, z = (rnd() - 0.5) * 2600;
      if (Math.abs(x) < 820 && z > -560 && z < 560) continue;  // keep the city itself clear
      spots.push({ x, z, w: 40 + rnd() * 90, h: 80 + rnd() * rnd() * 520, crown: rnd() });
    }
    const towers = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1),
      new THREE.MeshStandardMaterial({ color: GLASS, roughness: 0.3, metalness: 0.7 }), spots.length);
    const crowns = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshBasicMaterial(), spots.length);
    const m = new THREE.Object3D(), col = new THREE.Color();
    spots.forEach((s, i) => {
      m.position.set(s.x, s.h / 2, s.z); m.scale.set(s.w, s.h, s.w); m.updateMatrix();
      towers.setMatrixAt(i, m.matrix);
      m.position.set(s.x, s.h + 1, s.z); m.scale.set(s.w + 2, 3, s.w + 2); m.updateMatrix();
      crowns.setMatrixAt(i, m.matrix);
      crowns.setColorAt(i, col.set(s.crown < 0.45 ? 0x00e5ff : s.crown < 0.8 ? 0xff2bd6 : 0xb56bff));
    });
    scene.add(towers, crowns);
  }

  // ---------- window lights: one procedural texture, tiled on every building ----------
  const windowImage = (() => {
    const c = document.createElement("canvas");
    c.width = 64; c.height = 64;
    const g = c.getContext("2d");
    g.fillStyle = "#000"; g.fillRect(0, 0, 64, 64);
    let seed = 3;
    const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    for (let y = 4; y < 64; y += 8) for (let x = 3; x < 64; x += 8) {
      const v = rnd();
      if (v < 0.45) continue;  // dark window
      g.fillStyle = `rgba(255,255,255,${0.35 + v * 0.65})`;
      g.fillRect(x, y, 4, 3);
    }
    return c;
  })();
  function windowsFor(w, h) {
    const t = new THREE.CanvasTexture(windowImage);
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.repeat.set(Math.max(1, w / 48), Math.max(1, h / 48));
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  }

  // ---------- buildings: dark glass with neon edges and glowing windows ----------
  const buildings = {};
  for (const [name, p] of Object.entries(Z.PLACES)) {
    const h = HEIGHT[p.kind] || 50;
    const neon = Z.NEON[p.kind];
    const lit = p.kind !== "gate" && p.kind !== "tower";  // shield and spire stay smooth
    const mat = new THREE.MeshStandardMaterial({ color: GLASS, roughness: 0.25, metalness: 0.75,
                                                 emissive: new THREE.Color(neon), emissiveIntensity: lit ? 0.7 : 0.06,
                                                 emissiveMap: lit ? windowsFor(p.w, h) : null });
    const group = new THREE.Group();
    let geo;
    if (p.kind === "gate") geo = new THREE.CylinderGeometry(p.w / 2, p.w / 2.6, h, 6);
    else if (p.kind === "tower") geo = new THREE.CylinderGeometry(p.w * 0.12, p.w * 0.3, h, 6);
    else geo = new THREE.BoxGeometry(p.w, h, p.h * 0.9);
    const body = new THREE.Mesh(geo, mat);
    body.position.y = h / 2;
    const edges = neonEdges(geo, neon);
    edges.position.y = h / 2;
    group.add(body, edges);
    if (p.kind === "bank") {  // a triangular pediment roof, edged in gold
      const roofGeo = new THREE.CylinderGeometry(p.h * 0.55, p.h * 0.55, p.w + 12, 3);
      const roof = new THREE.Mesh(roofGeo, mat);
      const roofEdges = neonEdges(roofGeo, neon);
      for (const r of [roof, roofEdges]) { r.rotation.z = Math.PI / 2; r.position.y = h + p.h * 0.25; }
      group.add(roof, roofEdges);
    }
    let eye = null, pupil = null, ring = null;
    if (p.kind === "tower") {  // Ultron's eye, with a halo
      eye = new THREE.Mesh(new THREE.SphereGeometry(20, 24, 16),
        new THREE.MeshStandardMaterial({ color: 0x05030c, emissive: 0xb56bff, emissiveIntensity: 0.4 }));
      eye.position.y = h + 18;
      pupil = new THREE.Mesh(new THREE.SphereGeometry(7, 16, 12), new THREE.MeshBasicMaterial({ color: 0xb56bff }));
      ring = new THREE.Mesh(new THREE.TorusGeometry(32, 1.2, 8, 48), new THREE.MeshBasicMaterial({ color: 0xb56bff }));
      ring.position.y = h + 18;
      group.add(eye, pupil, ring);
    }
    if (p.kind === "hq") {  // holographic rings spinning over headquarters
      ring = new THREE.Group();
      [0, 1].forEach((i) => {
        const t = new THREE.Mesh(new THREE.TorusGeometry(p.w * 0.45 - i * 18, 1.5, 8, 64),
          new THREE.MeshBasicMaterial({ color: i ? 0x00e5ff : 0xffcf4a, transparent: true, opacity: 0.85 }));
        t.rotation.x = Math.PI / 2;
        t.position.y = i * 16;
        ring.add(t);
      });
      ring.position.y = h + 30;
      group.add(ring);
    }
    group.position.set(wx(p.x), 0, wz(p.y));
    scene.add(group);
    buildings[name] = { group, mat, edges, neon, h, p, eye, pupil, ring, base: lit ? 0.7 : 0.06 };
  }

  // ---------- exchanges: holo platforms with glowing price bars ----------
  const exchanges = Z.exchanges().map((ex) => {
    const cx = wx(ex.x + ex.w / 2), cz = wz(ex.y + ex.h / 2);
    const baseGeo = new THREE.BoxGeometry(ex.w, 6, ex.h * 0.8);
    const base = new THREE.Mesh(baseGeo, new THREE.MeshStandardMaterial({ color: GLASS, roughness: 0.3, metalness: 0.7 }));
    const baseEdges = neonEdges(baseGeo, 0x00e5ff, 0.7);
    for (const b of [base, baseEdges]) b.position.set(cx, 3, cz);
    scene.add(base, baseEdges);
    const bars = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1),
      new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.85 }), Z.SPARK_POINTS);
    bars.count = 0;
    scene.add(bars);
    const level = (color) => {  // a thin bar across the chart, just in front of the price bars
      const m = new THREE.Mesh(new THREE.BoxGeometry(ex.w - 24, 2, 3), new THREE.MeshBasicMaterial({ color }));
      m.position.set(cx, 0, cz + 16);
      m.visible = false;
      scene.add(m);
      return m;
    };
    return { ex, cx, cz, bars, levels: { target: level(C.green), entry: level(0xe8eefc), stop: level(C.red) } };
  });

  // ---------- particle pool ----------
  const orbGeo = new THREE.SphereGeometry(1, 12, 10);
  const orbs = Array.from({ length: MAX_PARTICLES }, () => {
    const m = new THREE.Mesh(orbGeo, new THREE.MeshBasicMaterial({ color: 0xffffff }));
    m.visible = false;
    scene.add(m);
    return m;
  });

  // ---------- bloom: makes every neon line and orb actually glow ----------
  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  // strength, radius, threshold: only bright things (neon lines, orbs) bloom, not whole surfaces
  const bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), 0.75, 0.4, 0.5);
  composer.addPass(bloom);
  composer.addPass(new OutputPass());

  // ---------- sizing ----------
  function resize() {
    const w = container.clientWidth, h = container.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    composer.setSize(w, h);
    bloom.setSize(w, h);
    renderer.domElement.style.width = w + "px";
    renderer.domElement.style.height = h + "px";
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    overlay.width = w * dpr; overlay.height = h * dpr;
    overlay.style.width = w + "px"; overlay.style.height = h + "px";
    octx.setTransform(dpr, 0, 0, dpr, 0, 0);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  const ro = new ResizeObserver(resize);
  ro.observe(container);
  resize();

  // sky gets its own Color: scene.background keeps a reference, so it must not be reused
  const sky = new THREE.Color(), barColor = new THREE.Color();
  const night = new THREE.Color(0x020109), day = new THREE.Color(0x160a30);  // always night; day is a violet dusk
  const edgeColor = new THREE.Color();
  const dummy = new THREE.Object3D();
  const vec = new THREE.Vector3();

  function toScreen(x, y, z) {
    vec.set(x, y, z).project(camera);
    if (vec.z > 1) return null;  // behind the camera
    return { x: (vec.x + 1) / 2 * container.clientWidth, y: (1 - vec.y) / 2 * container.clientHeight };
  }

  function label(text, x, y, z, size, color, weight = 600) {
    const s = toScreen(x, y, z);
    if (!s) return;
    octx.font = `${weight} ${size}px "Orbitron", "Segoe UI", system-ui, sans-serif`;
    octx.letterSpacing = "1px";
    octx.textAlign = "center"; octx.textBaseline = "middle";
    octx.lineWidth = 3; octx.strokeStyle = "rgba(2,4,12,0.9)";
    octx.strokeText(text, s.x, s.y);
    octx.save(); octx.shadowColor = color; octx.shadowBlur = 10;
    octx.fillStyle = color; octx.fillText(text, s.x, s.y);
    octx.restore();
  }

  function render(now) {
    const state = Z.state, fx = Z.fx;
    controls.update();

    // sky and sun
    const ph = Z.dayPhase(), light = Math.sin(ph * Math.PI);
    sky.copy(night).lerp(day, light);
    scene.background = sky;
    scene.fog.color.copy(sky);
    const ang = ph * Math.PI;
    sun.position.set(-Math.cos(ang) * 900, 80 + Math.sin(ang) * 900, -350);
    sun.intensity = 0.35 + light * 0.5;
    hemi.intensity = 0.4 + light * 0.3;

    // buildings flare when their worker acts; otherwise their neon edges breathe softly
    for (const [name, b] of Object.entries(buildings)) {
      const g = fx.glows[name];
      if (g && now < g.until) {
        const k = Math.min(1, (g.until - now) / 700);
        b.mat.emissive.set(g.color);
        b.mat.emissiveIntensity = b.base + (b.mat.emissiveMap ? 0.5 : 0.22) * k;  // windows flare
        b.edges.material.color.set(g.color);
        b.edges.material.opacity = 1;
      } else {
        b.mat.emissive.set(b.neon);
        b.mat.emissiveIntensity = b.base;
        b.edges.material.color.copy(edgeColor.set(b.neon));
        b.edges.material.opacity = 0.6 + 0.25 * Math.sin(now / 900 + b.p.x);
      }
      if (b.ring && b.p.kind === "hq") {
        b.ring.children[0].rotation.z = now / 1400;
        b.ring.children[1].rotation.z = -now / 900;
        b.ring.position.y = b.h + 30 + Math.sin(now / 700) * 4;
      } else if (b.ring) {
        b.ring.rotation.x = Math.PI / 2 + Math.sin(now / 1100) * 0.4;
        b.ring.rotation.y = now / 1300;
      }
    }

    // Ultron: eye colour = verdict, pupil follows the latest signal
    const u = buildings.Ultron;
    if (u) {
      const iris = Z.done ? (Z.audit.ok ? C.green : C.red) : C.violet;
      u.eye.material.emissive.set(iris);
      u.pupil.material.color.set(iris);
      u.ring.material.color.set(iris);
      const t = fx.eyeTarget || { x: u.p.x, y: u.p.y + 200 };
      const a = Math.atan2(wz(t.y) - wz(u.p.y), wx(t.x) - wx(u.p.x));
      u.pupil.position.set(Math.cos(a) * 15, u.eye.position.y, Math.sin(a) * 15);
    }

    // exchanges: bars from price history, level planes for an open position
    for (const e of exchanges) {
      const prices = (state.prices[e.ex.sym] || []).slice(-Z.SPARK_POINTS);
      const pos = Object.values(state.open).find((t) => t.symbol === e.ex.sym);
      let lo = Math.min(...prices), hi = Math.max(...prices);
      let target = null;
      if (pos) {
        target = pos.entry + (pos.entry - pos.stop_loss) * Z.meta.take_profit_rr;
        lo = Math.min(lo, pos.stop_loss); hi = Math.max(hi, target);
      }
      const span = hi - lo || 1;
      const Y = (v) => 10 + ((v - lo) / span) * 110;
      const step = (e.ex.w - 30) / Z.SPARK_POINTS;
      e.bars.count = prices.length;
      prices.forEach((v, i) => {
        const hgt = Y(v);
        dummy.position.set(e.cx - e.ex.w / 2 + 15 + step * (i + 0.5), hgt / 2 + 6, e.cz);
        dummy.scale.set(step * 0.7, hgt, 26);
        dummy.updateMatrix();
        e.bars.setMatrixAt(i, dummy.matrix);
        // dimmed so a wall of bars doesn't bloom into a white blob; the newest bar shines
        barColor.set(i && v < prices[i - 1] ? C.red : C.green).multiplyScalar(i === prices.length - 1 ? 1 : 0.35);
        e.bars.setColorAt(i, barColor);
      });
      e.bars.instanceMatrix.needsUpdate = true;
      if (e.bars.instanceColor) e.bars.instanceColor.needsUpdate = true;
      for (const [k, m] of Object.entries(e.levels)) {
        m.visible = !!pos;
        if (pos) m.position.y = Y(k === "target" ? target : k === "entry" ? pos.entry : pos.stop_loss) + 6;
      }
    }

    // signals flying between buildings, arcing over the roofs
    let n = 0;
    for (const p of fx.particles) {
      if (n >= MAX_PARTICLES) break;
      const t = Math.min(1, (now - p.t0) / p.dur);
      const q = Z.pointOn(p.pts, Z.ease(t));
      const orb = orbs[n++];
      orb.visible = true;
      orb.material.color.set(p.color);
      orb.scale.setScalar(p.size * 1.4);
      orb.position.set(wx(q.x), 30 + Math.sin(t * Math.PI) * 70, wz(q.y));
    }
    for (; n < MAX_PARTICLES && orbs[n].visible; n++) orbs[n].visible = false;

    composer.render();

    // labels, floating results and the day banner, drawn flat over the 3D scene
    octx.clearRect(0, 0, container.clientWidth, container.clientHeight);
    for (const [name, b] of Object.entries(buildings)) {
      let text = b.p.kind === "bank" ? `Treasury ${Z.money(state.startEquity + state.realized)}` : b.p.title;
      let color = b.p.kind === "tower" ? C.violet : C.text;
      if (Z.SCORED.includes(name)) {  // survival: health next to the name
        const life = Z.survival(name);
        color = Z.STATUS[life.status][1];
        text = `${life.status === "dying" ? "☠ " : ""}${text}${life.acc != null ? ` ${life.acc}%` : ""}`;
      }
      label(text, wx(b.p.x), b.h + (b.p.kind === "tower" ? 60 : b.p.kind === "bank" ? 45 : 18), wz(b.p.y),
            b.p.kind === "squad" ? 12 : 14, color);
    }
    for (const e of exchanges) {
      const prices = state.prices[e.ex.sym] || [];
      const last = prices[prices.length - 1];
      label(`${e.ex.sym} ${last != null ? last.toFixed(2) : ""}`, e.cx, 150, e.cz - e.ex.h * 0.35, 15, C.text, 700);
    }
    for (const f of fx.floats) {
      const t = (now - f.t0) / Z.FLOAT_LIFE;
      octx.globalAlpha = 1 - t * t;
      label(f.text, wx(f.x), 140 + t * 50, wz(f.y), 14, f.color, 700);
    }
    octx.globalAlpha = 1;
    if (fx.banner) {
      const t = (now - fx.banner.t0) / 2200;
      if (t < 1) {
        octx.globalAlpha = Math.sin(t * Math.PI) * 0.9;
        octx.font = `700 40px "Segoe UI", system-ui, sans-serif`;
        octx.textAlign = "center"; octx.fillStyle = "#e8eefc";
        octx.fillText(fx.banner.text, container.clientWidth / 2, 70);
        octx.globalAlpha = 1;
      }
    }
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
