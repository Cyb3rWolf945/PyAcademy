// Atividade "ligar": ligar cada bloco do fluxograma à linha de Python que o escreve. Em ecrãs largos mostra o fluxograma
// completo (renderFlowchart) à esquerda e as linhas de código baralhadas à direita, com linhas de ligação desenhadas;
// em ecrãs estreitos, duas colunas de cartões. Toque/clique (escolher o bloco e depois a linha), arrastar do bloco
// para a linha, ou teclado (Enter para escolher, Enter na linha para ligar, Esc/Delete para desfazer).
// Resposta: {pares: {stmtId: stmtId}} (bloco -> linha). A solução nunca está no cliente.
import { el } from "../../dom.js";
import { t } from "../../../services/i18n.js";
import { walk, labelOf } from "../model.js";
import { renderFlowchart } from "../flowchart.js";
import { stmtMap, flowBlock, firstLines, codeCard } from "./blocks.js";

const NS = "http://www.w3.org/2000/svg";
const WIDE = 720;
const PAIR_COLORS = ["#8f86d6", "#2e9e5b", "#f5a623", "#1f78c1", "#c2569b", "#8a6d00", "#3aa6a6", "#7a5c3b"];

function shuffled(arr) {
  const a = [...arr];
  for (let k = 0; k < 8; k++) {
    for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
    if (a.length < 2 || a.some((x, i) => x !== arr[i])) break; // nunca devolve a ordem original
  }
  return a;
}

