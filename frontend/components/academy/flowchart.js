// Fluxograma vetorial (SVG) no estilo limpo dos slides do professor: pílula verde, paralelogramo e retângulo lilás,
// losango azul-escuro, setas finas. NÃO é pixel art. Desenha-se a partir do modelo (model.js), por isso bate sempre
// certo com o Python. Todo o SVG é criado com createElementNS (nunca HTML em bruto); as cores vêm do CSS (.fx-*).
import { pickText, labelOf, familyOf } from "./model.js";
import { t, getLocale } from "../../services/i18n.js";
import { el } from "../dom.js";

const NS = "http://www.w3.org/2000/svg";
const FONT = '14px system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
const LH = 18;      // altura de linha do texto
const GAP = 30;     // comprimento das setas verticais
const SKEW = 12;    // inclinação do paralelogramo
const V = 34;       // espaço sob o losango para as etiquetas Sim/Não
const MARGIN = 16;

// ---------- medição de texto (canvas, sem ligar nada ao DOM) ----------
const ctx = document.createElement("canvas").getContext("2d");
ctx.font = FONT;
const width = (s) => ctx.measureText(s).width;

function wrap(text, maxW) {
  const words = String(text).split(/\s+/).filter(Boolean);
  const lines = [];
  let cur = "";
  for (const w of words) {
    const next = cur ? `${cur} ${w}` : w;
    if (cur && width(next) > maxW) { lines.push(cur); cur = w; } else cur = next;
  }
  if (cur) lines.push(cur);
  return lines.length ? lines : [""];
}

// ---------- layout: cada bloco devolve {l, r, h, items} com o eixo em x = 0 e o topo em y = 0 ----------
const shift = (items, dx, dy) => items.map((it) => (it.points
  ? { ...it, points: it.points.map(([x, y]) => [x + dx, y + dy]), label: it.label && { ...it.label, x: it.label.x + dx, y: it.label.y + dy } }
  : { ...it, x: it.x + dx, y: it.y + dy }));

const edge = (points, arrow = true, label = null) => ({ points, arrow, label });

function shapeNode(kind, s, locale, text) {
  const isDec = kind === "dec";
  const lines = wrap(text, isDec ? 130 : 135);
  const tw = Math.max(...lines.map(width));
  const th = lines.length * LH;
  let w, h;
  if (isDec) { w = Math.max(120, tw / 0.6 + 12); h = Math.max(64, th / 0.35); }
  else if (kind === "pill") { w = Math.max(96, tw + 44); h = 38; }
  else { w = Math.max(100, tw + 2 * 12 + (kind === "io" ? 2 * SKEW : 0)); h = Math.max(40, th + 18); }
  return { w, h, lines, stmt: s };
}

function layoutNode(kind, s, text, locale) {
  const n = shapeNode(kind, s, locale, text);
  return {
    l: n.w / 2, r: n.w / 2, h: n.h, dw: n.w, dh: n.h,
    items: [{ shape: kind, stmtId: s?.id ?? null, tipo: s?.tipo ?? kind, text, lines: n.lines, x: -n.w / 2, y: 0, w: n.w, h: n.h }],
  };
}

function layoutSeq(stmts, locale) {
  const items = [];
  let y = 0, l = 0, r = 0, prevBottom = null;
  for (const s of stmts) {
    const lay = layoutStmt(s, locale);
    if (prevBottom != null) items.push(edge([[0, prevBottom], [0, y]]));
    items.push(...shift(lay.items, 0, y));
    l = Math.max(l, lay.l); r = Math.max(r, lay.r);
    prevBottom = y + lay.h;
    y = prevBottom + GAP;
  }
  return { l, r, h: prevBottom ?? 0, items };
}

function layoutStmt(s, locale) {
  if (s.tipo === "inicio" || s.tipo === "fim") return layoutNode("pill", s, s.label, locale);
  if (s.tipo === "se") return layoutSe(s, locale);
  if (s.tipo === "enquanto" || s.tipo === "para") return layoutLoop(s, locale);
  return layoutNode(familyOf(s.tipo), s, labelOf(s, locale), locale);
}

