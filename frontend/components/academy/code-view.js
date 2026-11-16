// Vista Python ligada ao fluxograma: números de linha, faixa de cor à esquerda por tipo de bloco (lilás = ler/escrever/
// definir/calcular, azul-escuro = decisões e ciclos) e realce de todas as linhas do mesmo bloco. Fonte monoespaçada normal.
import { el } from "../dom.js";
import { toPython, familyOf } from "./model.js";

const KEYWORDS = new Set(["if", "elif", "else", "while", "for", "in", "and", "or", "not", "True", "False", "None", "def", "return"]);
const BUILTINS = new Set(["print", "input", "float", "int", "str", "range", "round", "len"]);

// Colorização mínima por tokens: cada pedaço vira um <span> com textContent (nunca HTML em bruto)
export function tokens(code) {
  const out = [];
  const re = /(#.*$)|("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|(\b\d+(?:\.\d+)?\b)|([A-Za-z_]\w*)|(\s+)|(.)/g;
  for (const m of code.matchAll(re)) {
    const [txt, com, str, num, word] = m;
    let cls = "";
    if (com) cls = "fx-com"; else if (str) cls = "fx-str"; else if (num) cls = "fx-num";
    else if (word) cls = KEYWORDS.has(word) ? "fx-kw" : BUILTINS.has(word) ? "fx-fn" : "";
    out.push(cls ? el("span", { class: cls }, txt) : txt);
    if (!str && !com && (txt === "(" || txt === "," || txt === "[")) out.push(el("wbr")); // permite quebrar depois de ( , [ sem mudar o texto
  }
  return out;
}

// renderCode(container, program, {locale, onSelect}) -> {select(stmtId), clear(), destroy(), lines}
export function renderCode(container, program, { onSelect } = {}) {
  const lines = toPython(program);
  const byStmt = new Map();
  const rows = lines.map((ln) => {
    if (ln.stmtId == null) return el("div", { class: "fx-line fx-blank", "aria-hidden": "true" }, el("span", { class: "fx-ln" }, String(ln.line)), el("span", { class: "fx-src" }, " "));
    const row = el("div", {
      class: `fx-line fx-k-${familyOf(ln.tipo)}`, role: "button", tabindex: 0, "data-stmt": ln.stmtId, "aria-pressed": "false",
      "aria-label": `${ln.line}: ${ln.text}`,
    }, el("span", { class: "fx-ln", "aria-hidden": "true" }, String(ln.line)), el("span", { class: "fx-src" }, "    ".repeat(ln.indent), ...tokens(ln.code)));
    const pick = () => { select(ln.stmtId); onSelect?.(ln.stmtId); };
    row.addEventListener("click", pick);
    row.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); pick(); } });
    if (!byStmt.has(ln.stmtId)) byStmt.set(ln.stmtId, []);
    byStmt.get(ln.stmtId).push(row);
    return row;
  });
  const box = el("div", { class: "fx-code", role: "group", "aria-label": "Python" }, ...rows);
  container.replaceChildren(box);

  let current = null;
  function clear() {
    for (const r of byStmt.get(current) || []) { r.classList.remove("is-selected"); r.setAttribute("aria-pressed", "false"); }
    current = null;
  }
  function select(id, { scroll = false } = {}) {
    clear();
    const rs = byStmt.get(id);
    if (!rs) return;
    current = id;
    rs.forEach((r) => { r.classList.add("is-selected"); r.setAttribute("aria-pressed", "true"); });
    if (scroll) rs[0].scrollIntoView?.({ block: "nearest", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }
  return { select, clear, destroy() { container.replaceChildren(); }, lines, has: (id) => byStmt.has(id) };
}