export function mountLigar(host, act, { exemplo, locale, say, onChange }) {
  const stmts = stmtMap(exemplo);
  const lines = firstLines(exemplo);
  // Com `alvo` trabalha-se só dentro dessa função (pílula de início ↔ linha def, mais o corpo); sem `alvo`, no programa principal
  const fn = act.alvo ? (exemplo.funcoes || []).find((f) => f.id === act.alvo) : null;
  const defaults = fn ? [fn.id, ...[...walk(fn.corpo || [])].map((s) => s.id)] : [...walk(exemplo.corpo || [])].map((s) => s.id);
  const ids = (act.ids || defaults).filter((id) => lines.has(id));
  const rightOrder = act.linhas ? act.linhas.map((x) => (typeof x === "object" ? x.id : x)) : shuffled(ids);
  const pairs = new Map(); // idEsquerda -> idDireita
  const colorOf = new Map(); // idEsquerda -> cor
  let selected = null, wrongSet = new Set(), locked = false, mode = null, flow = null, drag = null;
  let leftEl = new Map(), rightEl = new Map();
  const root = el("div", { class: "act-ligar" });
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("class", "act-links"); svg.setAttribute("aria-hidden", "true");
  host.replaceChildren(root);

  const leftLabel = (id) => labelOf(stmts.get(id), locale);
  const rightLabel = (id) => lines.get(id)?.code ?? String(id);
  const nextColor = () => PAIR_COLORS.find((c) => ![...colorOf.values()].includes(c)) || PAIR_COLORS[0];

  // ---- ações ----
  function chooseLeft(id) {
    if (locked || !ids.includes(id)) return;
    selected = selected === id ? null : id;
    paint();
    say(selected ? t("act.link_picked", { text: leftLabel(id) }) : t("act.cancelled"));
  }
  function unpair(id) {
    if (!pairs.has(id)) return;
    pairs.delete(id); colorOf.delete(id); wrongSet.delete(id);
    say(t("act.link_removed", { text: leftLabel(id) }));
    paint(); onChange();
  }
  function link(l, r) {
    for (const [k, v] of pairs) if (v === r && k !== l) { pairs.delete(k); colorOf.delete(k); } // uma linha só tem um bloco
    pairs.set(l, r);
    if (!colorOf.has(l)) colorOf.set(l, nextColor());
    wrongSet.clear(); selected = null;
    say(t("act.link_made", { a: leftLabel(l), b: rightLabel(r) }));
    paint(); onChange();
  }
  function chooseRight(r) {
    if (locked) return;
    if (selected != null) link(selected, r);
    else { const l = [...pairs].find(([, v]) => v === r)?.[0]; if (l != null) chooseLeft(l); else say(t("act.link_pick_block")); }
  }

  // ---- construção ----
  function build() {
    mode = root.clientWidth >= WIDE ? "wide" : "narrow";
    leftEl = new Map(); rightEl = new Map(); flow = null;
    const leftCol = el("div", { class: "act-col act-col--left" });
    const rightCol = el("div", { class: "act-col act-col--right", role: "list", "aria-label": t("fx.python") });
    if (mode === "wide") {
      const host2 = el("div");
      flow = renderFlowchart(host2, exemplo, { locale, alvo: act.alvo, onSelect: (id) => { if (ids.includes(id)) chooseLeft(id); else flow.clear(); } });
      leftCol.append(host2);
      for (const id of ids) {
        const g = host2.querySelector(`[data-stmt="${CSS.escape(id)}"]`);
        if (g) { leftEl.set(id, g); g.classList.add("act-target"); }
      }
      for (const g of host2.querySelectorAll(".fx-block[data-stmt]")) if (g.dataset.stmt && !ids.includes(g.dataset.stmt)) g.classList.add("act-inert");
    } else {
      for (const id of ids) {
        const card = el("div", { class: "act-link-card", role: "button", tabindex: 0, "aria-pressed": "false", "aria-label": `${t("act.block")}: ${leftLabel(id)}` }, flowBlock(stmts.get(id), locale), el("span", { class: "act-badge", hidden: true }));
        card.addEventListener("click", () => chooseLeft(id));
        card.addEventListener("keydown", (ev) => keys(ev, () => chooseLeft(id), id));
        leftEl.set(id, card); leftCol.append(card);
      }
    }
    for (const id of rightOrder) {
      const card = el("div", { class: "act-link-card", role: "button", tabindex: 0, "data-right": id, "aria-label": `${t("act.line")}: ${rightLabel(id)}` }, codeCard(lines.get(id)), el("span", { class: "act-badge", hidden: true }));
      card.addEventListener("click", () => chooseRight(id));
      card.addEventListener("keydown", (ev) => keys(ev, () => chooseRight(id), [...pairs].find(([, v]) => v === id)?.[0]));
      rightEl.set(id, card); rightCol.append(card);
    }
    // arrastar do bloco para a linha
    for (const [id, node] of leftEl) {
      node.addEventListener("pointerdown", (ev) => startDrag(ev, id));
    }
    root.className = `act-ligar act-ligar--${mode}`;
    root.replaceChildren(leftCol, rightCol, ...(mode === "wide" ? [svg] : []));
    paint();
  }

  function keys(ev, act1, pairedLeft) {
    if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); act1(); }
    else if (ev.key === "Escape") { selected = null; paint(); }
    else if ((ev.key === "Backspace" || ev.key === "Delete") && pairedLeft != null) { ev.preventDefault(); unpair(pairedLeft); }
  }

  // ---- arrastar ----
  function startDrag(ev, id) {
    if (locked || (ev.pointerType === "mouse" && ev.button !== 0)) return;
    drag = { id, x: ev.clientX, y: ev.clientY, moved: false, pid: ev.pointerId };
    const move = (e) => {
      if (!drag) return;
      if (!drag.moved && Math.hypot(e.clientX - drag.x, e.clientY - drag.y) > 8) { drag.moved = true; selected = id; paint(); }
      if (drag.moved) { rubber(e.clientX, e.clientY); e.preventDefault(); }
    };
    const up = (e) => {
      document.removeEventListener("pointermove", move); document.removeEventListener("pointerup", up); document.removeEventListener("pointercancel", up);
      const moved = drag?.moved; drag = null;
      svg.querySelector(".act-rubber")?.remove();
      if (!moved) return;
      const t2 = document.elementFromPoint(e.clientX, e.clientY)?.closest?.("[data-right]");
      if (t2) { link(id, t2.dataset.right); const stop = (c) => { c.stopPropagation(); }; root.addEventListener("click", stop, { capture: true, once: true }); }
      else paint();
    };
    document.addEventListener("pointermove", move, { passive: false });
    document.addEventListener("pointerup", up);
    document.addEventListener("pointercancel", up);
  }
  function rubber(x, y) {
    if (mode !== "wide") return;
    const rc = root.getBoundingClientRect(), a = leftEl.get(drag.id).getBoundingClientRect();
    let p = svg.querySelector(".act-rubber");
    if (!p) { p = document.createElementNS(NS, "path"); p.setAttribute("class", "act-rubber"); svg.append(p); }
    p.setAttribute("d", curve(a.right - rc.left, a.top + a.height / 2 - rc.top, x - rc.left, y - rc.top));
  }
  const curve = (x1, y1, x2, y2) => `M${x1} ${y1} C${x1 + 60} ${y1} ${x2 - 60} ${y2} ${x2} ${y2}`;

  // ---- pintura (estado -> DOM) ----
  function paint() {
    for (const [id, node] of leftEl) {
      const paired = pairs.has(id), color = colorOf.get(id);
      node.classList.toggle("is-selected", selected === id);
      node.classList.toggle("is-paired", paired);
      node.classList.toggle("is-wrong", wrongSet.has(id));
      node.setAttribute("aria-pressed", String(selected === id));
      if (mode === "wide") {
        node.style.setProperty("--pair", color || "transparent");
      }
      const b = node.querySelector?.(".act-badge");
      if (b) { b.hidden = !paired; b.textContent = paired ? String([...pairs.keys()].indexOf(id) + 1) : ""; b.style.background = color || ""; }
    }
    if (mode === "wide") { if (selected != null) flow.select(selected); else flow.clear(); }
    for (const [rid, node] of rightEl) {
      const l = [...pairs].find(([, v]) => v === rid)?.[0];
      node.classList.toggle("is-paired", l != null);
      node.classList.toggle("is-wrong", l != null && wrongSet.has(l));
      node.style.setProperty("--pair", l != null ? colorOf.get(l) : "transparent");
      const b = node.querySelector(".act-badge");
      b.hidden = l == null; b.textContent = l != null ? String([...pairs.keys()].indexOf(l) + 1) : ""; b.style.background = l != null ? colorOf.get(l) : "";
    }
    drawLinks();
  }
  function drawLinks() {
    if (mode !== "wide") return;
    svg.replaceChildren();
    const rc = root.getBoundingClientRect();
    svg.setAttribute("width", String(rc.width)); svg.setAttribute("height", String(rc.height));
    for (const [l, r] of pairs) {
      const a = leftEl.get(l)?.getBoundingClientRect(), b = rightEl.get(r)?.getBoundingClientRect();
      if (!a || !b) continue;
      const p = document.createElementNS(NS, "path");
      p.setAttribute("d", curve(a.right - rc.left, a.top + a.height / 2 - rc.top, b.left - rc.left, b.top + b.height / 2 - rc.top));
      p.setAttribute("class", `act-link${wrongSet.has(l) ? " is-wrong" : ""}`);
      p.style.stroke = wrongSet.has(l) ? "#d64545" : colorOf.get(l);
      svg.append(p);
    }
  }

  build();
  const ro = new ResizeObserver(() => { const m = root.clientWidth >= WIDE ? "wide" : "narrow"; if (m !== mode) build(); else drawLinks(); });
  ro.observe(root);
  return {
    getAnswer: () => ({ pares: Object.fromEntries(pairs) }),
    isComplete: () => pairs.size === ids.length,
    markWrong(detalhe) { wrongSet = new Set(detalhe?.erradas ?? detalhe?.pares_errados ?? []); paint(); },
    clearMarks() { wrongSet.clear(); paint(); },
    lock() { locked = true; root.classList.add("is-locked"); },
    destroy() { ro.disconnect(); flow?.destroy(); host.replaceChildren(); },
  };
}
