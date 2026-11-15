// Vista ligada: fluxograma e Python lado a lado (≥ 768 px) ou empilhados (telemóvel, fluxograma primeiro).
// Selecionar um bloco/linha num lado realça o correspondente no outro e leva-o para a vista.
import { el } from "../dom.js";
import { t } from "../../services/i18n.js";
import { renderFlowchart } from "./flowchart.js";
import { renderCode } from "./code-view.js";

// renderLinked(container, program, {locale, onSelect}) -> {select(stmtId), clear(), destroy(), selected}
export function renderLinked(container, program, { locale, onSelect } = {}) {
  const flowHost = el("div"), codeHost = el("div");
  const wrap = el("div", { class: "fx-linked" },
    el("section", { "aria-label": t("fx.flowchart") }, el("h3", { class: "fx-h" }, t("fx.flowchart")), flowHost),
    el("section", { "aria-label": t("fx.python") }, el("h3", { class: "fx-h" }, t("fx.python")), codeHost));
  container.classList.add("fx-linked-root");
  container.replaceChildren(wrap);

  let flow = null, code = null, selected = null;
  const both = (id, from) => {
    selected = id;
    if (from !== "flow") flow.select(id, { scroll: true }); else flow.select(id);
    if (from !== "code") code.select(id, { scroll: true }); else code.select(id);
    onSelect?.(id);
  };
  flow = renderFlowchart(flowHost, program, { locale, onSelect: (id) => both(id, "flow") });
  code = renderCode(codeHost, program, { locale, onSelect: (id) => both(id, "code") });
  return {
    select: (id) => both(id, "api"),
    clear() { flow.clear(); code.clear(); selected = null; },
    destroy() { flow.destroy(); code.destroy(); container.replaceChildren(); },
    get selected() { return selected; },
  };
}
