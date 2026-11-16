// Ponto de entrada do bundle CodeMirror 6 (Python + configuração básica). Compilado com esbuild: ver README.md.
import { EditorState, Compartment } from "@codemirror/state";
import {
  EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter, drawSelection, placeholder,
} from "@codemirror/view";
import {
  defaultKeymap, history, historyKeymap, indentWithTab, indentMore, indentLess,
  cursorCharLeft, cursorCharRight, cursorLineUp, cursorLineDown,
} from "@codemirror/commands";
import {
  indentUnit, indentOnInput, bracketMatching, syntaxHighlighting, HighlightStyle,
} from "@codemirror/language";
import { closeBrackets, closeBracketsKeymap } from "@codemirror/autocomplete";
import { python } from "@codemirror/lang-python";
import { tags as t } from "@lezer/highlight";

// Tema: só variáveis CSS do tema da app (--c-*), por isso acompanha as mudanças de tema sem recompilar.
const theme = EditorView.theme({
  "&": { color: "var(--c-text)", backgroundColor: "var(--c-bg)", fontSize: "15px", height: "100%" },
  ".cm-scroller": { fontFamily: "var(--f-mono, ui-monospace, Menlo, Consolas, monospace)", lineHeight: "1.5", overflow: "auto" },
  ".cm-content": { caretColor: "var(--c-accent)", padding: "8px 0" },
  ".cm-cursor, .cm-dropCursor": { borderLeftColor: "var(--c-accent)", borderLeftWidth: "2px" },
  "&.cm-focused": { outline: "3px solid var(--c-accent)", outlineOffset: "-3px" },
  "&.cm-focused > .cm-scroller > .cm-selectionLayer .cm-selectionBackground, .cm-selectionBackground, ::selection": {
    backgroundColor: "color-mix(in srgb, var(--c-accent) 35%, transparent)",
  },
  ".cm-activeLine": { backgroundColor: "color-mix(in srgb, var(--c-surface-2) 55%, transparent)" },
  ".cm-gutters": { backgroundColor: "var(--c-surface)", color: "var(--c-muted)", border: "0" },
  ".cm-activeLineGutter": { backgroundColor: "var(--c-surface-2)", color: "var(--c-text)" },
  ".cm-matchingBracket": { backgroundColor: "color-mix(in srgb, var(--c-accent) 40%, transparent)", outline: "1px solid var(--c-accent)" },
  ".cm-nonmatchingBracket": { backgroundColor: "color-mix(in srgb, var(--c-danger) 40%, transparent)" },
  ".cm-placeholder": { color: "var(--c-muted)" },
});

const highlight = HighlightStyle.define([
  { tag: [t.keyword, t.controlKeyword, t.definitionKeyword, t.moduleKeyword, t.operatorKeyword], color: "var(--c-accent)", fontWeight: "bold" },
  { tag: [t.string, t.special(t.string)], color: "var(--c-success)" },
  { tag: [t.number, t.bool, t.null], color: "var(--c-gold, var(--c-accent))" },
  { tag: [t.comment, t.lineComment], color: "var(--c-muted)", fontStyle: "italic" },
  { tag: [t.function(t.variableName), t.definition(t.variableName)], color: "var(--c-accent-2, var(--c-text))" },
  { tag: [t.self, t.className], color: "var(--c-accent-2, var(--c-text))" },
]);

const readOnlyC = new Compartment();

// Cria o editor. Devolve um objeto pequeno e estável (a app não precisa de conhecer o CodeMirror).
export function createEditor(parent, { doc = "", onChange, readOnly = false, placeholderText = "", ariaLabel = "" } = {}) {
  const view = new EditorView({
    parent,
    state: EditorState.create({
      doc,
      extensions: [
        lineNumbers(), highlightActiveLine(), highlightActiveLineGutter(), history(), drawSelection(),
        indentUnit.of("    "), EditorState.tabSize.of(4), indentOnInput(), bracketMatching(), closeBrackets(),
        python(), syntaxHighlighting(highlight), theme, EditorView.lineWrapping,
        keymap.of([...closeBracketsKeymap, ...defaultKeymap, ...historyKeymap, indentWithTab]),
        placeholder(placeholderText),
        EditorView.contentAttributes.of({ "aria-label": ariaLabel, autocapitalize: "off", autocorrect: "off", spellcheck: "false" }),
        readOnlyC.of(EditorState.readOnly.of(readOnly)),
        EditorView.updateListener.of((u) => { if (u.docChanged && onChange) onChange(u.state.doc.toString()); }),
      ],
    }),
  });
  const run = (cmd) => { cmd(view); view.focus(); };
  return {
    view,
    getValue: () => view.state.doc.toString(),
    getCompletionContext: () => {
      const { head } = view.state.selection.main;
      const line = view.state.doc.lineAt(head);
      const before = line.text.slice(0, head - line.from);
      const match = /[A-Za-z_][A-Za-z0-9_]*$/.exec(before);
      return { prefix: match?.[0] || "", from: head - (match?.[0]?.length || 0) };
    },
    getCompletionPosition: () => {
      const { head } = view.state.selection.main;
      const rect = view.coordsAtPos(head);
      return rect ? { left: rect.left, top: rect.bottom, height: rect.height } : null;
    },
    setValue: (text) => view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: text } }),
    insertCompletion: (text, from, cursorOffset = text.length) => {
      const head = view.state.selection.main.head;
      view.dispatch({ changes: { from, to: head, insert: text }, selection: { anchor: from + cursorOffset } });
      view.focus();
    },
    focus: () => view.focus(),
    setReadOnly: (v) => view.dispatch({ effects: readOnlyC.reconfigure(EditorState.readOnly.of(v)) }),
    insert: (text) => { view.dispatch(view.state.replaceSelection(text)); view.focus(); },
    indent: () => run(indentMore),
    dedent: () => run(indentLess),
    left: () => run(cursorCharLeft),
    right: () => run(cursorCharRight),
    up: () => run(cursorLineUp),
    down: () => run(cursorLineDown),
    destroy: () => view.destroy(),
  };
}
