// Editor do aluno: CodeMirror 6 (carregado só aqui, com import dinâmico) para os tipos com código, com textarea
// de reserva se o bundle falhar; e formulários de opções/texto para quiz, decomposição e traçar.
import { el } from "./dom.js";
import { t } from "../services/i18n.js";
import { pick } from "../pages/challenge/lib.js";
import { mountSymbolBar } from "./symbol-bar.js";

let cmPromise = null;
const loadCodeMirror = () => (cmPromise ??= import("/vendor/codemirror/codemirror.js?v=53752894").catch((e) => { cmPromise = null; throw e; }));

// Editor de reserva: textarea simples com as mesmas operações (indent/dedent/insert...)
function textareaEditor(host, { doc, onChange, readOnly, ariaLabel }) {
  const ta = el("textarea", {
    class: "input-pixel h-full min-h-[40dvh] resize-none font-mono", spellcheck: "false", autocapitalize: "off", autocomplete: "off",
    "aria-label": ariaLabel, "data-code-input": "1", readonly: readOnly,
  });
  ta.value = doc;
  ta.addEventListener("input", () => onChange?.(ta.value));
  ta.addEventListener("keydown", (e) => {
    if (e.key === "Tab") { e.preventDefault(); insert(e.shiftKey ? "" : "    "); }
  });
  host.replaceChildren(ta);
  function insert(text) {
    const { selectionStart: s, selectionEnd: e } = ta;
    ta.setRangeText(text, s, e, "end");
    ta.dispatchEvent(new Event("input"));
    ta.focus();
  }
  const move = (d) => { ta.focus(); ta.setSelectionRange(ta.selectionStart + d, ta.selectionStart + d); };
  return {
    getValue: () => ta.value,
    setValue: (v) => { ta.value = v; onChange?.(v); },
    focus: () => ta.focus(), insert,
    indent: () => insert("    "),
    dedent: () => {
      const v = ta.value, s = ta.selectionStart;
      const ls = v.lastIndexOf("\n", s - 1) + 1;
      const m = /^ {1,4}/.exec(v.slice(ls));
      if (m) { ta.setRangeText("", ls, ls + m[0].length, "preserve"); ta.dispatchEvent(new Event("input")); }
      ta.focus();
    },
    left: () => move(-1), right: () => move(1),
    setReadOnly: (v) => { ta.readOnly = v; },
    destroy: () => host.replaceChildren(),
  };
}

// O CodeMirror injeta um <style> no documento, o que a nossa CSP (style-src 'self') bloqueia. Dentro de um Shadow DOM
// usa folhas de estilo "adotadas" (CSSStyleSheet), que a CSP permite. Sem esse suporte, cai para o textarea simples.
const canShadow = () => "attachShadow" in Element.prototype && typeof CSSStyleSheet !== "undefined"
  && "replaceSync" in CSSStyleSheet.prototype && "adoptedStyleSheets" in Document.prototype;

// mountCodeEditor(host, {value, onChange, readOnly, ariaLabel, symbolBar}) -> Promise<editor>
export async function mountCodeEditor(host, { value = "", onChange, readOnly = false, ariaLabel = "", symbolBar = true, symbolHost = null } = {}) {
  host.setAttribute("data-code-input", "1"); // a barra de símbolos reconhece o foco por aqui (o foco dentro do Shadow DOM é "retargeted")
  let ed = null;
  if (canShadow()) {
    try {
      const cm = await loadCodeMirror();
      const root = host.attachShadow({ mode: "open" });
      const sheet = new CSSStyleSheet();
      sheet.replaceSync(":host{display:block;height:100%} .wrap{height:100%}");
      root.adoptedStyleSheets = [sheet];
      const wrap = document.createElement("div");
      wrap.className = "wrap";
      root.append(wrap);
      ed = cm.createEditor(wrap, { doc: value, onChange, readOnly, ariaLabel, placeholderText: t("editor.placeholder") });
    } catch (_) { ed = null; }
  }
  if (!ed) ed = textareaEditor(host, { doc: value, onChange, readOnly, ariaLabel });
  const bar = symbolBar ? mountSymbolBar(ed, { host: symbolHost }) : { destroy() {} };
  const destroy = ed.destroy;
  ed.destroy = () => { bar.destroy(); destroy(); };
  return ed;
}

// Formulário de perguntas (quiz/decomposição/traçar). Devolve {getAnswers(), setAnswers(a), setDisabled(b)}.
// Resposta por pergunta: lista de índices (com opções) ou texto. A resposta certa nunca chega ao cliente.
export function mountQuestions(host, perguntas, { answers = null, onChange, readOnly = false } = {}) {
  const state = perguntas.map((q, i) => (answers && answers[i] != null ? answers[i] : q.opcoes ? [] : ""));
  const controls = [];
  const emit = () => onChange?.(state.map((s) => (Array.isArray(s) ? [...s] : s)));

  const blocks = perguntas.map((q, qi) => {
    const head = el("div", { class: "grid gap-2" },
      el("p", { class: "font-bold" }, `${qi + 1}. ${pick(q.pergunta)}`),
      q.codigo ? el("pre", { class: "overflow-x-auto bg-surface-2 p-3 text-sm font-mono whitespace-pre" }, q.codigo) : null);
    let body;
    if (q.opcoes) {
      body = el("div", { class: "grid gap-2", role: "group" }, el("p", { class: "text-xs text-muted" }, t("editor.pick_all")),
        q.opcoes.map((opt, oi) => {
          const input = el("input", { type: "checkbox", class: "h-5 w-5 shrink-0 accent-[var(--c-accent)]", checked: state[qi].includes(oi) });
          input.addEventListener("change", () => {
            const set = new Set(state[qi]);
            if (input.checked) set.add(oi); else set.delete(oi);
            state[qi] = [...set].sort((a, b) => a - b);
            emit();
          });
          controls.push(input);
          return el("label", { class: "flex min-h-[44px] items-center gap-3 bg-surface-2 px-3 py-2" }, input, el("span", { class: "font-mono" }, pick(opt)));
        }));
    } else {
      const input = el("input", { class: "input-pixel", type: "text", maxlength: 500, value: state[qi], autocapitalize: "off", autocomplete: "off", "aria-label": t("editor.your_answer") });
      input.addEventListener("input", () => { state[qi] = input.value; emit(); });
      controls.push(input);
      body = input;
    }
    return el("section", { class: "panel-pixel grid gap-3" }, head, body);
  });
  host.replaceChildren(...blocks);
  const setDisabled = (d) => controls.forEach((c) => { c.disabled = d; });
  setDisabled(readOnly);
  return { getAnswers: () => state.map((s) => (Array.isArray(s) ? [...s] : s)), setDisabled };
}
