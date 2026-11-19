// Campus do Politécnico de Tomar em voxels pixelizados: cenário principal da homepage e hub dos modos de jogo.
// A geometria nasce em código de layout.json (planta simplificada do mapa do campus): edifícios de tijolo com colunatas
// brancas, relvados, calçada, lago, campo, estrada e rotunda, árvores, candeeiros, bancos, passadiço e pessoas.
// mountCampus(el, { theme, onHotspot }) -> { dispose(), setTheme(theme), focus(hotspotId) }
// Os "hotspots" (edifícios-porta) são botões HTML posicionados por cima (nunca texto 3D): funcionam com teclado,
// rato e toque e também sobre o cartaz 2D (sem WebGL, movimento reduzido ou autodegradação).
import { createStage, rng, disposeObject } from "../scene-base.js";
import { el } from "../../components/dom.js";
import { t } from "../../services/i18n.js";

let layoutP = null;
const loadLayout = () => (layoutP ||= fetch("/scenes/campus/layout.json").then((r) => r.json()));

// ---------- hotspots (HTML) ----------
function buildHotspots(host, L, { onHotspot, isTeacher }) {
  const spots = L.hotspots;
  const nav = el("nav", { class: "campus-hs", "aria-label": t("campus.name") });
  const card = el("div", { class: "campus-confirm", role: "dialog", "aria-live": "polite", hidden: true });
  const items = new Map();
  let active = null;
  const touchMode = () => matchMedia("(hover: none)").matches;
  const setActive = (id) => {
    active = id;
    items.forEach((it, key) => it.btn.classList.toggle("is-active", key === id));
    api.onActive?.(id);
  };
  const go = (h) => { if (h.soon) return; if (onHotspot) onHotspot(h); else location.assign(h.url); };
  spots.forEach((h) => {
    const label = t(h.key);
    const btn = el("button", { type: "button", class: `campus-hs__btn${h.soon ? " is-soon" : ""}`, "data-id": h.id, "aria-label": h.soon ? `${label} (${t("campus.soon")})` : label },
      el("img", { class: "sprite", src: `/assets/sprites/${h.icon === "m1" ? "academy" : "icons"}/${h.icon}.png`, width: 24, height: 24, alt: "" }),
      el("span", {}, label), h.soon ? el("small", {}, t("campus.soon")) : null);
    btn.addEventListener("pointerenter", () => setActive(h.id));
    btn.addEventListener("pointerleave", () => { if (document.activeElement !== btn) setActive(null); });
    btn.addEventListener("focus", () => setActive(h.id));
    btn.addEventListener("blur", () => setActive(null));
    btn.addEventListener("click", () => {
      if (touchMode() && !h.soon) { // toque: 1.º toque mostra o cartão de confirmação
        setActive(h.id);
        card.replaceChildren(el("b", {}, t("campus.confirm", { name: label })), el("button", { type: "button", class: "btn-pixel btn-pixel--accent", onclick: () => go(h) }, t("campus.go")), el("button", { type: "button", class: "btn-pixel btn-pixel--ghost", onclick: () => { card.hidden = true; setActive(null); } }, t("campus.cancel")));
        card.hidden = false;
      } else go(h);
    });
    items.set(h.id, { btn, h });
    nav.append(btn);
  });
  host.append(nav, card);
  const refresh = () => items.forEach(({ btn, h }) => { btn.hidden = !!h.teacher && !isTeacher(); }); // o painel do professor só aparece para professores
  refresh();
  const api = { nav, items, spots, setActive, refresh, onActive: null, destroy() { nav.remove(); card.remove(); } };
  return api;
}

// ---------- geometria: caixas fundidas numa só malha por material ----------
class Batch {
  constructor(THREE) { this.T = THREE; this.p = []; this.n = []; this.u = []; this.c = []; this.i = []; this.col = new THREE.Color(); }
  // caixa alinhada aos eixos (sem a face de baixo). tile = [largura, altura] em unidades de textura
  box(x0, y0, z0, x1, y1, z1, hex, tile = [3.2, 2.4]) {
    this.col.setHex(hex);
    const { r, g, b } = this.col;
    const w = x1 - x0, h = y1 - y0, d = z1 - z0;
    const faces = [
      [[x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1], [0, 0, 1], w / tile[0], h / tile[1]],
      [[x1, y0, z0], [x0, y0, z0], [x0, y1, z0], [x1, y1, z0], [0, 0, -1], w / tile[0], h / tile[1]],
      [[x1, y0, z1], [x1, y0, z0], [x1, y1, z0], [x1, y1, z1], [1, 0, 0], d / tile[0], h / tile[1]],
      [[x0, y0, z0], [x0, y0, z1], [x0, y1, z1], [x0, y1, z0], [-1, 0, 0], d / tile[0], h / tile[1]],
      [[x0, y1, z1], [x1, y1, z1], [x1, y1, z0], [x0, y1, z0], [0, 1, 0], w / tile[0], d / tile[0]],
    ];
    for (const [a, bb, cc, dd, nrm, su, sv] of faces) {
      const base = this.p.length / 3;
      for (const v of [a, bb, cc, dd]) { this.p.push(v[0], v[1], v[2]); this.n.push(...nrm); this.c.push(r, g, b); }
      this.u.push(0, 0, su, 0, su, sv, 0, sv);
      this.i.push(base, base + 1, base + 2, base, base + 2, base + 3);
    }
  }
  mesh(mat) {
    const T = this.T, g = new T.BufferGeometry();
    g.setAttribute("position", new T.Float32BufferAttribute(this.p, 3));
    g.setAttribute("normal", new T.Float32BufferAttribute(this.n, 3));
    g.setAttribute("uv", new T.Float32BufferAttribute(this.u, 2));
    g.setAttribute("color", new T.Float32BufferAttribute(this.c, 3));
    g.setIndex(this.i);
    return new T.Mesh(g, mat);
  }
}

