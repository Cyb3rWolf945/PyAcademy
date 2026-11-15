// Utilitários do módulo de missão: texto bilingue, estrelas e um renderizador Markdown mínimo e seguro (só nós DOM).
import { el } from "../../components/dom.js";
import { getLocale } from "../../services/i18n.js";

// Escolhe o texto {pt, en} no idioma atual; aceita também texto simples
export function pick(v) {
  if (v == null) return "";
  if (typeof v === "string") return v;
  return (getLocale() === "en" ? v.en : v.pt) ?? v.pt ?? v.en ?? "";
}

// Pontos com no máximo 1 casa decimal, no formato do idioma (PT 237,5 · EN 237.5)
export const fmtPoints = (n) => new Intl.NumberFormat(getLocale() === "en" ? "en-GB" : "pt-PT", { maximumFractionDigits: 1 }).format(Number(n) || 0);

export const stars = (n) => "★".repeat(Math.max(0, Math.min(5, n | 0)));

// Inline: **negrito**, `código`, *itálico*. Nunca HTML: cada pedaço vira um nó DOM.
function inline(text) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/g;
  let last = 0;
  for (const m of text.matchAll(re)) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) out.push(el("strong", {}, tok.slice(2, -2)));
    else if (tok.startsWith("`")) out.push(el("code", { class: "bg-surface-2 px-1 font-mono" }, tok.slice(1, -1)));
    else out.push(el("em", {}, tok.slice(1, -1)));
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

// Markdown → DocumentFragment: parágrafos, títulos (#), listas (-, *, 1.), blocos de código (```), **negrito**, `código`
export function renderMarkdown(md) {
  const frag = document.createDocumentFragment();
  const lines = String(md ?? "").replace(/\r\n?/g, "\n").split("\n");
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    if (line.trimStart().startsWith("```")) {
      const code = [];
      i++;
      while (i < lines.length && !lines[i].trimStart().startsWith("```")) code.push(lines[i++]);
      i++;
      frag.append(el("pre", { class: "overflow-x-auto bg-surface-2 p-3 text-sm font-mono whitespace-pre" }, code.join("\n")));
      continue;
    }
    const h = /^(#{1,4})\s+(.*)$/.exec(line);
    if (h) { frag.append(el("h4", { class: "mt-2 font-bold text-accent" }, inline(h[2]))); i++; continue; }
    const li = /^\s*([-*]|\d+[.)])\s+/;
    if (li.test(line)) {
      const ordered = /^\s*\d/.test(line);
      const items = [];
      while (i < lines.length && li.test(lines[i])) items.push(el("li", {}, inline(lines[i++].replace(li, ""))));
      frag.append(el(ordered ? "ol" : "ul", { class: `grid gap-1 pl-6 ${ordered ? "list-decimal" : "list-disc"}` }, items));
      continue;
    }
    const para = [];
    while (i < lines.length && lines[i].trim() && !lines[i].trimStart().startsWith("```") && !/^#{1,4}\s/.test(lines[i]) && !li.test(lines[i])) para.push(lines[i++]);
    const kids = [];
    para.forEach((p, k) => { if (k) kids.push(el("br")); kids.push(...inline(p)); });
    frag.append(el("p", {}, kids));
  }
  return frag;
}
