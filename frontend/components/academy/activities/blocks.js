// Peças visuais das atividades: bloco com a forma limpa do fluxograma (mesmas cores dos slides, em HTML+CSS para
// poder levar campos de texto) e cartão de uma linha de Python. Nada de pixel art.
import { el } from "../../dom.js";
import { familyOf, labelOf, toPython, allStmts, funcaoStmt, pickText } from "../model.js";
import { tokens } from "../code-view.js";

// Instruções (principal e funções) e as próprias funções como pseudo-instruções (pílula de início)
export const stmtMap = (exemplo) => new Map([...(exemplo?.funcoes || []).map(funcaoStmt), ...allStmts(exemplo || {})].map((s) => [s.id, s]));

// Bloco com forma de fluxograma; `content` = nós (texto, inputs...)
export function shapeBlock(tipo, content) {
  const fam = familyOf(tipo);
  return el("div", { class: `act-shape act-shape--${fam}${tipo === "chamar" ? " act-shape--call" : ""}` }, el("span", { class: "act-shape-text" }, ...[].concat(content)));
}

export const flowBlock = (stmt, locale) => shapeBlock(stmt.tipo, labelOf(stmt, locale));

// Primeira linha de Python de cada instrução (um `se` tem várias; para ordenar/ligar usamos a do `if`)
export function firstLines(exemplo) {
  const out = new Map();
  for (const ln of toPython(exemplo)) if (ln.stmtId && !out.has(ln.stmtId)) out.set(ln.stmtId, ln);
  return out;
}

// Cartão com uma linha de código colorida (sem número de linha, porque a ordem é o que se pede)
export function codeCard(ln) {
  return el("div", { class: `act-code fx-k-${familyOf(ln.tipo)}` }, el("span", { class: "fx-src" }, "    ".repeat(ln.indent), ...tokens(ln.code)));
}

export { pickText };
