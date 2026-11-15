// Barra de símbolos para o telemóvel: aparece por cima do teclado (visualViewport) com os caracteres difíceis de escrever.
// Os botões não roubam o foco ao editor, por isso o teclado nunca fecha.
import { el } from "./dom.js";
import { t } from "../services/i18n.js";

export const isTouch = () => matchMedia("(pointer: coarse)").matches || navigator.maxTouchPoints > 0;

const SYMBOLS = [":", "(", ")", "[", "]", '"', "'", "=", "#", ","];

// mountSymbolBar(editor, {force}) -> {destroy()} · editor = {insert, indent, dedent, left, right}
// host: elemento onde a barra fica "em linha" (por cima do botão Submeter, sem tapar nada). Sem host, fica fixa sobre o teclado.
export function mountSymbolBar(editor, { force = false, host = null } = {}) {
  if (!force && !isTouch()) return { destroy() {} };
  const btn = (label, action, aria) => el("button", {
    type: "button", class: "btn-pixel btn-pixel--ghost min-h-[44px] min-w-[44px] shrink-0 px-2", "aria-label": aria || label,
    onmousedown: (e) => e.preventDefault(), onpointerdown: (e) => e.preventDefault(),
    onclick: () => action(),
  }, label);
  const inline = !!host;
  host = host || document.body;
  const bar = el("div", { class: `${inline ? "" : "fixed inset-x-0 z-50"} flex gap-1 overflow-x-auto bg-surface-2 p-1`, role: "toolbar", "aria-label": t("editor.symbols") },
    btn("Tab ⇥", () => editor.indent(), t("editor.indent")),
    btn("⇤", () => editor.dedent(), t("editor.dedent")),
    ...SYMBOLS.map((s) => btn(s, () => editor.insert(s))),
    btn("←", () => editor.left(), t("editor.left")),
    btn("→", () => editor.right(), t("editor.right")));
  bar.hidden = true;
  host.append(bar);

  const vv = window.visualViewport;
  function place() {
    if (inline) return;
    const h = bar.offsetHeight || 52;
    const top = vv ? vv.offsetTop + vv.height - h : innerHeight - h;
    bar.style.top = `${Math.max(0, top)}px`;
  }
  const onFocus = (e) => { if (e.target.closest?.("[data-code-input]")) { bar.hidden = false; place(); } };
  const onBlur = () => setTimeout(() => {
    if (!document.activeElement?.closest?.("[data-code-input]")) bar.hidden = true;
  }, 150);
  document.addEventListener("focusin", onFocus);
  document.addEventListener("focusout", onBlur);
  vv?.addEventListener("resize", place);
  vv?.addEventListener("scroll", place);
  return {
    destroy() {
      document.removeEventListener("focusin", onFocus);
      document.removeEventListener("focusout", onBlur);
      vv?.removeEventListener("resize", place);
      vv?.removeEventListener("scroll", place);
      bar.remove();
    },
  };
}