// ---------- texturas procedurais (canvas pequeno + NearestFilter) ----------
function canvasTex(T, w, h, draw, repeat = true) {
  const c = document.createElement("canvas"); c.width = w; c.height = h;
  draw(c.getContext("2d"), w, h);
  const tx = new T.CanvasTexture(c);
  tx.magFilter = tx.minFilter = T.NearestFilter; tx.generateMipmaps = false; tx.colorSpace = T.SRGBColorSpace;
  if (repeat) tx.wrapS = tx.wrapT = T.RepeatWrapping;
  return tx;
}
const brickTex = (T) => canvasTex(T, 32, 32, (g, w, h) => {
  const r = rng(11), cols = ["#cc3b20", "#c03419", "#d64626", "#b52f16"];
  g.fillStyle = "#e3d6c2"; g.fillRect(0, 0, w, h);
  for (let y = 0; y < h; y += 4) for (let x = -(y / 4 % 2) * 4; x < w; x += 8) { g.fillStyle = cols[Math.floor(r() * 4)]; g.fillRect(x + 1, y + 1, 7, 3); }
  g.fillStyle = "#f3efe6"; g.fillRect(0, 6, w, 2); g.fillRect(0, 19, w, 2);           // faixas brancas de betão
  g.fillStyle = "#222c38"; g.fillRect(0, 9, w, 10);                                  // janela em faixa
  g.fillStyle = "#43566b"; for (let x = 1; x < w; x += 4) g.fillRect(x, 10, 2, 8);   // lâminas dos estores
  g.fillStyle = "#141b24"; g.fillRect(0, 9, w, 1); g.fillRect(0, 18, w, 1);
});
const groundFloorTex = (T) => canvasTex(T, 32, 32, (g, w, h) => {
  g.fillStyle = "#faf8f2"; g.fillRect(0, 0, w, h);
  g.fillStyle = "#2b3745"; g.fillRect(0, 7, w, 18);
  g.fillStyle = "#5d7690"; for (let x = 2; x < w; x += 8) g.fillRect(x, 8, 5, 16);
  g.fillStyle = "#ffffff"; for (let x = 0; x < w; x += 8) g.fillRect(x, 6, 1, 20); g.fillRect(0, 26, w, 2); g.fillRect(0, 4, w, 2);
});
const cobbleTex = (T) => canvasTex(T, 8, 8, (g) => {
  g.fillStyle = "#b6b6b3"; g.fillRect(0, 0, 8, 8);
  g.fillStyle = "#9a9a98"; for (const [x, y] of [[0, 0], [4, 0], [2, 4], [6, 4]]) g.fillRect(x, y, 3, 3);
  g.fillStyle = "#cfcfcc"; for (const [x, y] of [[0, 0], [4, 0], [2, 4], [6, 4]]) g.fillRect(x, y, 1, 1);
});
function groundTex(T, L, cobble) {
  const S = 6, [W, H] = L.size;
  return canvasTex(T, W * S, H * S, (g) => {
    const r = rng(5), X = (x) => Math.round(x * S), R = (rc, col) => { g.fillStyle = col; g.fillRect(X(rc[0]), X(rc[1]), X(rc[2]), X(rc[3])); };
    g.fillStyle = "#86b850"; g.fillRect(0, 0, W * S, H * S);
    const tones = ["#7cae47", "#8fc255", "#6a9d3a"], ditherRect = (rc, a) => { // 3 tons de relva com dither ordenado
      for (let y = X(rc[1]); y < X(rc[1] + rc[3]); y += 2) for (let x = X(rc[0]); x < X(rc[0] + rc[2]); x += 2) { const k = ((x >> 1) + (y >> 1)) % 4; g.fillStyle = tones[k === 0 ? a : k === 2 && r() < 0.5 ? (a + 1) % 3 : (k === 3 && r() < 0.3 ? 2 : a)]; g.fillRect(x, y, 2, 2); }
    };
    ditherRect([0, 0, W, H], 0);
    L.lawns.forEach((l) => ditherRect(l, 1));
    // campo de jogos: riscas, linhas e balizas
    const [fx, fz, fw, fd] = L.field; R(L.field, "#5ea43b");
    for (let i = 0; i < fd; i += 2) R([fx, fz + i, fw, 1], "#69af45");
    g.strokeStyle = "#fff"; g.lineWidth = 2; g.strokeRect(X(fx) + 3, X(fz) + 3, X(fw) - 6, X(fd) - 6);
    g.beginPath(); g.moveTo(X(fx) + 3, X(fz + fd / 2)); g.lineTo(X(fx + fw) - 3, X(fz + fd / 2)); g.stroke();
    g.beginPath(); g.arc(X(fx + fw / 2), X(fz + fd / 2), X(1.4), 0, 6.3); g.stroke();
    L.parking.forEach((p) => { R(p, "#cfd0d3"); g.fillStyle = "#fff"; for (let z = p[1] + 0.5; z < p[1] + p[3] - 0.5; z += 1.5) { g.fillRect(X(p[0]) + 2, X(z), 2, X(1.1)); g.fillRect(X(p[0] + p[2]) - 4, X(z), 2, X(1.1)); } });
    // calçada portuguesa (padrão ladrilhado pela textura)
    const ct = g.createPattern(cobble.image, "repeat");
    L.paths.forEach(([x1, z1, x2, z2, w]) => {
      const vx = x1 === x2; const rc = [Math.min(x1, x2) - (vx ? w / 2 : 0), Math.min(z1, z2) - (vx ? 0 : w / 2), Math.abs(x2 - x1) + (vx ? w : 0), Math.abs(z2 - z1) + (vx ? 0 : w)];
      g.fillStyle = ct; g.fillRect(X(rc[0]), X(rc[1]), X(rc[2]), X(rc[3]));
    });
    R(L.branch, "#5f6268"); R(L.road, "#5d6066");
    g.fillStyle = "#f1f1ee"; for (let x = 1; x < W; x += 4) g.fillRect(X(x), X(L.road[1] + L.road[3] / 2) - 1, X(2), 3);
    g.fillStyle = "#5d6066"; g.beginPath(); g.arc(X(L.roundabout[0]), X(L.roundabout[1]), X(L.roundabout[2]), 0, 6.3); g.fill();
    g.fillStyle = "#79ad45"; g.beginPath(); g.arc(X(L.roundabout[0]), X(L.roundabout[1]), X(L.roundabout[2] / 2.2), 0, 6.3); g.fill();
    // "sombras" a sudeste dos edifícios
    g.fillStyle = "rgba(20,40,10,.28)";
    L.buildings.forEach((b) => b.parts.forEach(([x, z, w, d, st]) => g.fillRect(X(x + st * 0.9), X(z + d), X(w), X(st * 0.8))));
  }, false);
}
function pondTex(T, L, frame) {
  const [W, H] = L.size, S = 4;
  return canvasTex(T, W * S, H * S, (g) => {
    g.clearRect(0, 0, W * S, H * S);
    const r = rng(3);
    L.pond.forEach((p) => {
      g.fillStyle = "#4f9fd2"; g.fillRect(p[0] * S, p[1] * S, p[2] * S, p[3] * S);
      for (let i = 0; i < p[2] * p[3] * 3; i++) { const x = p[0] * S + r() * p[2] * S, y = p[1] * S + r() * p[3] * S; g.fillStyle = (Math.floor(x / 3 + y / 5 + frame) % 4 === 0) ? "#b6e2f7" : "#3f8bc0"; g.fillRect(x, y, 3, 1); }
    });
  }, false);
}
const personTex = (T, shirt, hair) => canvasTex(T, 16, 12, (g) => {
  for (const f of [0, 1]) {
    const o = f * 8;
    g.fillStyle = "#f2c9a0"; g.fillRect(o + 3, 1, 2, 2);
    g.fillStyle = hair; g.fillRect(o + 3, 0, 2, 1);
    g.fillStyle = shirt; g.fillRect(o + 2, 3, 4, 4);
    g.fillStyle = "#2c3a55"; g.fillRect(o + 2, 7, 4, 3);
    g.fillStyle = "#1b1424"; g.fillRect(o + (f ? 2 : 3), 10, 2, 1); g.fillRect(o + (f ? 4 : 3) + (f ? 0 : 1), 10, 2, 1);
  }
}, false);
function wallTex(T) {
  return canvasTex(T, 64, 12, (g, w, h) => {
    g.fillStyle = "#f3f0e8"; g.fillRect(0, 0, w, h); g.fillStyle = "#c9c5ba"; g.fillRect(0, h - 2, w, 2);
    g.fillStyle = "#777c84"; g.font = "bold 7px monospace"; g.textBaseline = "middle"; g.fillText("Politécnico de Tomar", 4, 6);
    g.fillStyle = "#74bc1f"; g.fillRect(w - 7, 3, 5, 5);
  }, false);
}

