// Resultado de uma submissão: estado, "passou X/Y", diferença esperado vs obtido nos exemplos visíveis,
// requisitos em falta (🧱), dica amigável para o erro clássico e resultado por pergunta (quiz). Só nós DOM.
import { el } from "../../components/dom.js";
import { t } from "../../services/i18n.js";

const ICON = { accepted: "✅", queued: "⏳", running: "⏳", requirements_unmet: "🧱" };
const clip = (s, n = 1200) => { s = String(s ?? ""); return s.length > n ? `${s.slice(0, n)}…` : s; };

// Mostra as linhas; as que diferem das da outra coluna ficam destacadas
function diffBlock(label, text, otherText, bad) {
  const lines = String(text ?? "").split("\n");
  const other = String(otherText ?? "").split("\n");
  return el("div", { class: "min-w-0 grid gap-1" },
    el("span", { class: "text-xs text-muted" }, label),
    el("pre", { class: "overflow-x-auto bg-surface-2 p-2 text-sm font-mono whitespace-pre" },
      lines.map((l, i) => el("span", { class: `block ${bad && l !== other[i] ? "bg-danger/25" : ""}` }, l || " "))));
}

function caseView(c) {
  return el("div", { class: "grid gap-2 bg-surface p-3" },
    el("p", { class: "text-sm font-bold" }, `${c.passed ? "✅" : "❌"} ${t("tournament.example_n", { n: (c.index ?? 0) + 1 })}`),
    c.input ? el("div", { class: "grid gap-1" }, el("span", { class: "text-xs text-muted" }, t("tournament.input")),
      el("pre", { class: "overflow-x-auto bg-surface-2 p-2 text-sm font-mono" }, clip(c.input))) : null,
    el("div", { class: "grid gap-2 sm:grid-cols-2" },
      diffBlock(t("tournament.expected"), clip(c.expected), clip(c.actual), false),
      diffBlock(t("tournament.actual"), clip(c.actual), clip(c.expected), !c.passed)),
    c.error ? el("pre", { class: "overflow-x-auto bg-danger/20 p-2 text-sm font-mono" }, clip(c.error, 600)) : null);
}

// view = resposta de GET /api/submissions/{id}
export function renderResult(view) {
  const r = view.result || {};
  const status = view.status;
  const done = status !== "queued" && status !== "running";
  const box = el("div", { class: "grid gap-3" });
  const ok = status === "accepted";

  box.append(el("p", { class: `font-pixel text-lg ${ok ? "text-success anim-pop" : done ? "text-danger" : "text-muted"}`, role: "status" },
    `${ICON[status] || "❌"} ${t(`status.${status}`)}`));
  if (status === "queued" && view.queue_position) box.append(el("p", { class: "text-sm text-muted" }, t("tournament.queue_position", { n: view.queue_position })));
  if (!done) return box;

  const total = view.total ?? r.total, passed = view.passed ?? r.passed;
  if (total != null && total > 0) box.append(el("p", { class: "text-sm" }, t("tournament.passed_x_of_y", { x: passed ?? 0, y: total })));
  if (status === "requirements_unmet") box.append(el("p", { class: "text-sm text-success" }, t("requirement.result_ok")));

  for (const u of r.requirement_keys || []) {
    box.append(el("p", { class: "bg-surface-2 p-2 text-sm" }, t(u.key, { ...u, value: u.value ?? u.nome ?? "" })));
  }
  if (r.hint_key) box.append(el("p", { class: "bg-surface-2 p-3 text-sm" }, `💡 ${t(r.hint_key)}`));
  if (r.error && !ok) box.append(el("pre", { class: "overflow-x-auto bg-danger/20 p-2 text-sm font-mono whitespace-pre-wrap" }, clip(r.error, 600)));

  if (Array.isArray(r.questions)) {
    box.append(el("ul", { class: "grid gap-1 text-sm" }, r.questions.map((q, i) => el("li", {}, `${q ? "✅" : "❌"} ${t("tournament.question_n", { n: i + 1 })}`))));
  }
  const cases = r.cases || [];
  if (cases.length && !ok) {
    box.append(el("p", { class: "flex flex-wrap gap-1 text-sm", "aria-label": t("tournament.cases") },
      cases.map((c) => el("span", { class: "badge-pixel" }, `${c.passed ? "✅" : "❌"}${(c.index ?? 0) + 1}`))));
    const visibleFailed = cases.filter((c) => c.visible && !c.passed).slice(0, 2);
    box.append(...visibleFailed.map(caseView));
  }
  return box;
}