function layoutSe(s, locale) {
  const dec = layoutNode("dec", s, labelOf(s, locale), locale);
  const dw = dec.dw, dh = dec.dh;
  const sim = layoutSeq(s.sim || [], locale), nao = layoutSeq(s.nao || [], locale);
  const G = 32;
  const W = sim.l + sim.r + G + nao.l + nao.r;
  let aL = -W / 2 + sim.l;
  let aR = -W / 2 + sim.l + sim.r + G + nao.l;
  aL = Math.min(aL, -(dw / 2 + 36));
  aR = Math.max(aR, dw / 2 + 36);
  const y0 = dh + V;
  const bottomL = y0 + sim.h, bottomR = y0 + nao.h;
  const joinY = Math.max(bottomL, bottomR) + GAP - 6;
  const cy = dh / 2;
  const items = [...dec.items];
  const side = (a, branch, bottom, vx, label, anchor) => {
    if (branch.items.length) {
      items.push(edge([[vx, cy], [a, cy], [a, y0]], true, { text: label, x: a + (anchor === "end" ? -7 : 7), y: cy + 20, anchor }));
      items.push(...shift(branch.items, a, y0));
      items.push(edge([[a, bottom], [a, joinY], [0, joinY]], false));
    } else {
      items.push(edge([[vx, cy], [a, cy], [a, joinY], [0, joinY]], false, { text: label, x: a + (anchor === "end" ? -7 : 7), y: cy + 20, anchor }));
    }
  };
  side(aL, sim, bottomL, -dw / 2, t("fx.yes"), "end");
  side(aR, nao, bottomR, dw / 2, t("fx.no"), "start");
  return { l: Math.max(-aL + sim.l, dw / 2), r: Math.max(aR + nao.r, dw / 2), h: joinY, items };
}

function layoutLoop(s, locale) {
  const dec = layoutNode("dec", s, labelOf(s, locale), locale);
  const dw = dec.dw, dh = dec.dh, cy = dh / 2;
  const body = layoutSeq(s.corpo || [], locale);
  const y0 = dh + V;
  const bodyBottom = y0 + body.h;
  const back = bodyBottom + 26;
  const xl = -(Math.max(body.l, dw / 2) + 38);
  const xr = Math.max(body.r, dw / 2) + 52;
  const exitY = back + 32;
  const items = [...dec.items];
  items.push(edge([[0, dh], [0, y0]], true, { text: t("fx.yes"), x: 8, y: dh + 22, anchor: "start" }));
  items.push(...shift(body.items, 0, y0));
  items.push(edge([[0, bodyBottom], [0, back], [xl, back], [xl, cy], [-dw / 2, cy]], true));
  items.push(edge([[dw / 2, cy], [xr, cy], [xr, exitY], [0, exitY]], false, { text: t("fx.no"), x: dw / 2 + 12, y: cy - 8, anchor: "start" }));
  return { l: -xl, r: xr, h: exitY, items };
}

// ---------- desenho ----------
const svgEl = (tag, attrs = {}) => {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v));
  return e;
};

function drawText(lines, cx, cy) {
  const tx = svgEl("text", { x: cx, y: cy, "text-anchor": "middle" });
  const top = cy - ((lines.length - 1) * LH) / 2;
  lines.forEach((ln, i) => {
    const sp = svgEl("tspan", { x: cx, y: top + i * LH, "dominant-baseline": "central" });
    sp.textContent = ln;
    tx.append(sp);
  });
  return tx;
}

function drawShape(it) {
  const { x, y, w, h } = it;
  const cx = x + w / 2, cy = y + h / 2;
  let shape;
  if (it.shape === "pill") shape = svgEl("rect", { x, y, width: w, height: h, rx: h / 2, ry: h / 2 });
  else if (it.shape === "io") shape = svgEl("polygon", { points: `${x + SKEW},${y} ${x + w},${y} ${x + w - SKEW},${y + h} ${x},${y + h}` });
  else if (it.shape === "dec") shape = svgEl("polygon", { points: `${cx},${y} ${x + w},${cy} ${cx},${y + h} ${x},${cy}` });
  else shape = svgEl("rect", { x, y, width: w, height: h });
  shape.setAttribute("class", "fx-shape");
  return [shape, drawText(it.lines, cx, cy)];
}

function drawEdge(e) {
  const g = svgEl("g");
  g.append(svgEl("path", { class: "fx-edge", d: e.points.map(([px, py], i) => `${i ? "L" : "M"}${px} ${py}`).join(" ") }));
  if (e.arrow) {
    const [x2, y2] = e.points[e.points.length - 1], [x1, y1] = e.points[e.points.length - 2];
    const dx = Math.sign(x2 - x1), dy = Math.sign(y2 - y1);
    const L = 9, B = 4.5;
    const pts = dy ? `${x2},${y2} ${x2 - B},${y2 - dy * L} ${x2 + B},${y2 - dy * L}` : `${x2},${y2} ${x2 - dx * L},${y2 - B} ${x2 - dx * L},${y2 + B}`;
    g.append(svgEl("polygon", { class: "fx-head", points: pts }));
  }
  if (e.label) {
    const lb = svgEl("text", { class: "fx-label", x: e.label.x, y: e.label.y, "text-anchor": e.label.anchor });
    lb.textContent = e.label.text;
    g.append(lb);
  }
  return g;
}