// ---------- montagem ----------
export async function mountCampus(host, { theme, onHotspot, lift = 0, isTeacher = () => document.body.dataset.role === "teacher" } = {}) {
  host.dataset.scene = "campus";
  const L = await loadLayout();
  const hs = buildHotspots(host, L, { onHotspot, isTeacher });
  const P = L.poster;
  let stage = null, mode = "2d", disposed = false, focusId = null, want = null, pondMats = [];

  // área segura dos rótulos: abaixo do cabeçalho do herói, longe das margens e (na home) acima do HUD
  const sizes = new Map();
  const roSize = new ResizeObserver((es) => es.forEach((e) => sizes.set(e.target, [e.target.offsetWidth, e.target.offsetHeight])));
  hs.items.forEach(({ btn }) => { roSize.observe(btn); sizes.set(btn, [btn.offsetWidth || 120, btn.offsetHeight || 44]); });
  function safeArea() {
    const W = host.clientWidth, H = host.clientHeight, hr = host.getBoundingClientRect();
    const sc = host.querySelector(".scene-content"), row = sc && sc.classList.contains("grid") ? sc.firstElementChild : sc, hud = sc?.querySelector(":scope > section");
    const bottom = hud ? Math.min(H - 8, hud.getBoundingClientRect().top - hr.top - 8) : H - 10;
    // obstáculos fixos: logótipo e controlos do cabeçalho (os rótulos desviam-se, não tapam)
    const obs = [...(row ? row.children : [])].map((c) => { const r = c.getBoundingClientRect(); return { x: r.left - hr.left - 6, y: r.top - hr.top - 6, w: r.width + 12, h: r.height + 12 }; });
    return { x0: 8, x1: W - 8, y0: 8, y1: Math.max(60, bottom), obs };
  }
  const hit = (a, b) => Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x) > 0 && Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y) > 0;
  // pontos de ancoragem (px) -> posições dos botões: dentro da área segura, rodam para baixo junto às margens e afastam-se uns dos outros
  function layoutLabels(anchors) {
    const A = safeArea(), narrow = host.clientWidth < 640, cx = host.clientWidth / 2, list = anchors.filter((a) => !a.btn.hidden).map((a) => {
      const [w, h] = sizes.get(a.btn) || [120, 44];
      let x = (narrow ? cx + (a.x - cx) * 1.8 : a.x) - w / 2, y = a.y - h - 8; // em ecrãs estreitos os pinos abrem-se para os lados
      if (y < A.y0) y = a.y + 8;                       // sem espaço em cima: o rótulo passa para baixo do edifício
      return { btn: a.btn, w, h, x: Math.max(A.x0, Math.min(A.x1 - w, x)), y: Math.max(A.y0, Math.min(A.y1 - h, y)) };
    }).sort((a, b) => a.y - b.y);
    for (let it = 0; it < 5; it++) {
      for (const l of list) for (const o of A.obs) if (hit(l, o)) l.y = Math.min(A.y1 - l.h, o.y + o.h + 4);
      for (let i = 0; i < list.length; i++) for (let j = i + 1; j < list.length; j++) {
        const a = list[i], b = list[j], oy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
        if (hit(a, b)) b.y = b.y + oy + 4 > A.y1 - b.h ? Math.max(A.y0, a.y - b.h - 4) : b.y + oy + 4;
      }
    }
    list.forEach((l) => { l.btn.style.transform = `translate(${Math.round(l.x)}px, ${Math.round(l.y)}px)`; });
  }

  // posições sobre o cartaz 2D (cover, alinhado em baixo, como o CSS da cena)
  function place2D() {
    hs.refresh();
    if (mode !== "2d") return;
    const W = host.clientWidth, H = host.clientHeight, s = H / P.h, ox = (W - P.w * s) / 2, oy = 0; // o cartaz ocupa a altura toda, centrado
    layoutLabels([...hs.items.values()].map(({ btn, h }) => ({ btn, x: ox + h.at[0] * P.S * s, y: oy + (P.sky + h.at[1] * P.S * P.zk - (h.h / 2.4) * P.hk) * s })));
  }
  const ro = new ResizeObserver(place2D); ro.observe(host);
  place2D();

  const fallback = () => { mode = "2d"; host.classList.add("is-2d"); place2D(); };
  stage = await createStage(host, { fov: 26, onDegrade: fallback });
  if (!stage || disposed) { if (!stage) fallback(); return handle(); }

  const { THREE: T, scene, camera } = stage;
  mode = "3d";
  const R = rng(21);
  const bricks = new Batch(T), cores = new Batch(T), flat = new Batch(T), glow = new Batch(T);
  const parts = [];
  // --- edifícios ---
  L.buildings.forEach((b) => b.parts.forEach(([x, z, w, d, st]) => parts.push([x, z, w, d, st])));
  const GF = 2.6, SH = 2.4;
  parts.forEach(([x, z, w, d, st]) => {
    if (st >= 2) {
      cores.box(x + 0.7, 0, z + 0.7, x + w - 0.7, GF, z + d - 0.7, 0xffffff, [3.2, 2.6]);
      bricks.box(x, GF, z, x + w, GF + SH * (st - 1), z + d, 0xffffff, [3.2, SH]);
      for (let px = x + 0.2; px < x + w; px += 2.2) { flat.box(px, 0, z + 0.1, px + 0.4, GF, z + 0.5, 0xffffff); flat.box(px, 0, z + d - 0.5, px + 0.4, GF, z + d - 0.1, 0xffffff); }
      for (let pz = z + 2.2; pz < z + d - 0.4; pz += 2.2) { flat.box(x + 0.1, 0, pz, x + 0.5, GF, pz + 0.4, 0xffffff); flat.box(x + w - 0.5, 0, pz, x + w - 0.1, GF, pz + 0.4, 0xffffff); }
      flat.box(x - 0.1, GF - 0.25, z - 0.1, x + w + 0.1, GF, z + d + 0.1, 0xffffff); // laje branca
      const top = GF + SH * (st - 1);
      flat.box(x - 0.12, top - 0.3, z - 0.12, x + w + 0.12, top, z + d + 0.12, 0xffffff);
      flat.box(x - 0.1, top, z - 0.1, x + w + 0.1, top + 0.35, z + d + 0.1, 0xd8dbe0);
      flat.box(x + 0.3, top + 0.35, z + 0.3, x + w - 0.3, top + 0.55, z + d - 0.3, 0xeceef1);
    } else {
      bricks.box(x, 0, z, x + w, 2.6, z + d, 0xffffff, [3.2, 2.6]);
      flat.box(x - 0.1, 2.6, z - 0.1, x + w + 0.1, 3, z + d + 0.1, 0xdadde2);
    }
  });
  // auditório A: volume mais alto no telhado; pavilhão com telhado azulado
  flat.box(36.2, 5.2, 25, 39.8, 6.8, 27.6, 0xb9bdc5);
  flat.box(4.4, 2.6, 11.4, 12.4, 3.6, 15.3, 0x5d7ea8);
  // detalhe da porta do pavilhão (Atividades extra): mesa de cartas e painel de bits luminoso
  if (L.extra) {
    const [tx, tz, tw, td] = L.extra.table, [px0, pz0, pw, pd] = L.extra.panel;
    flat.box(tx + 0.1, 0, tz + 0.1, tx + 0.3, 0.8, tz + 0.3, 0x6b4423); flat.box(tx + tw - 0.3, 0, tz + td - 0.3, tx + tw - 0.1, 0.8, tz + td - 0.1, 0x6b4423);
    flat.box(tx, 0.8, tz, tx + tw, 1.0, tz + td, 0x2f8f4a);
    flat.box(tx + 0.2, 1.0, tz + 0.25, tx + 0.55, 1.05, tz + 0.7, 0xffffff); flat.box(tx + 0.7, 1.0, tz + 0.4, tx + 1.05, 1.05, tz + 0.85, 0xffffff);
    flat.box(tx + 1.2, 1.0, tz + 0.2, tx + 1.4, 1.2, tz + 0.4, 0xd94a4a);
    flat.box(px0 + 0.1, 0, pz0, px0 + 0.25, 2.2, pz0 + 0.12, 0x3b3f46); flat.box(px0 + pw - 0.25, 0, pz0, px0 + pw - 0.1, 2.2, pz0 + 0.12, 0x3b3f46);
    flat.box(px0, 1.0, pz0, px0 + pw, 2.4, pz0 + pd, 0x1c2340);
    for (let i = 0; i < 4; i++) glow.box(px0 + 0.15 + i * 0.37, 1.35, pz0 + pd, px0 + 0.4 + i * 0.37, 2.0, pz0 + pd + 0.06, i % 3 === 1 ? 0x3a4570 : 0x52e3ee);
  }
  // passadiço metálico entre o pente e o bloco B
  const [bx0, bz0, bx1, bz1] = L.bridge;
  flat.box(bx0, 2.8, bz0, bx1, 3.1, bz1, 0xc9cdd3);
  flat.box(bx0, 3.1, bz0, bx1, 3.9, bz0 + 0.12, 0xdfe3e8); flat.box(bx0, 3.1, bz1 - 0.12, bx1, 3.9, bz1, 0xdfe3e8);
  flat.box(bx0 + 0.9, 0, bz0 + 0.3, bx0 + 1.1, 2.8, bz0 + 0.5, 0xc9cdd3);
  // muro de entrada (textura com as letras)
  const [wx, wz, ww] = L.wall;
  // --- árvores (choupos, ciprestes, copas redondas) ---
  const blocked = (x, z) => parts.some((p) => x > p[0] - 1.2 && x < p[0] + p[2] + 1.2 && z > p[1] - 1.2 && z < p[1] + p[3] + 1.2) ||
    L.paths.some(([x1, z1, x2, z2, w]) => (x1 === x2 ? Math.abs(x - x1) < w / 2 + 0.6 && z > Math.min(z1, z2) - 0.5 && z < Math.max(z1, z2) + 0.5 : Math.abs(z - z1) < w / 2 + 0.6 && x > Math.min(x1, x2) - 0.5 && x < Math.max(x1, x2) + 0.5)) ||
    L.pond.some((p) => x > p[0] - 1 && x < p[0] + p[2] + 1 && z > p[1] - 1 && z < p[1] + p[3] + 1);
  const greens = [0x2e7d32, 0x3d8f3a, 0x4fa04a, 0x2a6f2f];
  L.lawns.forEach((lw) => {
    const n = Math.round(lw[2] * lw[3] / 11);
    for (let i = 0; i < n; i++) {
      const x = lw[0] + 0.8 + R() * (lw[2] - 1.6), z = lw[1] + 0.8 + R() * (lw[3] - 1.6);
      if (blocked(x, z)) continue;
      const kind = R(), g = greens[Math.floor(R() * 4)], gd = (g >> 1) & 0x7f7f7f;
      flat.box(x - 0.15, 0, z - 0.15, x + 0.15, 1.2, z + 0.15, 0x6b4423);
      if (kind < 0.35) { for (let k = 0; k < 5; k++) flat.box(x - 0.55 + k * 0.02, 1 + k * 1.1, z - 0.55, x + 0.55 - k * 0.02, 2.2 + k * 1.1, z + 0.55, k < 2 ? gd : g); }          // choupo
      else if (kind < 0.6) { for (let k = 0; k < 4; k++) { const wd = 0.8 - k * 0.17; flat.box(x - wd, 1 + k * 1.0, z - wd, x + wd, 2.1 + k * 1.0, z + wd, 0x2a6f2f); } } // cipreste
      else { flat.box(x - 1, 1.2, z - 1, x + 1, 2.0, z + 1, gd); flat.box(x - 1, 2.0, z - 1, x + 1, 2.4, z + 1, g); flat.box(x - 0.7, 2.4, z - 0.7, x + 0.7, 3, z + 0.7, 0x5fb058); }                                       // copa
    }
  });
  // --- candeeiros de globo duplo, balizadores, bancos ---
  L.lamps.forEach(([x, z]) => { flat.box(x - 0.08, 0, z - 0.08, x + 0.08, 2.3, z + 0.08, 0x3b3f46); flat.box(x - 0.55, 2.3, z - 0.06, x + 0.55, 2.38, z + 0.06, 0x3b3f46); glow.box(x - 0.8, 2.38, z - 0.18, x - 0.4, 2.78, z + 0.18, 0xfff2b8); glow.box(x + 0.4, 2.38, z - 0.18, x + 0.8, 2.78, z + 0.18, 0xfff2b8); });
  L.bollards.forEach(([x, z]) => flat.box(x - 0.12, 0, z - 0.12, x + 0.12, 0.6, z + 0.12, 0xf4f4f0));
  L.benches.forEach(([x, z, rot]) => { const a = rot ? [0.25, 0.7] : [0.7, 0.25]; flat.box(x - a[0], 0.3, z - a[1], x + a[0], 0.42, z + a[1], 0x9a6a3a); flat.box(x - a[0], 0, z - a[1], x - a[0] + 0.1, 0.3, z + a[1], 0x6b4423); flat.box(x + a[0] - 0.1, 0, z - a[1], x + a[0], 0.3, z + a[1], 0x6b4423); });
  // --- materiais e malhas ---
  const bt = brickTex(T), gt = groundFloorTex(T), cobble = cobbleTex(T), gnd = groundTex(T, L, cobble);
  const vc = { vertexColors: true };
  const mBrick = new T.MeshLambertMaterial({ ...vc, map: bt }), mCore = new T.MeshLambertMaterial({ ...vc, map: gt }), mFlat = new T.MeshLambertMaterial(vc), mGlow = new T.MeshBasicMaterial(vc);
  scene.add(bricks.mesh(mBrick), cores.mesh(mCore), flat.mesh(mFlat), glow.mesh(mGlow));
  const [GW, GH] = L.size;
  const ground = new T.Mesh(new T.PlaneGeometry(GW, GH), new T.MeshLambertMaterial({ map: gnd }));
  ground.rotation.x = -Math.PI / 2; ground.position.set(GW / 2, 0, GH / 2); scene.add(ground);
  const base = new T.Mesh(new T.PlaneGeometry(GW * 9, GH * 9), new T.MeshBasicMaterial({ color: 0x7cae47 })); base.rotation.x = -Math.PI / 2; base.position.set(GW / 2, -0.05, GH / 2); scene.add(base);
  pondMats = [0, 1, 2, 3].map((f) => new T.MeshBasicMaterial({ map: pondTex(T, L, f), transparent: true }));
  const pond = new T.Mesh(new T.PlaneGeometry(GW, GH), pondMats[0]); pond.rotation.x = -Math.PI / 2; pond.position.set(GW / 2, 0.04, GH / 2); scene.add(pond);
  const wall = new T.Mesh(new T.BoxGeometry(ww, 1.3, 0.4), new T.MeshLambertMaterial({ color: 0xe9e6dd }));
  wall.position.set(wx + ww / 2, 0.65, wz); scene.add(wall);
  const wallFront = new T.Mesh(new T.PlaneGeometry(ww, 1.3), new T.MeshBasicMaterial({ map: wallTex(T) })); wallFront.position.set(wx + ww / 2, 0.65, wz + 0.21); scene.add(wallFront);
  // nuvens
  const clouds = [];
  for (let i = 0; i < 6; i++) { const g = new T.Group(); for (let k = 0; k < 4; k++) { const c = new T.Mesh(new T.BoxGeometry(3 + (k % 2) * 2, 1, 2.2), new T.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.92 })); c.position.set(k * 2.4, (k % 2) * 0.6, 0); g.add(c); } g.position.set(R() * 90 - 20, 24 + R() * 8, R() * 60 - 10); scene.add(g); clouds.push(g); }
  // pessoas a andar pelos caminhos
  const shirts = ["#c44536", "#2a6fdb", "#e0b020", "#6a3fb0", "#2a8a3a", "#d4580a"], hairs = ["#3a2a1a", "#1b1424", "#8a5a2a", "#caa86a"];
  const walkers = L.paths.filter((p) => Math.hypot(p[2] - p[0], p[3] - p[1]) > 6).slice(0, 8).map((p, i) => {
    const tx = personTex(T, shirts[i % 6], hairs[i % 4]); tx.repeat.set(0.5, 1);
    const sp = new T.Sprite(new T.SpriteMaterial({ map: tx })); sp.scale.set(1.0, 1.5, 1); scene.add(sp);
    return { sp, tx, p, off: R(), speed: 0.7 + R() * 0.6 };
  });
  // luzes e contorno do hotspot ativo
  scene.fog = new T.Fog(0xd2e9fb, 80, 190);
  const amb = new T.AmbientLight(0xffffff, 1.2), sun = new T.DirectionalLight(0xffffff, 1.7); sun.position.set(-30, 50, 40); scene.add(amb, sun);
  const outlines = new Map();
  hs.spots.forEach((h) => {
    const [x0, z0, x1, z1] = h.bounds, hh = h.h || 6;
    const eg = new T.EdgesGeometry(new T.BoxGeometry(x1 - x0, hh, z1 - z0)), ln = new T.LineSegments(eg, new T.LineBasicMaterial({ color: 0xffd23f }));
    ln.position.set((x0 + x1) / 2, hh / 2 + 0.1, (z0 + z1) / 2); ln.visible = false; scene.add(ln); outlines.set(h.id, ln);
  });
  hs.onActive = (id) => outlines.forEach((ln, key) => { ln.visible = key === id; });
  // caixas invisíveis dos edifícios-porta para o raycast do rato/toque no próprio canvas
  const hitBoxes = hs.spots.map((h) => { const [x0, z0, x1, z1] = h.bounds, hh = h.h || 6, m = new T.Mesh(new T.BoxGeometry(x1 - x0, hh, z1 - z0), new T.MeshBasicMaterial({ visible: false })); m.position.set((x0 + x1) / 2, hh / 2, (z0 + z1) / 2); m.userData.id = h.id; scene.add(m); m.updateMatrixWorld(); return m; });
  const ray = new T.Raycaster(), ndc = new T.Vector2();
  const pick = (e) => {
    const r = host.getBoundingClientRect(); ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ndc, camera);
    const hit = ray.intersectObjects(hitBoxes, false).find((i) => { const it = hs.items.get(i.object.userData.id); return it && !it.btn.hidden; });
    return hit ? hit.object.userData.id : null;
  };
  let hoverId = null;
  const onMove = (e) => {
    if (e.pointerType === "touch" || e.target !== stage.canvas) { if (hoverId && e.target !== stage.canvas) { hoverId = null; hs.setActive(null); stage.canvas.style.cursor = ""; } return; }
    const id = pick(e);
    if (id !== hoverId) { hoverId = id; hs.setActive(id); stage.canvas.style.cursor = id ? "var(--cur-pointer)" : ""; }
  };
  const onUp = (e) => { if (e.target !== stage.canvas) return; const id = pick(e); if (id) hs.items.get(id).btn.click(); };
  host.addEventListener("pointermove", onMove); host.addEventListener("pointerup", onUp);
  host.addEventListener("pointerleave", () => { if (hoverId) { hoverId = null; hs.setActive(null); } });

  // ---- ciclo de luz em degraus: dia -> fim de tarde ----
  const DAY = { s1: 0x5aa8e8, s2: 0xd2e9fb, sun: 0xfffaf0, amb: 0xdfeaff }, LATE = { s1: 0xe5935f, s2: 0xffdca8, sun: 0xffb86b, amb: 0xffd9b8 };
  const c1 = new T.Color(), c2 = new T.Color();
  const lerpHex = (a, b, k) => c1.setHex(a).lerp(c2.setHex(b), k).getHexString();
  let lastStep = -1;
  function light(clock) {
    const p = 1 - Math.abs(((clock / 70) % 2) - 1), step = Math.round(p * 5);
    if (step === lastStep) return; lastStep = step;
    const k = step / 5;
    host.style.setProperty("--cs1", `#${lerpHex(DAY.s1, LATE.s1, k)}`); host.style.setProperty("--cs2", `#${lerpHex(DAY.s2, LATE.s2, k)}`);
    sun.color.set(`#${lerpHex(DAY.sun, LATE.sun, k)}`); amb.color.set(`#${lerpHex(DAY.amb, LATE.amb, k)}`);
    sun.position.set(-30 + k * 55, 50 - k * 22, 40 - k * 18);
    if (scene.fog) scene.fog.color.set(`#${lerpHex(DAY.s2, LATE.s2, k)}`);
  }

  // ---- câmara: deriva lenta à volta do campus; focus() aproxima-se de um edifício ----
  let dist = 80, aspectNow = 1.8, focusX = 28;
  stage.onResize((a) => { aspectNow = a; dist = a < 1.7 ? Math.max(62, 40 / (0.4624 * a) + 10) : Math.max(84, 60 / (0.4624 * a) + 12); focusX = a < 1.7 ? 29 : 28; if (want) { want.x = focusX; } scene.fog.near = dist * 0.85; scene.fog.far = dist * 1.9; });
  const tgt = new T.Vector3(focusX, -lift * 0.7, 19); want = new T.Vector3(focusX, -lift * 0.7, 19); // lift sobe o campus no ecrã (home: o HUD tapa a parte de baixo)
  const v = new T.Vector3();
  function project() {
    const W = host.clientWidth, H = host.clientHeight;
    layoutLabels([...hs.items.values()].map(({ btn, h }) => { v.set(h.at[0], h.h || 6, h.at[1]).project(camera); return { btn, x: (v.x * 0.5 + 0.5) * W, y: (-v.y * 0.5 + 0.5) * H }; }));
  }
  stage.onFrame((dt, clock) => {
    light(clock);
    const sway = Math.sin(clock * 0.07) * 0.5;
    const az = 0.15 + sway, el_ = 0.6, d = focusId ? dist * 0.62 : dist;
    tgt.lerp(want, 0.08);
    camera.position.set(tgt.x + Math.sin(az) * d * Math.cos(el_), d * Math.sin(el_) * 0.95, tgt.z + Math.cos(az) * d * Math.cos(el_));
    camera.lookAt(tgt); camera.updateMatrixWorld();
    clouds.forEach((c) => { c.position.x += dt * 0.9; if (c.position.x > 90) c.position.x = -30; });
    pond.material = pondMats[Math.floor(clock * 2) % 4];
    walkers.forEach((w) => {
      const [x1, z1, x2, z2] = w.p, len = Math.hypot(x2 - x1, z2 - z1), s = (((clock * w.speed + w.off * len * 2) % (len * 2)));
      const u = (s < len ? s : 2 * len - s) / len, q = Math.round(u * len * 3) / 3 / len;
      w.sp.position.set(x1 + (x2 - x1) * q + 0.35, 0.75, z1 + (z2 - z1) * q + 0.35);
      w.tx.offset.x = (Math.floor(clock * 3 + w.off * 10) % 2) * 0.5;
    });
    outlines.forEach((ln) => { if (ln.visible) ln.material.color.setHex(Math.floor(clock * 4) % 2 ? 0xffd23f : 0xffffff); });
    hs.refresh();
    project();
  });
  host.classList.remove("is-2d");
  void aspectNow;

  function handle() {
    return {
      setTheme() { /* o campus tem o seu próprio céu: a paleta da interface não o altera */ },
      focus(id) {
        const h = L.hotspots.find((x) => x.id === id); focusId = id || null;
        if (want) { if (h) want.set(h.at[0], -lift * 0.7, h.at[1]); else want.set(focusX, -lift * 0.7, 19); }
        hs.setActive(id || null);
      },
      dispose() {
        if (disposed) return; disposed = true; ro.disconnect(); roSize.disconnect(); try { host.removeEventListener("pointermove", onMove); host.removeEventListener("pointerup", onUp); } catch (_) { /* ignora */ } hs.destroy(); host.style.removeProperty("--cs1"); host.style.removeProperty("--cs2");
        if (stage) { try { stage.dispose(); } catch (_) { /* já libertado */ } }
        pondMats.forEach((m) => m.map?.dispose?.());
        host.classList.remove("is-2d");
        delete host.dataset.scene;
      },
    };
  }
  return handle();
}
