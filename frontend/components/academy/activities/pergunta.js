// Atividade "pergunta": opções de escolha (uma, ou várias quando act.multipla). Resposta: {escolha: [idx]}.
// Pode mostrar o exemplo ligado (fluxograma + Python) por cima quando act.mostrar_exemplo é true.
import { el } from "../../dom.js";
import { t } from "../../../services/i18n.js";
import { pickText } from "../model.js";
import { renderLinked } from "../linked-view.js";

export function mountPergunta(host, act, { exemplo, locale, say, onChange }) {
  const multi = !!act.multipla;
  const chosen = new Set();
  const group = el("div", { class: "act-options", role: multi ? "group" : "radiogroup", "aria-label": pickText(act.pergunta, locale) });
  const buttons = (act.opcoes || []).map((op, i) => {
    const b = el("button", { type: "button", class: "act-option", role: multi ? "checkbox" : "radio", "aria-checked": "false", "data-idx": String(i) },
      el("span", { class: "act-mark", "aria-hidden": "true" }), el("span", { class: "act-option-text" }, pickText(op, locale)));
    b.addEventListener("click", () => {
      if (b.disabled) return;
      if (!multi) { chosen.clear(); buttons.forEach((x) => x.setAttribute("aria-checked", "false")); }
      if (chosen.has(i)) chosen.delete(i); else chosen.add(i);
      b.setAttribute("aria-checked", String(chosen.has(i)));
      buttons.forEach((x, j) => x.classList.toggle("is-selected", chosen.has(j)));
      clearMarks();
      say(t("act.option_chosen", { text: pickText(op, locale) }));
      onChange();
    });
    // setas navegam entre as opções (grupo de rádio/caixas)
    b.addEventListener("keydown", (ev) => {
      if (ev.key !== "ArrowDown" && ev.key !== "ArrowUp") return;
      ev.preventDefault();
      buttons[(i + (ev.key === "ArrowDown" ? 1 : buttons.length - 1)) % buttons.length].focus();
    });
    return b;
  });
  group.append(...buttons);
  const pre = [];
  if (act.mostrar_exemplo === true && exemplo) { const h = el("div", { class: "act-example" }); renderLinked(h, exemplo, { locale }); pre.push(h); }
  host.replaceChildren(...pre, el("p", { class: "act-question" }, pickText(act.pergunta, locale)), ...(multi ? [el("p", { class: "act-note" }, t("act.pick_all"))] : []), group);
  function clearMarks() { buttons.forEach((b) => b.classList.remove("is-wrong")); }
  return {
    getAnswer: () => ({ escolha: [...chosen].sort((a, b) => a - b) }),
    isComplete: () => chosen.size > 0,
    markWrong() { buttons.forEach((b, i) => b.classList.toggle("is-wrong", chosen.has(i))); },
    clearMarks,
    lock() { buttons.forEach((b) => { b.disabled = true; }); },
  };
}
