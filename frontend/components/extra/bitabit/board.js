// Grelha do Bit a Bit: cabeçalho com os pesos (128 … 1), linhas que sobem, linha ativa destacada e explosão de pixels ao acertar.
// Tudo é DOM criado com el() (texto por textContent); as posições são escritas em element.style (CSSOM, permitido pela CSP).
import { el } from "../../dom.js";
import { t } from "../../../services/i18n.js";
import { reducedMotion } from "../../../services/motion.js";

const label = (row) => t(row.kind === "b2d" ? "bit.row_bd" : "bit.row_db", { bits: row.kind === "b2d" ? row.value.toString(2).padStart(row.bits, "0") : row.value });
const STEP = 4; // a posição vertical anda de 4 em 4 px: o movimento "salta" como pixel art

export function createBoard(host, { capacity }) {
  let cols = 4, rowH = 40;
  const rows = new Map(); // índice da linha -> {row, node, cells, val}
  const head = el("div", { class: "bit-head", "aria-hidden": "true" });
  const fx = el("div", { class: "bit-fx", "aria-hidden": "true" });
  const stage = el("div", { class: "bit-stage__rows" }, el("div", { class: "bit-danger", "aria-hidden": "true" }), fx);
  host.replaceChildren(head, stage);
  host.style.setProperty("--cap", String(capacity));

  const measure = () => { rowH = stage.clientHeight / capacity || 40; };
  if (typeof ResizeObserver !== "undefined") new ResizeObserver(measure).observe(stage);
  measure();

  function paintHead() {
    head.style.setProperty("--cols", String(cols));
    head.replaceChildren(...Array.from({ length: cols }, (_, i) => el("span", { class: "bit-head__w", "data-col": cols - 1 - i }, String(2 ** (cols - 1 - i)))), el("span", { class: "bit-head__w bit-head__eq" }, "="));
  }

  function build(row) {
    const pad = cols - row.bits;
    const cells = Array.from({ length: row.bits }, (_, i) => el("span", { class: "bit-cell", "data-col": row.bits - 1 - i }));
    const val = el("span", { class: "bit-val" });
    const node = el("div", { class: "bit-row", "data-kind": row.kind, role: "img", "aria-label": label(row) },
      Array.from({ length: pad }, () => el("span", { class: "bit-void" })), cells, val);
    node.style.setProperty("--cols", String(cols));
    const r = { row, node, cells, val };
    if (row.kind === "b2d") { cells.forEach((c, i) => c.classList.toggle("is-on", ((row.value >> (row.bits - 1 - i)) & 1) === 1)); val.textContent = "?"; }
    else val.textContent = String(row.value);
    return r;
  }

  function setCols(n) {
    if (n === cols && head.childElementCount) return;
    cols = n; paintHead();
    for (const r of rows.values()) { const fresh = build(r.row); r.node.replaceWith(fresh.node); Object.assign(r, fresh); }
  }

  return {
    stage,
    addRow(row, pendingBits) {
      setCols(Math.max(cols, pendingBits));
      const r = build(row);
      rows.set(row.row, r);
      stage.append(r.node);
      this.place(row);
    },
    place(row) {
      const r = rows.get(row.row); if (!r) return;
      const y = reducedMotion() ? Math.round(capacity - 1 - Math.floor(row.p)) * rowH : (capacity - 1 - row.p) * rowH;
      r.node.style.transform = `translateY(${Math.round(y / STEP) * STEP}px)`;
      r.node.classList.toggle("is-danger", capacity - 1 - row.p < 2.2);
    },
    shrinkTo(n) { if (n < cols) setCols(n); },
    // linha ativa: bits escolhidos (dec->bin), texto digitado (bin->dec) e coluna do cursor
    paintActive(row, { bits, buf, cursor, focus = true }) {
      for (const r of rows.values()) r.node.classList.toggle("is-active", r.row === row);
      const r = rows.get(row.row); if (!r) return;
      if (row.kind === "d2b") r.cells.forEach((c, i) => { c.classList.toggle("is-on", bits[i] === 1); c.classList.toggle("is-cursor", focus && i === cursor); });
      else r.val.textContent = buf === "" ? "?" : buf;
      r.node.setAttribute("aria-label", label(row));
    },
    cellAt(target) { // célula clicada -> {row, index} da linha ativa
      const node = target.closest?.(".bit-row.is-active"); if (!node) return null;
      const cell = target.closest(".bit-cell"); if (!cell) return null;
      const r = [...rows.values()].find((x) => x.node === node);
      return r ? { row: r.row, index: r.cells.indexOf(cell) } : null;
    },
    shake(row) { const r = rows.get(row.row); if (!r) return; r.node.classList.remove("anim-shake"); void r.node.offsetWidth; r.node.classList.add("anim-shake"); },
    clear(row) {
      const r = rows.get(row.row); if (!r) return;
      rows.delete(row.row);
      if (reducedMotion()) { r.node.remove(); return; }
      const y = (capacity - 1 - row.p) * rowH, w = stage.clientWidth;
      for (let i = 0; i < 18; i++) {
        const px = el("i", { class: "bit-px" });
        px.style.left = `${Math.round((w / 18) * i + 4)}px`;
        px.style.top = `${Math.round(y + rowH / 2)}px`;
        px.style.setProperty("--dx", `${Math.round((Math.random() - 0.5) * 60)}px`);
        px.style.setProperty("--dy", `${Math.round(-30 - Math.random() * 60)}px`);
        px.style.animationDelay = `${(i % 3) * 30}ms`;
        fx.append(px);
        setTimeout(() => px.remove(), 650);
      }
      r.node.classList.add("is-cleared");
      setTimeout(() => r.node.remove(), 260);
    },
    reset() { rows.clear(); for (const n of stage.querySelectorAll(".bit-row")) n.remove(); fx.replaceChildren(); cols = 4; paintHead(); },
  };
}
