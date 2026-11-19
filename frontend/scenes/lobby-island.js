// Ilha flutuante de voxels do ecrã inicial: um bioma por tema, câmara a rodar devagar, nuvens e partículas.
// mountLobby(el, { theme }) -> { dispose(), setTheme(theme) }. Tudo é carregado depois do primeiro pixel (import dinâmico).
import { createStage, voxelMesh, disposeObject, rng } from "./scene-base.js";
import { sceneFor } from "./themes.js";

const R = 8; // raio da ilha em voxels

// ---- construção do bioma (devolve voxels estáticos + objetos animados) ----
function buildBiome(theme) {
  const cfg = sceneFor(theme), rand = rng(theme.length * 977 + theme.charCodeAt(0));
  const vox = [], anim = [];
  const put = (x, y, z, c) => vox.push(x, y, z, c);
  const land = new Set(); // colunas com terra
  const surf = (x, z) => (surfH.get(x + "," + z) ?? 0);
  const surfH = new Map();
  const ocean = cfg.biome === "ocean" || cfg.biome === "tropic", radius = cfg.biome === "ocean" ? 5.2 : cfg.biome === "tropic" ? 6.4 : R;

  // terreno: topo, camada lateral e fundo em cone invertido (ilha flutuante)
  for (let x = -R; x <= R; x++) for (let z = -R; z <= R; z++) {
    const d = Math.hypot(x, z), edge = radius - rand() * 1.4;
    if (d > edge) continue;
    land.add(x + "," + z);
    let h = 0;
    if (cfg.biome === "desert") h = Math.round(1.6 * Math.sin(x * 0.55) * Math.cos(z * 0.45) + 0.8);
    surfH.set(x + "," + z, h);
    for (let y = 0; y <= h; y++) put(x, y, z, y === h ? cfg.top : cfg.side);
    const depth = Math.round((edge - d) * 1.25) + 2;
    for (let k = 1; k <= depth; k++) put(x, -k, z, k === 1 ? cfg.side : rand() < 0.25 ? cfg.side : cfg.deep);
  }
  const free = () => { // posição de terra livre, afastada da borda
    for (let i = 0; i < 40; i++) {
      const x = Math.round((rand() - 0.5) * 2 * (radius - 2)), z = Math.round((rand() - 0.5) * 2 * (radius - 2));
      if (land.has(x + "," + z) && Math.hypot(x, z) < radius - 1.6) return [x, z];
    }
    return [0, 0];
  };
  const blob = (cx, cy, cz, r, c, c2) => {
    for (let x = -r; x <= r; x++) for (let y = -r; y <= r; y++) for (let z = -r; z <= r; z++)
      if (x * x + y * y + z * z <= r * r + 0.5) put(cx + x, cy + y, cz + z, rand() < 0.3 && c2 ? c2 : c);
  };
  const tree = (x, z, leaf, leaf2, trunk = 0x6b4423, tall = 3) => {
    const h = surf(x, z);
    for (let i = 1; i <= tall; i++) put(x, h + i, z, trunk);
    blob(x, h + tall + 1, z, 2, leaf, leaf2);
  };
  const pine = (x, z, c, snow) => {
    const h = surf(x, z);
    put(x, h + 1, z, 0x6b4423);
    for (let i = 0; i < 4; i++) { const r = i < 3 ? 2 - Math.floor(i / 2) : 0; for (let dx = -r; dx <= r; dx++) for (let dz = -r; dz <= r; dz++) if (Math.abs(dx) + Math.abs(dz) <= r + 1) put(x + dx, h + 2 + i, z + dz, i === 3 && snow ? snow : c); }
  };
  const tower = (x, z, hgt, c, c2) => {
    const h = surf(x, z);
    for (let y = 1; y <= hgt; y++) for (let dx = -1; dx <= 1; dx++) for (let dz = -1; dz <= 1; dz++) put(x + dx, h + y, z + dz, (y + dx) % 2 ? c : c2);
    for (const [dx, dz] of [[-1, -1], [1, -1], [-1, 1], [1, 1], [0, -1], [0, 1]]) put(x + dx, h + hgt + 1, z + dz, c);
    put(x, h + hgt - 2, z + 2, 0xffc94d); // janela acesa
  };

  switch (cfg.biome) {
    case "forest": {
      for (let i = 0; i < 7; i++) { const [x, z] = free(); if (Math.hypot(x, z) > 2.5) tree(x, z, 0x2e8f3a, 0x45b04c, 0x6b4423, 2); }
      for (let x = -1; x <= 1; x++) for (let z = -1; z <= 1; z++) { for (let y = 1; y <= 2; y++) put(x, y, z, 0xe8d8b8); }
      for (let x = -2; x <= 2; x++) for (let z = -2; z <= 2; z++) put(x, 3, z, 0xc8503c);
      put(0, 4, 0, 0xc8503c); put(0, 1, 2, 0x6b4423); put(0, 2, 2, 0x6b4423);
      for (let i = 0; i < 6; i++) { const [x, z] = free(); put(x, surf(x, z) + 1, z, [0xff6b9a, 0xffe14d, 0xffffff][i % 3]); } // flores
      break;
    }
    case "dungeon": {
      tower(-4, -3, 7, 0x9a97b4, 0x8a87a4); tower(4, 3, 9, 0x9a97b4, 0x8a87a4);
      for (let x = -3; x <= 3; x++) for (let y = 1; y <= 3; y++) { put(x, y, 4 - (x > 1 ? 0 : 0), 0x6c698a); }
      for (let y = 1; y <= 2; y++) put(0, y, 4, 0x16141f); // portão
      for (const [x, z] of [[-2, 2], [2, -2], [-1, -4]]) { put(x, 1, z, 0x56536c); put(x, 2, z, 0xff9a3c); anim.push({ kind: "torch", x, y: 2, z }); }
      for (let i = 0; i < 3; i++) { const [x, z] = free(); put(x, surf(x, z) + 1, z, 0x56536c); }
      break;
    }
    case "ocean": {
      tree(0, 0, 0x3fb34a, 0x2f9a3c, 0x8a5a33, 4); tree(2, 1, 0x3fb34a, null, 0x8a5a33, 3);
      for (let i = 0; i < 4; i++) { const [x, z] = free(); put(x, surf(x, z) + 1, z, i % 2 ? 0xff7a8a : 0xffffff); }
      anim.push({ kind: "boat", r: 7.5, sp: 0.35, ph: 0 }, { kind: "boat", r: 9.8, sp: -0.22, ph: 2.4 });
      anim.push({ kind: "water" });
      break;
    }
    case "tropic": {
      const palm = (x, z, tall, lean) => { // tronco inclinado e folhas em cruz, a cair nas pontas
        const h = surf(x, z);
        for (let i = 1; i <= tall; i++) put(x + Math.round((lean * i) / tall), h + i, z, 0x6a3a50);
        const tx = x + lean, ty = h + tall + 1;
        put(tx, ty, z, 0x1f8f7a);
        for (const [dx, dz] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) for (let k = 1; k <= 3; k++) put(tx + dx * k, ty - (k === 3 ? 1 : 0), z + dz * k, k === 2 ? 0x2bb39a : 0x1f8f7a);
      };
      palm(-4, 2, 6, -1); palm(-2, 4, 4, 1); palm(4, -3, 5, 1);
      for (let x = 0; x <= 4; x++) for (let z = 0; z <= 2; z++) for (let y = 1; y <= 5; y++) { // hotel de praia
        const wall = x === 0 || x === 4 || z === 0 || z === 2;
        if (wall) put(x - 2, y, z - 3, y === 3 ? 0xff5c93 : (y % 2 === 0 && x % 2 === 1 && z === 2) ? 0xffcf5a : 0xffd9c7);
      }
      for (let x = -1; x <= 5; x++) for (let z = -1; z <= 3; z++) put(x - 2, 6, z - 3, 0x3fe6d4);
      for (let y = 1; y <= 2; y++) put(3, y, 3, 0xfff3e8); // chapéu de praia
      for (const [dx, dz] of [[0, 0], [1, 0], [-1, 0], [0, 1], [0, -1]]) put(3 + dx, 3, 3 + dz, (dx + dz) % 2 ? 0xff5c93 : 0xfff3e8);
      anim.push({ kind: "boat", r: 8.6, sp: 0.3, ph: 1 }, { kind: "water" }, { kind: "sunset" });
      break;
    }
    case "desert": {
      for (const [x, z, h] of [[-4, 2, 3], [3, -3, 2], [-2, -4, 2]]) {
        const y0 = surf(x, z);
        for (let i = 1; i <= h + 1; i++) put(x, y0 + i, z, 0x2e8f3a);
        put(x - 1, y0 + 2, z, 0x2e8f3a); put(x - 1, y0 + 3, z, 0x2e8f3a); put(x + 1, y0 + 3, z, 0x2e8f3a); put(x + 1, y0 + 4, z, 0x2e8f3a);
      }
      for (let k = 0; k < 4; k++) for (let x = -k; x <= k; x++) for (let z = -k; z <= k; z++) put(4 + x, surf(4, 3) + 4 - k + 0, 3 + z, 0xd9a24e); // pirâmide
      put(4, surf(4, 3) + 5, 3, 0xffd23f);
      break;
    }
    case "snow": {
      for (const [x, z, hh] of [[-2, -2, 7], [2, -3, 5], [3, 2, 4]]) {
        const y0 = surf(x, z);
        for (let k = 0; k < hh; k++) { const r = Math.floor((hh - k) / 2); for (let dx = -r; dx <= r; dx++) for (let dz = -r; dz <= r; dz++) if (Math.abs(dx) + Math.abs(dz) <= r + 1) put(x + dx, y0 + 1 + k, z + dz, k >= hh - 2 ? 0xffffff : 0xc8dcf2); }
      }
      for (let i = 0; i < 5; i++) { const [x, z] = free(); if (Math.hypot(x + 2, z + 2) > 3) pine(x, z, 0x3c7f6a, 0xffffff); }
      break;
    }
    case "night": {
      for (const [x, z] of [[-3, -2], [3, 3], [0, -4]]) for (let y = 1; y <= 2; y++) put(x, y, z, y === 2 ? 0x7a78e0 : 0x4a4890); // runas
      anim.push({ kind: "crystal", x: -3, y: 6, z: 1, c: 0x7af0ff, s: 1.5 }, { kind: "crystal", x: 3, y: 8, z: -2, c: 0xff7ad9, s: 1.2 }, { kind: "crystal", x: 0, y: 5.5, z: 3, c: 0xffe34d, s: 1.8 }, { kind: "crystal", x: -1, y: 9, z: -3, c: 0x7af0ff, s: 1 });
      anim.push({ kind: "stars" }, { kind: "moon" });
      break;
    }
  }
  return { cfg, vox, anim, radius };
}

