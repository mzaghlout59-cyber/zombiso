// Zombiso AI City in 3D (three.js). Reads the same state and effects as the 2D view
// through the handles city.js passes in (Z), so both views always show the same city.
// The 2D map's (x, y) becomes the ground plane: world X = x - 600, world Z = y - 360.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const HEIGHT = { squad: 45, commander: 85, hq: 140, gate: 80, tower: 230, bank: 55 };
const MAX_PARTICLES = 300;

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
  scene.fog = new THREE.Fog(0x070b16, 1600, 3200);
  const camera = new THREE.PerspectiveCamera(42, 1, 10, 6000);
  camera.position.set(0, 640, 780);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 0, -20);  // between the buildings (back) and the exchanges (front)
  controls.enableDamping = true;
  controls.maxPolarAngle = Math.PI * 0.47;   // never go under the ground
  controls.minDistance = 300;
  controls.maxDistance = 2600;

  // ---------- light: the sun follows the city clock ----------
  const hemi = new THREE.HemisphereLight(0x9fb4ff, 0x0b1020, 0.6);
  const sun = new THREE.DirectionalLight(0xffe2b0, 1.2);
  scene.add(hemi, sun, new THREE.AmbientLight(0x404a70, 0.35));

  // ---------- ground and roads ----------
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(2600, 1800),
    new THREE.MeshStandardMaterial({ color: 0x0d1428, roughness: 1 }));
  ground.rotation.x = -Math.PI / 2;
  scene.add(ground);

  const roadMat = new THREE.MeshStandardMaterial({ color: 0x1b2747, roughness: 0.9 });
  for (const [pts, width] of Z.roadPaths()) {
    for (let i = 1; i < pts.length; i++) {
      const a = pts[i - 1], b = pts[i];
      const len = Math.hypot(b.x - a.x, b.y - a.y);
      if (len < 1) continue;
      const seg = new THREE.Mesh(new THREE.BoxGeometry(len + width, 1, width * 1.6), roadMat);
      seg.position.set(wx((a.x + b.x) / 2), 0.6, wz((a.y + b.y) / 2));
      seg.rotation.y = -Math.atan2(b.y - a.y, b.x - a.x);
      scene.add(seg);
    }
  }

  // ---------- buildings ----------
  const buildings = {};
  for (const [name, p] of Object.entries(Z.PLACES)) {
    const h = HEIGHT[p.kind] || 50;
    const color = p.kind === "hq" ? 0x2a2f4a : p.kind === "bank" ? 0x2b2a22 : 0x18233f;
    const mat = new THREE.MeshStandardMaterial({ color, roughness: 0.55, metalness: 0.25, emissive: 0x000000 });
    const group = new THREE.Group();
    let body;
    if (p.kind === "gate") {
      body = new THREE.Mesh(new THREE.CylinderGeometry(p.w / 2, p.w / 2.6, h, 6), mat);
    } else if (p.kind === "tower") {
      body = new THREE.Mesh(new THREE.BoxGeometry(p.w * 0.45, h, p.w * 0.45), mat);
    } else {
      body = new THREE.Mesh(new THREE.BoxGeometry(p.w, h, p.h * 0.9), mat);
    }
    body.position.y = h / 2;
    group.add(body);
    if (p.kind === "bank") {  // a triangular pediment roof
      const roof = new THREE.Mesh(new THREE.CylinderGeometry(p.h * 0.55, p.h * 0.55, p.w + 12, 3),
        new THREE.MeshStandardMaterial({ color: 0x8a6a2a, roughness: 0.6, metalness: 0.4 }));
      roof.rotation.z = Math.PI / 2;
      roof.position.y = h + p.h * 0.25;
      group.add(roof);
    }
    let eye = null, pupil = null;
    if (p.kind === "tower") {  // Ultron's eye
      eye = new THREE.Mesh(new THREE.SphereGeometry(20, 24, 16),
        new THREE.MeshStandardMaterial({ color: 0x111827, emissive: 0xa78bfa, emissiveIntensity: 0.5 }));
      eye.position.y = h + 18;
      pupil = new THREE.Mesh(new THREE.SphereGeometry(7, 16, 12), new THREE.MeshBasicMaterial({ color: 0xa78bfa }));
      group.add(eye, pupil);
    }
    group.position.set(wx(p.x), 0, wz(p.y));
    scene.add(group);
    buildings[name] = { group, mat, h, p, eye, pupil };
  }

  // ---------- exchanges: platforms with 3D price bars ----------
  const exchanges = Z.exchanges().map((ex) => {
    const cx = wx(ex.x + ex.w / 2), cz = wz(ex.y + ex.h / 2);
    const base = new THREE.Mesh(new THREE.BoxGeometry(ex.w, 6, ex.h * 0.8),
      new THREE.MeshStandardMaterial({ color: 0x111a33, roughness: 0.8 }));
    base.position.set(cx, 3, cz);
    scene.add(base);
    const bars = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1),
      new THREE.MeshStandardMaterial({ roughness: 0.5, metalness: 0.1 }), Z.SPARK_POINTS);
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

  // ---------- sizing ----------
  function resize() {
    const w = container.clientWidth, h = container.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
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
  const night = new THREE.Color(0x060914), day = new THREE.Color(0x1d3460);
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
    octx.font = `${weight} ${size}px "Segoe UI", system-ui, sans-serif`;
    octx.textAlign = "center"; octx.textBaseline = "middle";
    octx.lineWidth = 3; octx.strokeStyle = "rgba(5,8,18,0.85)";
    octx.strokeText(text, s.x, s.y);
    octx.fillStyle = color; octx.fillText(text, s.x, s.y);
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
    sun.intensity = 0.15 + light * 1.2;
    hemi.intensity = 0.35 + light * 0.4;

    // buildings glow when their worker acts; HQ windows light up at night
    for (const [name, b] of Object.entries(buildings)) {
      const g = fx.glows[name];
      if (g && now < g.until) {
        b.mat.emissive.set(g.color);
        b.mat.emissiveIntensity = 0.25 + 0.9 * Math.min(1, (g.until - now) / 700);
      } else if (b.p.kind === "hq") {
        b.mat.emissive.set(C.gold);
        b.mat.emissiveIntensity = Math.max(0, 0.35 - light * 0.35);
      } else {
        b.mat.emissiveIntensity = 0;
      }
    }

    // Ultron: eye colour = verdict, pupil follows the latest signal
    const u = buildings.Ultron;
    if (u) {
      const iris = Z.done ? (Z.audit.ok ? C.green : C.red) : C.violet;
      u.eye.material.emissive.set(iris);
      u.pupil.material.color.set(iris);
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
        e.bars.setColorAt(i, barColor.set(i && v < prices[i - 1] ? C.red : C.green));
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

    renderer.render(scene, camera);

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
    controls.dispose();
    renderer.dispose();
    container.textContent = "";
  }

  return { render, resize, dispose };
}
