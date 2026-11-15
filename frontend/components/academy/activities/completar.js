// Atividade "completar": a instrução com campos de texto nos "___" (Python em fonte mono; fluxograma dentro da forma do bloco).
// O servidor só manda o modelo; as respostas certas nunca estão no cliente. Resposta: {valores: ["3", ...]}.
import { el } from "../../dom.js";
import { t } from "../../../services/i18n.js";
import { pickText } from "../model.js";
import { stmtMap, shapeBlock } from "./blocks.js";

export function mountCompletar(host, act, { exemplo, locale, say, onChange }) {
  const stmts = stmtMap(exemplo);
  const inputs = [];
  const cards = (act.lacunas || []).map((lac, i) => {
    const parts = pickText(lac.modelo, locale).split("___");
    const content = [];
    parts.forEach((txt, k) => {
      if (txt) content.push(txt);
      if (k < parts.length - 1) {
        const inp = el("input", { type: "text", class: "act-blank", maxlength: 40, autocomplete: "off", autocapitalize: "none", spellcheck: "false", inputmode: "text", "aria-label": t("act.blank_n", { n: inputs.length + 1 }) });
        inp.addEventListener("input", () => { clearMarks(); onChange(); });
        inp.addEventListener("keydown", (ev) => { if (ev.key === "Enter") { ev.preventDefault(); inputs[inputs.indexOf(inp) + 1]?.focus(); } });
        inputs.push(inp);
        content.push(inp);
      }
    });
    const stmt = stmts.get(lac.stmt);
    const body = lac.lado === "fluxo"
      ? shapeBlock(stmt?.tipo || "calcular", content)
      : el("div", { class: "act-code act-code--fill" }, el("span", { class: "fx-src" }, ...content));
    return el("div", { class: "act-blank-card", "data-lado": lac.lado }, el("span", { class: "act-side" }, lac.lado === "fluxo" ? t("fx.flowchart") : t("fx.python")), body);
  });
  host.replaceChildren(el("div", { class: "act-blanks" }, ...cards));
  const wrongOf = new Map(); // índice da lacuna -> input
  // um campo por "___": mapeamos as lacunas aos seus inputs (normalmente 1 por lacuna)
  let n = 0;
  (act.lacunas || []).forEach((lac, i) => { const k = pickText(lac.modelo, locale).split("___").length - 1; for (let j = 0; j < k; j++) wrongOf.set(n++, i); });
  function clearMarks() { inputs.forEach((x) => x.classList.remove("is-wrong")); }
  return {
    getAnswer: () => ({ valores: inputs.map((x) => x.value.trim()) }),
    isComplete: () => inputs.every((x) => x.value.trim() !== ""),
    markWrong(detalhe) {
      clearMarks();
      const bad = detalhe?.erradas ?? detalhe?.lacunas ?? [];
      inputs.forEach((x, k) => { if (bad.includes(wrongOf.get(k)) || bad.includes(k)) x.classList.add("is-wrong"); });
    },
    clearMarks,
    lock() { inputs.forEach((x) => { x.disabled = true; }); },
  };
}
