// Pódio 1-2-3 em voxels com avatares pixel nas cores das equipas. Os nomes são etiquetas HTML nítidas por cima
// (nunca texto 3D) e, sem WebGL ou com prefers-reduced-motion, o pódio passa a blocos CSS (.podium--2d).
// mountPodium(el, top3 [{name, points, color_idx}], { theme }) -> { dispose() }
import { createStage, voxelMesh, rng, cssColor, disposeObject } from "./scene-base.js";
import { el as h } from "../components/dom.js";
import { medalImg } from "../components/medal.js";

const ORDER = [1, 0, 2]; // da esquerda para a direita: 2.º, 1.º, 3.º
const HEIGHT = [4, 3, 2];
const teamVar = (i) => `--c-team-${(Number(i) || 0) % 8}`;

// Pontos no formato da língua da página (PT: 237,5 · EN: 237.5)
const fmt = (n) => new Intl.NumberFormat(document.documentElement.lang || "pt-PT", { maximumFractionDigits: 1 }).format(n);

function labels(host, top3) {
  return top3.slice(0, 3).map((p, rank) => {
    const lab = h("div", { class: "podium-label" },
      medalImg(rank + 1, { size: 64, cls: "medal medal--pod mx-auto" }), h("b", {}, `#${rank + 1}`), h("span", {}, String(p.name ?? "")), h("small", { class: "block text-muted" }, p.points == null ? "" : fmt(p.points)));
    lab.style.setProperty("--blk", `var(${teamVar(p.color_idx)})`);
    lab.style.setProperty("--h", `${28 + HEIGHT[rank] * 14}px`);
    return lab;
  });
}

export async function mountPodium(el, top3 = [], { theme } = {}) {
  el.classList.add("podium");
  el.replaceChildren();
  const labs = labels(el, top3);
  const slots = ORDER.filter((r) => r < labs.length);
  const to2d = () => { // reserva 2D: blocos CSS com as mesmas etiquetas
    el.classList.add("podium--2d");
    labs.forEach((l) => { l.style.left = ""; l.style.top = ""; });
    el.replaceChildren(...slots.map((r) => labs[r]));
  };
  const stage = await createStage(el, { fov: 28, onDegrade: to2d });
  if (!stage) {
    to2d();
    return { dispose() { el.replaceChildren(); el.classList.remove("podium", "podium--2d"); } };
  }
  const { THREE, scene, camera } = stage;
  scene.add(new THREE.AmbientLight(0xffffff, 1.6));
  const sun = new THREE.DirectionalLight(0xffffff, 2.2); sun.position.set(6, 12, 8); scene.add(sun);

  const vox = [], rand = rng(42), tops = [];
  const stone = Number.parseInt(cssColor("--c-surface-3").slice(1), 16) || 0x888888;
  slots.forEach((rank, slot) => {
    const cx = (slot - 1) * 5, hgt = HEIGHT[rank], team = new THREE.Color(cssColor(teamVar(top3[rank].color_idx))).getHex();
    for (let x = -1; x <= 1; x++) for (let z = -1; z <= 1; z++) {
      for (let y = 0; y < hgt; y++) vox.push(cx + x, y, z, y === hgt - 1 ? [0xffd23f, 0xc4863a, 0xd9573b][rank] : stone);
    }
    // avatar: pernas, corpo na cor da equipa, cabeça, cabelo; o 1.º leva coroa
    const y0 = hgt;
    vox.push(cx - 0.5, y0, 0, 0x3a2a4a, cx + 0.5, y0, 0, 0x3a2a4a);
    for (let y = 1; y <= 2; y++) vox.push(cx, y0 + y, 0, team, cx - 1, y0 + y, 0, team, cx + 1, y0 + y, 0, team);
    vox.push(cx, y0 + 3, 0, 0xf6cda3, cx, y0 + 4, 0, 0xf6cda3, cx, y0 + 5, 0, 0x5e3a20);
    if (rank === 0) vox.push(cx - 1, y0 + 5, 0, 0xffd23f, cx, y0 + 6, 0, 0xffd23f, cx + 1, y0 + 5, 0, 0xffd23f);
    tops.push({ rank, p: new THREE.Vector3(cx, y0 + 7.6, 0) });
  });
  scene.add(voxelMesh(THREE, vox, { seed: 3, size: 1 }));

  // confete: cubos coloridos a cair em ciclo
  const colors = [cssColor("--c-accent"), cssColor("--c-accent-2"), cssColor("--c-gold"), cssColor("--c-team-0"), cssColor("--c-team-5")];
  const N = 40, conf = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshBasicMaterial(), N);
  const C = [], m4 = new THREE.Matrix4(), col = new THREE.Color();
  for (let i = 0; i < N; i++) { C.push({ x: (rand() - 0.5) * 14, y: rand() * 14, z: (rand() - 0.5) * 6, s: 0.6 + rand() }); conf.setColorAt(i, col.set(colors[i % colors.length])); }
  conf.frustumCulled = false; scene.add(conf);

  const v = new THREE.Vector3();
  const place = () => {
    const r = el.getBoundingClientRect();
    for (const { rank, p } of tops) {
      v.copy(p).project(camera);
      const lab = labs[rank];
      lab.style.left = `${(v.x * 0.5 + 0.5) * r.width}px`;
      lab.style.top = `${(-v.y * 0.5 + 0.5) * r.height}px`;
    }
  };
  el.append(...labs);
  let dist = 32; // distância da câmara: o pódio tem de caber na largura e na altura (com folga para as etiquetas)
  stage.onResize((aspect) => { dist = Math.max(34, 17 / (0.4986 * aspect)); camera.position.set(0, 10, dist); camera.lookAt(0, 8.2, 0); camera.updateMatrixWorld(); place(); });
  stage.onFrame((dt, t) => {
    for (let i = 0; i < N; i++) {
      const c = C[i]; c.y -= dt * 3 * c.s; if (c.y < -1) c.y = 14;
      m4.makeScale(0.25, 0.25, 0.25); m4.setPosition(c.x + Math.sin(t * 2 + i) * 0.3, c.y, c.z); conf.setMatrixAt(i, m4);
    }
    conf.instanceMatrix.needsUpdate = true;
    const a = Math.sin(t * 0.35) * 0.22;
    camera.position.set(Math.sin(a) * dist, 10, Math.cos(a) * dist); camera.lookAt(0, 8.2, 0); camera.updateMatrixWorld();
    place();
  });
  return { dispose() { stage.dispose(); el.replaceChildren(); el.classList.remove("podium", "podium--2d"); } };
}
