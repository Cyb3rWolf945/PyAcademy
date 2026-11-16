// Auxiliar de código: sugestões locais para nomes e funções do exercício, aberto com Ctrl+Space ou Cmd+Space.
import { el } from "./dom.js";
import { t } from "../services/i18n.js";
import { pick } from "../pages/challenge/lib.js";

const BUILTINS = [
  ["abs()", "Python"], ["enumerate()", "Python"], ["float()", "Python"], ["int()", "Python"],
  ["len()", "Python"], ["max()", "Python"], ["min()", "Python"], ["range()", "Python"],
  ["round()", "Python"], ["sorted()", "Python"], ["sum()", "Python"], ["zip()", "Python"],
];
const STRUCTURES = [
  { label: "if ...:", insert: "if :\n    ", cursorOffset: 3, detail: "editor.helper_condition" },
  { label: "elif ...:", insert: "elif :\n    ", cursorOffset: 5, detail: "editor.helper_condition" },
  { label: "else:", insert: "else:\n    ", cursorOffset: 10, detail: "editor.helper_condition" },
  { label: "for ... in ...:", insert: "for item in items:\n    ", cursorOffset: 4, detail: "editor.helper_loop" },
  { label: "while ...:", insert: "while :\n    ", cursorOffset: 6, detail: "editor.helper_loop" },
];
const RESERVED = new Set([
  "and", "as", "assert", "break", "class", "continue", "def", "elif", "else", "False",
  "for", "from", "if", "import", "in", "is", "None", "not", "or", "pass", "raise",
  "return", "True", "try", "while", "with", "yield",
]);

function addDeclaredIdentifiers(target, value, detail) {
  const source = String(value ?? "");
  const add = (name) => {
    if (name && !RESERVED.has(name) && name.length > 1) target.set(name, detail);
  };
  const addList = (value) => {
    for (const name of String(value).matchAll(/[A-Za-z_][A-Za-z0-9_]*/g)) add(name[0]);
  };

  for (const match of source.matchAll(/^\s*def\s+[A-Za-z_][A-Za-z0-9_]*\s*\(([^)]*)\)/gm)) addList(match[1]);
  for (const match of source.matchAll(/^\s*(?:async\s+)?for\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\b/gm)) add(match[1]);
  for (const match of source.matchAll(/^\s*(?:if|elif|while)\s+([A-Za-z_][A-Za-z0-9_]*)\s*:/gm)) add(match[1]);
  for (const match of source.matchAll(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:=|\+=|-=|\*=|\/=|\/\/=|%=)/gm)) add(match[1]);
  for (const match of source.matchAll(/^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)/gm)) add(match[1]);

  for (const match of source.matchAll(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*,/gm)) add(match[1]);
  for (const match of source.matchAll(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=/gm)) add(match[1]);
}

function addDeclaredContextIdentifiers(target, value, detail) {
  const source = String(value ?? "");
  for (const match of source.matchAll(/\b(?:variável|variavel|variable|lista|list|função|funcao|function)\s+([A-Za-z_][A-Za-z0-9_]*)\b/gi)) {
    const name = match[1];
    if (!RESERVED.has(name) && name.length > 1) target.set(name, detail);
  }
}

function suggestions(mission, editor) {
  const items = new Map();
  const codeItems = new Map();
  addDeclaredIdentifiers(codeItems, editor.getValue(), t("editor.helper_your_code"));
  for (const [name, detail] of codeItems) items.set(name, { detail, insert: name });
  for (const structure of STRUCTURES) {
    items.set(structure.label, { detail: t(structure.detail), insert: structure.insert, cursorOffset: structure.cursorOffset });
  }
  for (const [label, detail] of BUILTINS) items.set(label, { detail, insert: label });
  const signature = String(mission.assinatura ?? "");
  const functionName = /^[A-Za-z_][A-Za-z0-9_]*/.exec(signature)?.[0];
  if (functionName) items.set(`${functionName}()`, { detail: t("editor.helper_exercise_function"), insert: `${functionName}()` });
  const defined = mission.requisitos?.define_funcao?.nome;
  if (defined) items.set(`${defined}()`, { detail: t("editor.helper_exercise_function"), insert: `${defined}()` });
  const contextItems = new Map();
  addDeclaredIdentifiers(contextItems, signature, t("editor.helper_exercise_function"));
  addDeclaredContextIdentifiers(contextItems, pick(mission.enunciado), t("editor.helper_exercise_word"));
  for (const [name, detail] of contextItems) {
    if (!items.has(name)) items.set(name, { detail, insert: name });
  }
  return [...items.entries()].map(([label, value]) => ({ label, ...value }));
}

