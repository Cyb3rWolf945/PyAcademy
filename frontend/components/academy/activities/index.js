// Atividades da Academia: ponto de entrada comum. Cada tipo (ligar, ordenar_*, completar, pergunta) devolve
// {getAnswer, isComplete, markWrong, clearMarks, lock}; aqui tratamos do enunciado, do botão "Verificar", do pedido ao
// servidor (que corrige; a resposta certa nunca está no cliente), do feedback e da explicação.
import { el } from "../../dom.js";
import { t, getLocale } from "../../../services/i18n.js";
import { api, errorText } from "../../../services/api.js";
import { pickText } from "../model.js";
import { mountLigar } from "./ligar.js";
import { mountOrdenar } from "./ordenar.js";
import { mountCompletar } from "./completar.js";
import { mountPergunta } from "./pergunta.js";

const TYPES = {
  ligar: mountLigar, ordenar_fluxograma: mountOrdenar, ordenar_python: mountOrdenar, ordenar_lista: mountOrdenar,
  completar: mountCompletar, pergunta: mountPergunta,
};

// renderActivity(container, activityPublic, {sectionId, idx, exemplo, locale, onSolved}) -> {destroy(), solved}
export function renderActivity(container, act, { sectionId, idx, exemplo, locale = getLocale(), onSolved } = {}) {
  const mount = TYPES[act.tipo];
  const live = el("div", { class: "sr-only", role: "status", "aria-live": "polite" });
  const say = (msg) => { live.textContent = ""; setTimeout(() => { live.textContent = msg; }, 20); };
  const body = el("div", { class: "act-body-host" });
  const feedback = el("div", { class: "act-feedback", hidden: true });
  const btn = el("button", { type: "button", class: "btn-pixel btn-pixel--accent act-check" }, t("act.check"));
  const hintEl = el("p", { class: "act-note" });
  let attempts = 0, solved = false, busy = false, view = null;

  const root = el("section", { class: "act-root", "data-tipo": act.tipo, "aria-label": pickText(act.enunciado, locale) },
    el("p", { class: "act-statement" }, pickText(act.enunciado, locale)), hintEl, body, feedback, el("div", { class: "act-actions" }, btn), live);
  container.replaceChildren(root);
  if (!mount) { body.textContent = t("act.unsupported"); btn.hidden = true; return { destroy() { container.replaceChildren(); }, solved: false }; }

  const ctx = { exemplo, locale, say, onChange: () => { refresh(); clearFeedback(); } };
  view = mount(body, act, ctx);
  hintEl.textContent = view.hint || "";
  hintEl.hidden = !view.hint;

  function refresh() { btn.disabled = busy || solved || !view.isComplete(); }
  function clearFeedback() { if (!solved) { feedback.hidden = true; feedback.replaceChildren(); } }
  function show(kind, title, expl) {
    feedback.hidden = false;
    feedback.className = `act-feedback act-feedback--${kind}`;
    feedback.replaceChildren(el("p", { class: "act-feedback-title" }, `${kind === "ok" ? "✅" : kind === "no" ? "❌" : "⚠️"} ${title}`),
      ...(expl ? [el("p", { class: "act-explain" }, el("strong", {}, `${t("act.explanation")}: `), expl)] : []));
  }

  async function check() {
    if (busy || solved || !view.isComplete()) return;
    busy = true; refresh(); btn.textContent = t("act.checking");
    try {
      const res = await api("POST", `/api/academy/sections/${encodeURIComponent(sectionId)}/activities/${idx}/answer`, { resposta: view.getAnswer() });
      attempts += 1;
      const expl = res.explicacao ? pickText(res.explicacao, locale) : "";
      if (res.correta) {
        solved = true; view.clearMarks?.(); view.lock();
        show("ok", t("act.correct"), expl);
        say(`${t("act.correct")} ${expl}`);
        root.classList.add("is-solved");
        onSolved?.(res);
      } else {
        view.markWrong(res.detalhe);
        show("no", t("act.wrong"), expl || (attempts >= 2 ? "" : ""));
        say(t("act.wrong_say"));
      }
    } catch (err) {
      show("warn", errorText(err));
    } finally {
      busy = false; btn.textContent = t("act.check"); refresh();
    }
  }
  btn.addEventListener("click", check);
  refresh();
  const onLocale = () => { btn.textContent = t("act.check"); };
  document.addEventListener("localechange", onLocale);
  return { get solved() { return solved; }, destroy() { document.removeEventListener("localechange", onLocale); view?.destroy?.(); container.replaceChildren(); } };
}
