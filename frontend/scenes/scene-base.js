// Base comum das cenas 3D: carrega o three.js só quando é preciso e cria um "palco" pixelizado e leve.
// - renderiza a baixa resolução (cada "pixel" tem 2 a 4 px de ecrã) e o CSS amplia com image-rendering: pixelated
// - limita a 30 fps, pausa com o separador escondido ou fora do ecrã, liberta tudo no dispose()
// - se o WebGL não existir, se houver prefers-reduced-motion ou se ficar lento (> 33 ms durante 2 s) devolve null/degrada
//   para o cartaz 2D (CSS) que já está por baixo, por isso nunca fica um buraco.
let threePromise = null;
export const loadThree = () => (threePromise ||= import("/vendor/three/three.module.min.js"));

export const prefersReducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

export function webglAvailable() {
  try {
    const c = document.createElement("canvas");
    return !!(window.WebGLRenderingContext && (c.getContext("webgl2") || c.getContext("webgl")));
  } catch (_) { return false; }
}

// Lê uma variável CSS de cor (ex.: "--c-team-3") do tema atual
export const cssColor = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#ffffff";

// Gerador pseudo-aleatório determinístico (as ilhas ficam sempre iguais para o mesmo tema)
export function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Lista de voxels -> um único InstancedMesh (1 draw call). voxels = [x, y, z, 0xRRGGBB, x, y, z, ...]
export function voxelMesh(THREE, voxels, { basic = false, jitter = 0.06, seed = 1, size = 1 } = {}) {
  const n = voxels.length / 4;
  const mat = basic ? new THREE.MeshBasicMaterial() : new THREE.MeshLambertMaterial();
  const mesh = new THREE.InstancedMesh(new THREE.BoxGeometry(size, size, size), mat, Math.max(1, n));
  const m = new THREE.Matrix4(), c = new THREE.Color(), r = rng(seed);
  for (let i = 0; i < n; i++) {
    m.makeTranslation(voxels[i * 4], voxels[i * 4 + 1], voxels[i * 4 + 2]);
    mesh.setMatrixAt(i, m);
    c.setHex(voxels[i * 4 + 3]).multiplyScalar(1 - jitter + r() * jitter * 2);
    mesh.setColorAt(i, c);
  }
  mesh.count = n;
  mesh.instanceMatrix.needsUpdate = true;
  if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  return mesh;
}

export function disposeObject(obj) {
  obj.traverse((o) => {
    o.geometry?.dispose?.();
    const mats = Array.isArray(o.material) ? o.material : o.material ? [o.material] : [];
    mats.forEach((mt) => { mt.map?.dispose?.(); mt.dispose(); });
    o.dispose?.(); // InstancedMesh
  });
}

// Tamanho de "pixel de cena" em px de ecrã: 2 em ecrãs pequenos, até 4 em ecrãs grandes
const pixelSize = (w) => Math.min(4, Math.max(2, Math.round(w / 300)));

// Cria o palco. Devolve null se não for possível (WebGL em falta, movimento reduzido, erro).
// opts: { fps = 30, fov = 32, onDegrade() }
export async function createStage(host, opts = {}) {
  const { fps = 30, fov = 32, onDegrade } = opts;
  if (prefersReducedMotion() || !webglAvailable()) return null;
  let THREE;
  try { THREE = await loadThree(); } catch (_) { return null; }

  const canvas = document.createElement("canvas");
  canvas.setAttribute("aria-hidden", "true");
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: true, powerPreference: "low-power", stencil: false });
  } catch (_) { return null; }
  renderer.setPixelRatio(1); // DPR fixo: a resolução interna é pequena de propósito
  renderer.setClearColor(0x000000, 0);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(fov, 16 / 9, 0.1, 200);
  host.prepend(canvas);

  // (para depurar em máquinas lentas: localStorage["pyarena.scene.nodegrade"] = "1" desliga a autodegradação)
  let monitor = true;
  try { monitor = !localStorage.getItem("pyarena.scene.nodegrade"); } catch (_) { /* ignora */ }
  const frameCbs = [], resizeCbs = [];
  let raf = 0, running = false, inView = true, disposed = false, first = true;
  let acc = 0, prevNow = 0, clock = 0;
  let winStart = 0, winFrames = 0, winRaf = 0, winCpu = 0; // monitor de desempenho

  function resize() {
    const r = host.getBoundingClientRect();
    const w = Math.max(1, r.width), h = Math.max(1, r.height), px = pixelSize(w);
    renderer.setSize(Math.max(48, Math.round(w / px)), Math.max(32, Math.round(h / px)), false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    resizeCbs.forEach((f) => f(w / h));
  }
  const ro = new ResizeObserver(resize);
  ro.observe(host);
  resize();

  function tick(now) {
    raf = requestAnimationFrame(tick);
    const dt = prevNow ? now - prevNow : 16;
    prevNow = now;
    // monitor: janelas de 2 s depois de 1 s de aquecimento (a compilação dos shaders não conta)
    if (!winStart) winStart = now + 1000;
    if (now >= winStart) { winFrames++; winRaf += dt; }
    acc += dt;
    const step = 1000 / fps;
    if (acc < step - 2) return;
    const dtSec = Math.min(acc, 100) / 1000;
    acc = 0;
    clock += dtSec;
    const t0 = performance.now();
    frameCbs.forEach((f) => f(dtSec, clock));
    renderer.render(scene, camera);
    if (now >= winStart) winCpu += performance.now() - t0;
    if (first) { first = false; host.classList.add("is-3d"); }
    if (monitor && now - winStart > 2000 && winFrames) {
      const avgRaf = winRaf / winFrames, avgCpu = winCpu / Math.max(1, winFrames / 2);
      if (avgRaf > 36 || avgCpu > 33) { degrade(); return; }
      winStart = now; winFrames = 0; winRaf = 0; winCpu = 0;
    }
  }
  function sync() {
    const should = !disposed && inView && document.visibilityState === "visible";
    if (should && !running) { running = true; prevNow = 0; acc = 0; winStart = 0; winFrames = 0; winRaf = 0; winCpu = 0; raf = requestAnimationFrame(tick); }
    else if (!should && running) { running = false; cancelAnimationFrame(raf); }
  }
  const io = new IntersectionObserver((es) => { inView = es[es.length - 1].isIntersecting; sync(); });
  io.observe(host);
  document.addEventListener("visibilitychange", sync);

  function dispose() {
    if (disposed) return;
    disposed = true;
    sync();
    document.removeEventListener("visibilitychange", sync);
    io.disconnect();
    ro.disconnect();
    disposeObject(scene);
    scene.clear();
    renderer.dispose();
    renderer.forceContextLoss?.();
    canvas.remove();
    host.classList.remove("is-3d");
  }
  function degrade() {
    dispose();
    host.classList.add("is-2d");
    onDegrade?.();
  }

  sync();
  return {
    THREE, scene, camera, renderer, canvas, dispose,
    onFrame: (f) => frameCbs.push(f),
    onResize: (f) => { resizeCbs.push(f); f(camera.aspect); },
  };
}
