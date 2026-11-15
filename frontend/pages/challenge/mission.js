// Vista de missão reutilizável (torneio e treino): enunciado, editor/perguntas, pistas com confirmação,
// submissão com fila offline e resultado. Telemóvel: separadores Enunciado | Código | Resultado; ecrã largo: lado a lado.
import { el } from "../../components/dom.js";
import { t } from "../../services/i18n.js";
import { api, errorText } from "../../services/api.js";
import { draftKey, loadDraft, saveDraft, flushDraft, submitWithQueue, onQueueEvent, queuedSubmissions } from "../../services/storage.js";
import { mountCodeEditor, mountQuestions } from "../../components/editor.js";
import { isTouch } from "../../components/symbol-bar.js";
import { pick, stars, renderMarkdown } from "./lib.js";
import { renderResult } from "./result.js";

const CODE_TIPOS = ["programa", "funcao", "bug"];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ctx: {tournamentId?, roundIdx?, canSubmit?() -> bool, hintUrl?(slug, n) -> url, onResult?(view), onClose?()}
export function mountMission(host, { mission, ctx = {} }) {
  const slug = mission.slug || mission.id;
  const isCode = CODE_TIPOS.includes(mission.tipo);
  const key = draftKey(ctx.tournamentId, ctx.roundIdx, slug);
  const hintUrl = ctx.hintUrl || ((s, n) => (ctx.tournamentId ? `/api/tournaments/${ctx.tournamentId}/hints/${s}/${n}` : `/api/problems/${s}/hints/${n}`));
  let tab = "statement";
  let editor = null, questions = null;
  let destroyed = false, busy = false, waitingClient = null, pollToken = 0;
  const hints = {}; // n -> texto (pistas já abertas)
  let hintsOpened = mission.hints_opened || 0;

  // ---------- Cabeçalho e separadores ----------
  const closeBtn = el("button", { type: "button", class: "btn-pixel btn-pixel--ghost", "aria-label": t("tournament.back"), onclick: () => ctx.onClose?.() }, "←");
  const header = el("header", { class: "flex items-center gap-2 bg-surface p-2 pt-[max(0.5rem,env(safe-area-inset-top))]" },
    closeBtn,
    el("div", { class: "min-w-0 flex-1" },
      el("h2", { class: "truncate text-base" }, pick(mission.titulo)),
      el("p", { class: "flex items-center gap-2 text-xs text-muted" }, el("span", { class: "stars text-gold" }, stars(mission.dificuldade)),
        el("span", { class: "badge-pixel" }, t(`tournament.tipo_${mission.tipo}`)))));
  const tabBtns = {};
  const tabs = el("div", { class: "tabs-pixel flex flex-nowrap lg:hidden", role: "tablist" },
    ["statement", "code", "result"].map((id) => {
      const b = el("button", { type: "button", role: "tab", class: "min-h-[44px] min-w-0 flex-1 px-1 text-xs", onclick: () => setTab(id) }, t(`tournament.tab_${id}`));
      tabBtns[id] = b;
      return b;
    }));

  // ---------- Enunciado ----------
  const statement = el("div", { class: "grid gap-3 p-3 text-sm leading-relaxed" });
  const hintsBox = el("section", { class: "grid gap-2" });
  const left = el("div", { class: "min-h-0 min-w-0 flex-col overflow-y-auto" }, statement);

  function buildStatement() {
    statement.replaceChildren(renderMarkdown(pick(mission.enunciado)));
    if (mission.assinatura) statement.append(el("p", {}, `${t("tournament.signature")}: `, el("code", { class: "bg-surface-2 px-1" }, mission.assinatura)));
    if (mission.restricoes) statement.append(el("p", { class: "text-muted" }, `${t("tournament.constraints")}: ${pick(mission.restricoes)}`));
    const req = mission.requisitos;
    if (req && !pick(mission.enunciado).includes("🧱")) { // se o enunciado já destaca o requisito (🧱), não o repete
      const items = [];
      if (req.usa) items.push(t("requirement.usa", { value: [].concat(req.usa).join(", ") }));
      if (req.proibe) items.push(t("requirement.proibe", { value: [].concat(req.proibe).join(", ") }));
      if (req.define_funcao) items.push(t("requirement.define_funcao", { nome: req.define_funcao.nome, parametros: req.define_funcao.parametros ?? "" }));
      if (req.recursiva) items.push(t("requirement.recursiva"));
      if (items.length) statement.append(el("div", { class: "grid gap-1 border-l-4 border-accent bg-surface-2 p-2" }, items.map((x) => el("p", {}, x))));
    }
    (mission.exemplos || []).forEach((ex, i) => {
      const parts = [el("p", { class: "font-bold" }, t("tournament.example_n", { n: i + 1 }))];
      const block = (label, text) => el("div", { class: "grid gap-1" }, el("span", { class: "text-xs text-muted" }, label),
        el("pre", { class: "overflow-x-auto bg-surface-2 p-2 font-mono whitespace-pre" }, text));
      if (ex.stdin != null) parts.push(block(t("tournament.input"), ex.stdin));
      if (ex.args != null) parts.push(block(t("tournament.args"), JSON.stringify(ex.args)));
      if (ex.stdout != null) parts.push(block(t("tournament.expected"), pick(ex.stdout)));
      if (ex.devolve != null) parts.push(block(t("tournament.returns"), JSON.stringify(ex.devolve)));
      statement.append(el("div", { class: "grid gap-2 bg-surface p-3" }, parts));
    });
    statement.append(hintsBox);
    paintHints();
  }

  // ---------- Pistas ----------
  let confirming = false;
  async function fetchHint(n) {
    const res = await api("GET", hintUrl(slug, n));
    hints[n] = pick(res.text ?? res.hint);
  }
  function paintHints() {
    const total = mission.pistas_count || 0;
    if (!total) { hintsBox.replaceChildren(); return; }
    const kids = [el("h3", { class: "text-sm" }, t("tournament.hints"))];
    for (let n = 1; n <= total; n++) {
      if (hints[n] != null) kids.push(el("p", { class: "bg-surface-2 p-3" }, `💡 ${n}. ${hints[n]}`));
    }
    const next = Object.keys(hints).length + 1;
    if (next <= total) {
      if (confirming) {
        kids.push(el("div", { class: "grid gap-2 border-l-4 border-warning bg-surface-2 p-3" },
          el("p", {}, t("tournament.hint_warning")),
          el("div", { class: "flex gap-2" },
            el("button", { type: "button", class: "btn-pixel btn-pixel--accent flex-1", onclick: () => openHint(next) }, t("tournament.hint_confirm")),
            el("button", { type: "button", class: "btn-pixel btn-pixel--ghost flex-1", onclick: () => { confirming = false; paintHints(); } }, t("tournament.cancel")))));
      } else {
        kids.push(el("button", { type: "button", class: "btn-pixel btn-pixel--ghost", onclick: () => { confirming = true; paintHints(); } }, t("tournament.hint_ask", { n: next, total })));
      }
    }
    hintsBox.replaceChildren(...kids);
  }
  async function openHint(n) {
    try { await fetchHint(n); hintsOpened = Math.max(hintsOpened, n); } catch (err) { setStatus(errorText(err), true); }
    confirming = false;
    if (!destroyed) paintHints();
  }

  // ---------- Código / perguntas + submissão ----------
  const editorHost = el("div", { class: "min-h-0 min-w-0 flex-1 overflow-auto" });
  const statusLine = el("p", { class: "min-h-5 text-sm", role: "status", "aria-live": "polite" });
  const queueNote = el("p", { class: "text-sm text-warning", hidden: true });
  const submitBtn = el("button", { type: "button", class: "btn-pixel btn-pixel--accent btn-pixel--lg w-full", onclick: () => submit() }, t("tournament.submit"));
  const symbolHost = el("div", { class: "min-w-0" });
  const codePanel = el("div", { class: "min-h-0 flex-1 flex-col" },
    editorHost, symbolHost, el("div", { class: "grid gap-1 bg-surface p-2" }, statusLine, queueNote, submitBtn));
  const resultBox = el("div", { class: "p-3" }, el("p", { class: "text-sm text-muted" }, t("tournament.no_result_yet")));
  const resultPanel = el("div", { class: "min-h-0 overflow-y-auto lg:max-h-[45%] lg:border-t-2 lg:border-surface-2" }, resultBox);
  const right = el("div", { class: "min-h-0 min-w-0 flex-col" }, codePanel, resultPanel);
  const body = el("div", { class: "grid min-h-0 min-w-0 flex-1 grid-cols-1 lg:grid-cols-2" }, left, right);
  const root = el("div", { class: "fixed inset-0 z-30 flex min-w-0 flex-col overflow-hidden bg-bg" }, header, tabs, body);
  host.replaceChildren(root);

  function setTab(next) {
    tab = next;
    for (const [id, b] of Object.entries(tabBtns)) { b.setAttribute("aria-selected", String(id === tab)); }
    left.className = `min-h-0 min-w-0 overflow-y-auto ${tab === "statement" ? "flex" : "hidden lg:flex"} flex-col`;
    right.className = `min-h-0 min-w-0 ${tab !== "statement" ? "flex" : "hidden lg:flex"} flex-col`;
    codePanel.className = `min-h-0 min-w-0 flex-1 ${tab === "result" ? "hidden lg:flex" : "flex"} flex-col`;
    resultPanel.className = `min-h-0 min-w-0 overflow-y-auto ${tab === "result" ? "block flex-1" : "hidden lg:block"} lg:max-h-[45%] lg:border-t-2 lg:border-surface-2`;
  }

  function setStatus(text, bad = false) {
    statusLine.textContent = text;
    statusLine.className = `min-h-5 text-sm ${bad ? "text-danger" : "text-muted"}`;
  }

  function refreshSubmit() {
    const allowed = ctx.canSubmit ? ctx.canSubmit() : true;
    submitBtn.disabled = busy || !allowed;
    submitBtn.textContent = busy ? t("tournament.submitting") : t("tournament.submit");
    if (!allowed && !busy) setStatus(t("tournament.submit_paused"), true);
    else if (statusLine.textContent === t("tournament.submit_paused")) setStatus("");
  }

  function paintQueue() {
    const n = queuedSubmissions().length;
    queueNote.hidden = n === 0;
    queueNote.textContent = n ? t("tournament.queue_pending", { n }) : "";
  }

  function currentPayload() {
    const p = { problem_slug: slug, hints_used: Math.max(hintsOpened, Object.keys(hints).length) };
    if (ctx.tournamentId != null) { p.tournament_id = ctx.tournamentId; p.round_idx = ctx.roundIdx; }
    if (isCode) p.code = editor.getValue(); else p.answers = questions.getAnswers();
    return p;
  }

  async function submit() {
    if (busy || destroyed) return;
    if (isCode && !editor.getValue().trim()) { setStatus(t("tournament.empty_code"), true); return; }
    busy = true; refreshSubmit(); setStatus(t("tournament.sending"));
    flushDraft(key);
    let res;
    try { res = await submitWithQueue(currentPayload()); }
    catch (err) { busy = false; setStatus(errorText(err), true); refreshSubmit(); if (err.key === "tournament.team_required") ctx.onTeamRequired?.(); return; }
    paintQueue();
    if (res.queued) { waitingClient = res.client_id; setStatus(t("tournament.queued_offline")); return; }
    await pollResult(res.id);
  }

  async function pollResult(id) {
    const token = ++pollToken;
    setTab("result");
    const delays = [500, 700, 1000, 1500, 2000];
    const started = Date.now();
    for (let i = 0; !destroyed && token === pollToken; i++) {
      let view = null;
      try { view = await api("GET", `/api/submissions/${id}`); } catch (_) { /* rede instável: continua */ }
      if (destroyed || token !== pollToken) return;
      if (view) {
        resultBox.replaceChildren(renderResult(view));
        if (view.status !== "queued" && view.status !== "running") {
          busy = false; waitingClient = null; setStatus("");
          refreshSubmit();
          ctx.onResult?.(view);
          return;
        }
      }
      if (Date.now() - started > 90000) { busy = false; setStatus(t("tournament.poll_timeout"), true); refreshSubmit(); return; }
      await sleep(delays[Math.min(i, delays.length - 1)]);
    }
  }

  // A fila offline reenvia sozinha: quando a nossa submissão sai, passa a fazer polling
  const offQueue = onQueueEvent((ev) => {
    if (destroyed) return;
    paintQueue();
    if (ev.client_id && ev.client_id === waitingClient) {
      if (ev.type === "sent") { setStatus(t("tournament.sending")); pollResult(ev.id); }
      else if (ev.type === "failed") { busy = false; waitingClient = null; setStatus(errorText(ev.error), true); refreshSubmit(); }
    }
  });

  // ---------- Arranque ----------
  buildStatement();
  setTab("statement");
  paintQueue();
  (async () => {
    // pistas já abertas (idempotente: voltar a pedir não custa mais)
    for (let n = 1; n <= hintsOpened; n++) { try { await fetchHint(n); } catch (_) { break; } if (destroyed) return; }
    paintHints();
  })();
  if (isCode) {
    const draft = loadDraft(key);
    // Sem código inicial, as funções começam com a assinatura pronta (menos escrita no telemóvel)
    const starter = pick(mission.codigo_inicial) || (mission.assinatura ? `def ${mission.assinatura}:\n    ` : "");
    const start = draft != null ? draft : starter;
    mountCodeEditor(editorHost, {
      value: start, ariaLabel: t("tournament.tab_code"), onChange: (v) => saveDraft(key, v), symbolHost,
    }).then((ed) => { if (destroyed) ed.destroy(); else editor = ed; refreshSubmit(); });
    // nada bloqueia a escrita: o editor monta de forma assíncrona e o botão só espera por ele
    submitBtn.disabled = true;
  } else {
    let saved = null;
    try { saved = JSON.parse(loadDraft(key) || "null"); } catch (_) { /* rascunho inválido */ }
    questions = mountQuestions(editorHost, mission.perguntas || [], { answers: saved, onChange: (a) => saveDraft(key, JSON.stringify(a)) });
    refreshSubmit();
  }

  const vv = window.visualViewport;
  const fit = () => { if (isTouch() && vv) { root.style.top = `${vv.offsetTop}px`; root.style.height = `${vv.height}px`; root.style.bottom = "auto"; } };
  vv?.addEventListener("resize", fit);
  vv?.addEventListener("scroll", fit);
  fit();
  const onLocale = () => { buildStatement(); Object.entries(tabBtns).forEach(([id, b]) => { b.textContent = t(`tournament.tab_${id}`); }); refreshSubmit(); };
  document.addEventListener("localechange", onLocale);

  return {
    slug,
    // Chamado quando o snapshot muda (por exemplo, pausa/retoma ou missão resolvida)
    update(next) { if (next) { mission.solved_by_me = next.solved_by_me; } refreshSubmit(); },
    refresh: refreshSubmit,
    destroy() {
      destroyed = true; pollToken++;
      flushDraft(key); offQueue();
      vv?.removeEventListener("resize", fit); vv?.removeEventListener("scroll", fit);
      document.removeEventListener("localechange", onLocale);
      editor?.destroy();
      host.replaceChildren();
    },
  };
}