export function mountCodeHelper(host, { mission, editor, panelHost = host }) {
  const panel = el("section", { class: "panel-pixel fixed z-[70] hidden max-h-[min(50dvh,360px)] min-w-[220px] max-w-[min(90vw,360px)] overflow-hidden p-1 shadow-pixel", role: "dialog", "aria-label": t("editor.helper_title") });
  document.body.append(panel);
  let visible = false;
  let selected = 0;
  let current = [];
  let optionsList = null;

  function close() {
    visible = false;
    panel.classList.add("hidden");
    panel.replaceChildren();
  }

  function choose(index) {
    const option = current[index];
    if (!option) return;
    const context = editor.getCompletionContext();
    const insert = option.insert ?? option.label;
    const suffix = insert.startsWith(context.prefix) ? insert.slice(context.prefix.length) : insert;
    const cursorOffset = option.cursorOffset ?? (option.label.endsWith("()") ? Math.max(0, suffix.length - 1) : suffix.length);
    editor.insertCompletion(suffix, context.from, cursorOffset);
    close();
  }

  function paint() {
    const options = current.length
      ? el("div", { class: "grid max-h-[min(40dvh,280px)] gap-1 overflow-y-auto", role: "listbox" },
        current.map((item, index) => el("button", {
          type: "button", class: `flex min-h-[44px] items-center justify-between gap-3 px-2 py-2 text-left font-mono ${index === selected ? "bg-surface-2 text-accent" : ""}`,
          "aria-selected": String(index === selected),
          onclick: () => choose(index),
        }, el("span", {}, item.label), el("span", { class: "text-xs text-muted" }, item.detail))))
      : el("p", { class: "p-2 text-sm text-muted" }, t("editor.helper_no_match"));
    optionsList = options instanceof HTMLElement ? options : null;
    panel.replaceChildren(
      el("div", { class: "flex items-center justify-between gap-2 border-b-2 border-surface-2 pb-2" },
        el("strong", {}, t("editor.helper_title")),
        el("button", { type: "button", class: "btn-pixel btn-pixel--ghost min-h-[44px] px-3", "aria-label": t("editor.helper_close"), onclick: close }, "×")),
      el("p", { class: "p-2 text-xs text-muted" }, t("editor.helper_hint")),
      options,
    );
    optionsList?.children[selected]?.scrollIntoView({ block: "nearest" });
    panel.classList.remove("hidden");
    const position = editor.getCompletionPosition?.();
    if (position) {
      const width = Math.min(360, Math.max(220, window.innerWidth - 16));
      const left = Math.min(Math.max(8, position.left), Math.max(8, window.innerWidth - width - 8));
      const top = Math.min(position.top + position.height + 4, Math.max(8, window.innerHeight - 360));
      panel.style.width = `${width}px`;
      panel.style.left = `${left}px`;
      panel.style.top = `${top}px`;
    }
  }

  function open() {
    const context = editor.getCompletionContext();
    const all = suggestions(mission, editor);
    const prefix = context.prefix.toLowerCase();
    current = all.filter((item) => item.label.toLowerCase().startsWith(prefix)).slice(0, 12);
    selected = 0;
    visible = true;
    paint();
  }

  function onKeydown(event) {
    if ((event.ctrlKey || event.metaKey) && event.code === "Space") {
      event.preventDefault();
      open();
      return;
    }
    if (!visible) return;
    if (event.key === "Escape") { event.preventDefault(); close(); }
    else if (event.key === "ArrowDown") { event.preventDefault(); selected = Math.min(selected + 1, current.length - 1); paint(); }
    else if (event.key === "ArrowUp") { event.preventDefault(); selected = Math.max(selected - 1, 0); paint(); }
    else if (event.key === "Enter" && current.length) { event.preventDefault(); choose(selected); }
  }

  const onDocumentKeydown = (event) => {
    if (event.composedPath().includes(host)) onKeydown(event);
  };
  document.addEventListener("keydown", onDocumentKeydown, true);
  return { destroy: () => { document.removeEventListener("keydown", onDocumentKeydown, true); panel.remove(); } };
}