export async function mountLobby(el, { theme, lift = 0 } = {}) { // lift: sobe a ilha no ecrã (home: o HUD tapa a parte de baixo)
  const stage = await createStage(el, { fov: 30, onDegrade: () => {} });
  if (!stage) return { dispose() {}, setTheme() {} }; // reserva 2D: o cartaz do CSS já está visível
  const { THREE, scene, camera } = stage;
  const world = new THREE.Group(), island = new THREE.Group(), tickers = [];
  scene.add(world); world.add(island);
  const amb = new THREE.AmbientLight(0xffffff, 1.5), sun = new THREE.DirectionalLight(0xffffff, 2.2);
  sun.position.set(8, 14, 6);
  scene.add(amb, sun);

  let current = null, currentName = "", camDist = 42, camRef = 1;
  stage.onResize((aspect) => { camRef = aspect; camDist = 42 * Math.max(1, 1.45 / aspect) ** 0.85; });

  function clearIsland() {
    tickers.length = 0;
    for (const ch of [...island.children]) { island.remove(ch); disposeObject(ch); }
  }

  function build(name) {
    clearIsland();
    const b = buildBiome(name);
    current = b; currentName = name;
    el.dataset.biome = b.cfg.biome;
    sun.color.setHex(b.cfg.sun); amb.color.setHex(b.cfg.amb);
    island.add(voxelMesh(THREE, b.vox, { seed: 7 }));
    const mk = (geo, color, basic = true) => new THREE.Mesh(geo, basic ? new THREE.MeshBasicMaterial({ color }) : new THREE.MeshLambertMaterial({ color }));
    const box = new THREE.BoxGeometry(1, 1, 1);

    // nuvens (blocos brancos a deslizar devagar)
    if (b.cfg.biome !== "night") {
      for (let i = 0; i < 5; i++) {
        const g = new THREE.Group(), n = 3 + (i % 3);
        for (let k = 0; k < n; k++) { const m = mk(box, b.cfg.cloud, false); m.scale.set(2 + (k % 2), 1, 1.6); m.position.set(k * 1.8 - n, (k % 2) * 0.6, 0); g.add(m); }
        const r0 = 15 + i * 1.5, a0 = (i / 5) * Math.PI * 2, y0 = 9 + (i % 3) * 2;
        g.position.set(Math.cos(a0) * r0, y0, Math.sin(a0) * r0);
        island.add(g);
        tickers.push((dt) => { const a = Math.atan2(g.position.z, g.position.x) + dt * 0.05; g.position.x = Math.cos(a) * r0; g.position.z = Math.sin(a) * r0; g.rotation.y = -a; });
      }
    }

    // partículas do tema
    const fx = b.cfg.fx, parts = new THREE.InstancedMesh(box, new THREE.MeshBasicMaterial({ color: fx.color }), fx.n);
    const pr = rng(99), P = [], m4 = new THREE.Matrix4();
    for (let i = 0; i < fx.n; i++) P.push({ x: (pr() - 0.5) * 22, y: pr() * 11 - 1, z: (pr() - 0.5) * 22, s: 0.5 + pr(), p: pr() * 6 });
    parts.frustumCulled = false;
    island.add(parts);
    tickers.push((dt, t) => {
      for (let i = 0; i < fx.n; i++) {
        const p = P[i];
        if (fx.kind === "fall") { p.y -= dt * 2 * p.s; p.x += Math.sin(t + p.p) * dt * 0.6; if (p.y < -2) p.y = 11; }
        else if (fx.kind === "rise") { p.y += dt * 1.6 * p.s; p.x += Math.sin(t * 2 + p.p) * dt * 0.5; if (p.y > 10) p.y = 0; }
        else if (fx.kind === "drift") { p.x += dt * 2.2 * p.s; if (p.x > 11) p.x = -11; }
        else { p.x += Math.sin(t * 0.7 + p.p) * dt * 0.8; p.y += Math.cos(t * 0.9 + p.p) * dt * 0.5; }
        const sc = fx.kind === "twinkle" ? 0.15 + 0.15 * (Math.floor(t * 3 + p.p) % 2) : 0.22;
        m4.makeScale(sc, sc, sc); m4.setPosition(p.x, p.y, p.z); parts.setMatrixAt(i, m4);
      }
      parts.instanceMatrix.needsUpdate = true;
    });

    // detalhes animados do bioma
    for (const a of b.anim) {
      if (a.kind === "torch") {
        const m = mk(box, 0xffdd66); m.scale.setScalar(0.6); m.position.set(a.x, a.y + 0.8, a.z); island.add(m);
        tickers.push((dt, t) => m.scale.setScalar(0.45 + 0.2 * (Math.floor(t * 6 + a.x) % 2)));
      } else if (a.kind === "crystal") {
        const m = mk(new THREE.OctahedronGeometry(a.s * 0.9), a.c); m.scale.y = 1.5; m.position.set(a.x, a.y, a.z); island.add(m);
        tickers.push((dt, t) => { m.rotation.y += dt * 1.1; m.position.y = a.y + Math.round(Math.sin(t * 1.5 + a.x) * 3) / 4; });
      } else if (a.kind === "moon") {
        const m = mk(new THREE.SphereGeometry(3.2, 8, 6), 0xfff6c8); m.position.set(-16, 14, -14); island.add(m);
      } else if (a.kind === "sunset") { // sol às riscas, parado ao fundo: bandas de voxels, sem luz nem brilho
        const R0 = 7, g = new THREE.Group();
        for (let y = -R0; y <= R0; y++) {
          if (y < -1 && (-y) % 3 === 0) continue;
          const w = 2 * Math.sqrt(R0 * R0 - y * y), f = (y + R0) / (2 * R0);
          const c = new THREE.Color(0xff4f8b).lerp(new THREE.Color(0xffe36b), f);
          const m = mk(box, c.getHex()); m.scale.set(Math.max(1, w), 1, 1); m.position.y = y; g.add(m);
        }
        g.position.set(-15, 6, -24); g.rotation.y = 0.55; island.add(g);
      } else if (a.kind === "stars") {
        const sp = new Float32Array(90), sr = rng(5);
        for (let i = 0; i < 30; i++) { const th = sr() * 6.28, ph = Math.acos(sr() * 1.2 - 0.2), r = 40; sp[i * 3] = r * Math.sin(ph) * Math.cos(th); sp[i * 3 + 1] = r * Math.cos(ph) * 0.9 + 4; sp[i * 3 + 2] = r * Math.sin(ph) * Math.sin(th); }
        const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(sp, 3));
        const pts = new THREE.Points(g, new THREE.PointsMaterial({ color: 0xffffff, size: 2, sizeAttenuation: false })); pts.frustumCulled = false; island.add(pts);
      } else if (a.kind === "water") {
        const N = 17, wm = new THREE.InstancedMesh(box, new THREE.MeshLambertMaterial({ color: 0xffffff }), N * N);
        const col = new THREE.Color(), pos = [];
        let n = 0;
        for (let x = -8; x <= 8; x++) for (let z = -8; z <= 8; z++) {
          const d = Math.hypot(x, z); if (d < 3.6 || d > 8.2) continue;
          pos.push([x * 1.35, z * 1.35]); col.setHex((x + z) & 1 ? (b.cfg.water?.[0] ?? 0x1f7fc0) : (b.cfg.water?.[1] ?? 0x2a90d6)); wm.setColorAt(n++, col);
        }
        wm.count = n; wm.frustumCulled = false; island.add(wm);
        tickers.push((dt, t) => {
          for (let i = 0; i < n; i++) { m4.makeScale(1.35, 0.6, 1.35); m4.setPosition(pos[i][0], -1.2 + Math.round(Math.sin(t * 1.8 + pos[i][0] * 0.7 + pos[i][1] * 0.5) * 2) / 5, pos[i][1]); wm.setMatrixAt(i, m4); }
          wm.instanceMatrix.needsUpdate = true;
        });
      } else if (a.kind === "boat") {
        const g = new THREE.Group();
        const hull = mk(box, 0x8a5a33, false); hull.scale.set(2.4, 0.7, 1.2); g.add(hull);
        const mast = mk(box, 0x5e3a20, false); mast.scale.set(0.2, 2.6, 0.2); mast.position.y = 1.6; g.add(mast);
        const sail = mk(box, 0xffffff, false); sail.scale.set(0.15, 1.8, 1.5); sail.position.set(0, 1.8, 0.6); g.add(sail);
        island.add(g);
        tickers.push((dt, t) => { const ang = a.ph + t * a.sp; g.position.set(Math.cos(ang) * a.r, -0.9 + Math.round(Math.sin(t * 2 + a.ph) * 2) / 6, Math.sin(ang) * a.r); g.rotation.y = -ang + (a.sp > 0 ? 0 : Math.PI); });
      }
    }
  }

  build(theme || document.documentElement.dataset.theme);
  stage.onFrame((dt, t) => {
    tickers.forEach((f) => f(dt, t));
    island.position.y = Math.round(Math.sin(t * 0.8) * 4) / 6; // flutua em degraus
    const ang = t * 0.12 + 0.6;
    camera.position.set(Math.cos(ang) * camDist, camDist * 0.42, Math.sin(ang) * camDist);
    camera.lookAt(0, (camRef < 1 ? 3 : 2.2) - lift, 0);
  });

  return {
    setTheme(name) { if (name && name !== currentName) build(name); },
    dispose: stage.dispose,
  };
}
