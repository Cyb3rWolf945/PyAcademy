// Atividades "ordenar": fluxograma (blocos com as formas dos slides), Python (linhas de código) e lista (cartões simples).
// O servidor manda os itens já baralhados; a ordem certa nunca está no cliente. Resposta: {ordem: [id...]}.
import { el } from "../../dom.js";
import { t } from "../../../services/i18n.js";
import { pickText } from "../model.js";
import { makeSortable } from "./sortable.js";
import { stmtMap, flowBlock, firstLines, codeCard } from "./blocks.js";

// act.itens: ids (ordenar_fluxograma / ordenar_python) ou [{id, texto}] (ordenar_lista), já baralhados pelo servidor
export function mountOrdenar(host, act, { exemplo, locale, say, onChange }) {
  const raw = act.itens || act.ids || [];
  const ids = raw.map((x) => (typeof x === "object" ? x.id : x));
  const textOf = new Map(raw.filter((x) => typeof x === "object").map((x) => [x.id, pickText(x.texto, locale)]));
  const stmts = stmtMap(exemplo);
  const lines = firstLines(exemplo || { corpo: [] });
  const labelOf = (id) => textOf.get(id) ?? (act.tipo === "ordenar_python" ? lines.get(id)?.code : pickText(stmts.get(id)?.texto ?? stmts.get(id)?.cond, locale)) ?? String(id);
  const renderItem = (id) => {
    if (act.tipo === "ordenar_fluxograma" && stmts.get(id)) return flowBlock(stmts.get(id), locale);
    if (act.tipo === "ordenar_python" && lines.get(id)) return codeCard(lines.get(id));
    return el("span", { class: "act-text" }, labelOf(id));
  };
  const box = el("div", { class: `act-order act-order--${act.tipo}` });
  host.replaceChildren(box);
  const sortable = makeSortable(box, { ids, renderItem, labelOf, say, onChange });
  return {
    getAnswer: () => ({ ordem: sortable.getOrder() }),
    isComplete: () => true,
    markWrong(detalhe) { sortable.setWrong(detalhe?.erradas ?? detalhe?.posicoes_erradas ?? detalhe?.posicoes ?? []); },
    clearMarks: sortable.clearMarks,
    lock: sortable.lock,
    hint: t("act.sort_hint"),
  };
}