// renderFlowchart(container, program, {locale, onSelect, highlight}) -> {select(stmtId), clear(), destroy(), relayout()}
export function renderFlowchart(container, program, { locale = getLocale(), onSelect, highlight = null } = {}) {
  const lay = layoutSeq([
    { tipo: "inicio", id: null, label: t("fx.start") },
    ...program.corpo,
    { tipo: "fim", id: null, label: t("fx.end") },
  ], locale);
  const minX = -lay.l - MARGIN, W = lay.l + lay.r + 2 * MARGIN, H = lay.h + 2 * MARGIN;
  // O texto nunca desce abaixo de ~13 px: o SVG não encolhe além de 93% do tamanho natural (o cartão faz scroll se faltar largura)
  const svg = svgEl("svg", { class: "fx-svg", viewBox: `${minX} ${-MARGIN} ${W} ${H}`, width: Math.round(W), height: Math.round(H), role: "group", "aria-label": pickText(program.titulo, locale) });
  const nodes = new Map(); // stmtId -> <g>
  const edges = svgEl("g"), shapes = svgEl("g");
  svg.append(edges, shapes);
  for (const it of lay.items) {
    if (it.points) { edges.append(drawEdge(it)); continue; }
    const g = svgEl("g", { class: `fx-block fx-${it.shape}`, "data-stmt": it.stmtId ?? "" });
    g.append(...drawShape(it));
    if (it.stmtId) {
      g.setAttribute("role", "button");
      g.setAttribute("tabindex", "0");
      g.setAttribute("aria-pressed", "false");
      g.setAttribute("aria-label", `${t(`fx.k_${it.tipo}`)}: ${it.text}`);
      nodes.set(it.stmtId, g);
      const pick = () => { select(it.stmtId); onSelect?.(it.stmtId); };
      g.addEventListener("click", pick);
      g.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); pick(); } });
    }
    shapes.append(g);
  }
  // Cartão: barra com o botão "Ver inteiro / Tamanho legível" e a dica de scroll, e a zona com o SVG
  const FLOOR = 0.93;
  const store = { get() { try { return sessionStorage.getItem("fx.fit") === "1"; } catch (_) { return false; } }, set(v) { try { sessionStorage.setItem("fx.fit", v ? "1" : "0"); } catch (_) { /* ignora */ } } };
  let fitAll = store.get();
  const toggle = el("button", { type: "button", class: "fx-toggle", hidden: true });
  const hint = el("span", { class: "fx-hint", hidden: true });
  const bar = el("div", { class: "fx-bar" }, hint, toggle);
  const scroller = el("div", { class: "fx-scroll" }, svg);
  const wrapEl = el("div", { class: "fx-scroll-wrap" }, scroller);
  container.classList.add("fx-chart");
  container.replaceChildren(bar, wrapEl);
  function refresh() {
    svg.style.minWidth = fitAll ? "0" : `${Math.round(W * FLOOR)}px`;
    const narrow = scroller.clientWidth < W * FLOOR - 1; // o diagrama não cabe no tamanho legível
    toggle.hidden = !narrow;
    toggle.textContent = fitAll ? t("fx.fit_readable") : t("fx.fit_all");
    toggle.setAttribute("aria-pressed", String(fitAll));
    const more = !fitAll && narrow && scroller.scrollLeft + scroller.clientWidth < scroller.scrollWidth - 2;
    hint.hidden = !(!fitAll && narrow);
    hint.textContent = t("fx.scroll_hint");
    wrapEl.classList.toggle("has-more", more);
  }
  toggle.addEventListener("click", () => { fitAll = !fitAll; store.set(fitAll); refresh(); });
  scroller.addEventListener("scroll", refresh, { passive: true });
  const ro = new ResizeObserver(refresh);
  ro.observe(scroller);
  refresh();
  if (!fitAll && scroller.scrollWidth > scroller.clientWidth) scroller.scrollLeft = (scroller.scrollWidth - scroller.clientWidth) / 2; // começa centrado no eixo
  requestAnimationFrame(refresh);

  let current = null;
  function select(id, { scroll = false } = {}) {
    clear();
    const g = nodes.get(id);
    if (!g) return;
    current = id;
    g.classList.add("is-selected");
    g.setAttribute("aria-pressed", "true");
    if (scroll) g.scrollIntoView?.({ block: "nearest", inline: "nearest", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }
  function clear() {
    if (current) {
      const g = nodes.get(current);
      g?.classList.remove("is-selected");
      g?.setAttribute("aria-pressed", "false");
    }
    current = null;
  }
  if (highlight) select(highlight);
  return { select, clear, destroy() { ro.disconnect(); container.replaceChildren(); }, get selected() { return current; }, ids: () => [...nodes.keys()] };
}
