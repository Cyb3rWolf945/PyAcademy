// Secção "Torneios" do painel do professor: criar, editar rondas (seletor de problemas), painel de controlo grande,
// presença dos alunos e ligação ao projetor. Os botões perigosos pedem um segundo toque para confirmar.
import { api, errorText } from "../../services/api.js";
import { t, getLocale } from "../../services/i18n.js";
import { el } from "../../components/dom.js";
import { toast } from "../../components/toast.js";
import { pick, stars } from "../challenge/lib.js";
import { fmtClock } from "../../components/timer.js";
import { memberRow } from "../../components/bracket.js";

const POLL_MS = 3000;
const TIPOS = ["programa", "funcao", "bug", "quiz", "decomposicao", "tracar"];

// Botão que só executa no segundo toque: à prova de toques acidentais. Fica "armado" 4 s, com uma barra de
// progresso visível (a barra encolhe até ao fim do prazo).
const ARM_MS = 4000;
function confirmButton(label, confirmLabel, action, cls = "btn-pixel btn-pixel--danger btn-pixel--lg") {
  let armed = null, started = 0, raf = 0;
  const bar = el("span", { class: "block h-1 bg-accent-text", "aria-hidden": "true", hidden: true });
  const text = el("span", {}, label);
  const b = el("button", { type: "button", class: `${cls} flex-col` }, text, bar);
  const disarm = () => { clearTimeout(armed); cancelAnimationFrame(raf); armed = null; text.textContent = label; bar.hidden = true; };
  const tick = () => {
    const left = Math.max(0, 1 - (Date.now() - started) / ARM_MS);
    bar.style.width = `${Math.round(left * 100)}%`;
    if (armed) raf = requestAnimationFrame(tick);
  };
  b.addEventListener("click", async () => {
    if (!armed) {
      text.textContent = `${confirmLabel} (${ARM_MS / 1000} s)`;
      bar.hidden = false; started = Date.now(); tick();
      armed = setTimeout(disarm, ARM_MS);
      return;
    }
    disarm();
    b.disabled = true;
    try { await action(); } finally { b.disabled = false; }
  });
  return b;
}

export function initTournaments(root) {
  let classes = [];
  let selected = null; // id do torneio aberto
  let data = null; // última resposta de /admin
  let pollTimer = null;
  let problems = null; // cache de /api/problems
  let editing = null; // idx da ronda em edição
  let draft = null; // {title:{pt,en}, points, multiplier, duration_min, slugs}
  let picking = false;
  const filters = { q: "", bloco: "", tipo: "", dificuldade: "" };

  const classSelect = el("select", { class: "input-pixel", name: "class_id", required: true });
  const nameInput = el("input", { class: "input-pixel", name: "name", maxlength: 80, required: true });
  const modeSelect = el("select", { class: "input-pixel", name: "mode" });
  const formatSelect = el("select", { class: "input-pixel", name: "format" });
  const groupSize = el("input", { class: "input-pixel", name: "group_size", type: "number", min: 3, max: 6, value: 4 });
  const advance = el("input", { class: "input-pixel", name: "advance_per_group", type: "number", min: 1, max: 2, value: 1 });
  const elimFields = el("div", { class: "grid grid-cols-2 gap-2" });
  const aulaFields = el("div", { class: "grid gap-1" });
  const createForm = el("form", { class: "grid gap-3" });
  const list = el("ul", { class: "grid gap-2" });
  const detail = el("div", { class: "grid min-w-0 gap-3" });
  const heading = el("h2", { class: "text-lg" });
  const lab = (text, input) => el("label", { class: "grid gap-1 text-sm" }, el("span", {}, text), input);
  const syncFormat = () => { const e = formatSelect.value === "eliminatoria"; elimFields.hidden = !e; aulaFields.hidden = e; };
  formatSelect.addEventListener("change", syncFormat);
  // Textos do cabeçalho e do formulário: refeitos quando o idioma muda (os campos mantêm o valor)
  function paintShell() {
    heading.textContent = t("tournament.admin_title");
    const mode = modeSelect.value, fmt = formatSelect.value || "eliminatoria";
    modeSelect.replaceChildren(el("option", { value: "agencias" }, t("tournament.mode_agencias")), el("option", { value: "individual" }, t("tournament.mode_individual")));
    if (mode) modeSelect.value = mode;
    formatSelect.replaceChildren(el("option", { value: "eliminatoria" }, t("tournament.format_eliminatoria")), el("option", { value: "aula" }, t("tournament.format_aula")));
    formatSelect.value = fmt;
    elimFields.replaceChildren(lab(t("tournament.group_size"), groupSize), lab(t("tournament.advance_per_group"), advance));
    aulaFields.replaceChildren(lab(t("tournament.admin_mode"), modeSelect));
    createForm.replaceChildren(
      el("h3", {}, t("tournament.admin_new")),
      lab(t("tournament.admin_class"), classSelect), lab(t("tournament.admin_name"), nameInput), lab(t("tournament.admin_format"), formatSelect),
      elimFields, aulaFields,
      el("button", { class: "btn-pixel btn-pixel--accent", type: "submit" }, t("tournament.admin_create")));
    syncFormat();
  }
  paintShell();
  root.replaceChildren(heading, createForm, list, detail);

  async function loadList() {
    const all = [];
    for (const c of classes) {
      try { const r = await api("GET", `/api/tournaments?class_id=${c.id}`); for (const x of r.tournaments || []) all.push({ ...x, class_name: c.name }); }
      catch (_) { /* uma turma sem torneios ou erro: ignora */ }
    }
    list.replaceChildren(...all.map((x) => el("li", {},
      el("button", { type: "button", class: `btn-pixel btn-pixel--ghost w-full justify-between ${x.id === selected ? "text-accent" : ""}`, onclick: () => select(x.id) },
        el("span", { class: "truncate" }, `${x.name} · ${x.class_name}`), el("span", { class: "badge-pixel" }, t(`tournament.state_${x.state}`))))));
    if (!all.length) list.replaceChildren(el("li", { class: "text-sm text-muted" }, t("tournament.admin_none")));
  }

  function setClasses(next) {
    classes = next;
    classSelect.replaceChildren(...classes.map((c) => el("option", { value: c.id }, c.name)));
    loadList();
  }

  function setActiveClass(classId) {
    if (classes.some((c) => c.id === classId)) classSelect.value = String(classId);
  }

  createForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      const body = { class_id: Number(classSelect.value), name: nameInput.value.trim(), format: formatSelect.value };
      if (body.format === "eliminatoria") Object.assign(body, { group_size: Number(groupSize.value), advance_per_group: Number(advance.value) });
      else body.mode = modeSelect.value;
      const res = await api("POST", "/api/tournaments", body);
      nameInput.value = "";
      await loadList();
      select(res.tournament?.id ?? res.id);
    } catch (err) { toast(errorText(err), "error"); }
  });

  async function select(id) {
    selected = id; editing = null; picking = false; lastSig = "";
    clearInterval(pollTimer);
    await reload(true);
    pollTimer = setInterval(() => { if (document.visibilityState === "visible" && !editing) reload(); }, POLL_MS);
    detail.scrollIntoView?.({ behavior: "smooth", block: "start" });
  }

  // Só repinta se os dados mudaram (assim um botão "toca outra vez para confirmar" não é desarmado pelo poll)
  let lastSig = "";
  async function reload(force = false) {
    try {
      const next = await api("GET", `/api/tournaments/${selected}/admin`);
      const sig = JSON.stringify(next, (k, v) => (k === "server_now" || k === "last_seen" || k === "last_seq" ? undefined : v));
      if (sig === lastSig && !force) return;
      lastSig = sig; data = next; render();
    } catch (err) { if (force) toast(errorText(err), "error"); }
  }

  async function call(method, path, body) {
    try { await api(method, `/api/tournaments/${selected}${path}`, body); } catch (err) { toast(errorText(err), "error"); }
    await reload(true);
    loadList();
  }

  // ---------- Painel de controlo ----------
  const isElim = () => data.format === "eliminatoria";

  // Painel da eliminatória: um botão grande por ação; fechar/terminar pedem segundo toque
  function elimControls() {
    const tour = data.tournament;
    const cur = tour.current_round, st = tour.state;
    const big = "btn-pixel btn-pixel--lg min-h-[64px]";
    const btns = [];
    if (st === "lobby" || st === "between_rounds") {
      btns.push(el("button", { type: "button", class: `${big} btn-pixel--accent sm:col-span-2`, onclick: () => call("POST", "/rounds/next/start") }, `▶ ${t("tournament.ctl_next_round")}`));
    }
    if (st === "round_active") btns.push(el("button", { type: "button", class: big, onclick: () => call("POST", `/rounds/${cur}/pause`) }, `⏸ ${t("tournament.ctl_pause")}`));
    if (st === "round_paused") btns.push(el("button", { type: "button", class: `${big} btn-pixel--accent`, onclick: () => call("POST", `/rounds/${cur}/resume`) }, `▶ ${t("tournament.ctl_resume")}`));
    if (st === "round_active" || st === "round_paused") {
      btns.push(el("button", { type: "button", class: big, onclick: () => call("POST", `/rounds/${cur}/extend`, { seconds: 120 }) }, `⏱ ${t("tournament.ctl_extend")}`));
      btns.push(confirmButton(`⏹ ${t("tournament.ctl_close")}`, t("tournament.ctl_tap_confirm"), () => call("POST", `/rounds/${cur}/close`), `${big} btn-pixel--danger`));
    }
    if (st !== "finished") btns.push(confirmButton(`🏁 ${t("tournament.ctl_finish")}`, t("tournament.ctl_tap_confirm"), () => call("POST", "/finish"), `${big} btn-pixel--danger`));
    const curRound = (data.rounds || []).find((r) => r.idx === cur);
    return el("section", { class: "panel-pixel grid gap-3" },
      el("div", { class: "flex flex-wrap items-center gap-2" },
        el("span", { class: "badge-pixel" }, t(`tournament.state_${st}`)),
        el("span", { class: "text-sm" }, t("tournament.alive_of", { alive: data.alive_count ?? "?", total: data.players_count ?? "?" })),
        curRound ? el("span", { class: "text-sm" }, `${roundTitleOf(curRound)}${curRound.state === "paused" ? ` · ${fmtClock(curRound.remaining_s || 0)}` : ""}`) : null),
      el("div", { class: "grid gap-2 sm:grid-cols-2" }, btns));
  }
  const roundTitleOf = (r) => pick(r.title) || (r.is_final ? t("tournament.final_round") : t("tournament.round_n", { n: r.idx }));

  // Grelha dos grupos da ronda atual (ou da última): progresso ao vivo + "definir vencedor" com confirmação
  function groupsView() {
    const rounds = (data.rounds || []).filter((r) => r.groups?.length);
    const r = rounds.find((x) => x.idx === data.tournament.current_round) || rounds[rounds.length - 1];
    if (!r) return el("section", { class: "panel-pixel" }, el("p", { class: "text-sm text-muted" }, t("tournament.bracket_empty")));
    const grid = el("div", { class: "grid min-w-0 gap-2 sm:grid-cols-2 lg:grid-cols-3" }, r.groups.map((g, i) => el("div", { class: `grid min-w-0 gap-1 bg-surface-2 p-2 ${g.decided ? "border-l-4 border-success" : ""}` },
      el("p", { class: "text-xs text-muted" }, `${t("tournament.group_n", { n: i + 1 })}${g.decided_by ? ` · ${t(`tournament.decided_${g.decided_by}`)}` : ""}`),
      ...(g.members || []).map((m) => el("div", { class: "grid gap-1" },
        memberRow(m, { meId: null, attempts: true }),
        m.status === "winner" ? null : confirmButton(`🏆 ${t("tournament.set_winner")}`, t("tournament.ctl_tap_confirm"), () => call("POST", `/groups/${g.id}/winner`, { user_id: m.user_id }), "btn-pixel btn-pixel--ghost text-xs"))))));
    return el("section", { class: "panel-pixel grid min-w-0 gap-2" }, el("h3", {}, `${t("tournament.groups_live")} · ${roundTitleOf(r)}`), grid);
  }

  // Pré-visualização do bracket com os alunos que já entraram (só no lobby)
  let previewBox = null, previewTimer = 0;
  const pv = { group_size: 4, advance: 1 };
  function previewView() {
    const box = el("section", { class: "panel-pixel grid min-w-0 gap-2" });
    const gs = el("input", { class: "input-pixel", type: "number", min: 3, max: 6, value: data.config?.group_size ?? data.tournament.config?.group_size ?? pv.group_size, "aria-label": t("tournament.group_size") });
    const ad = el("input", { class: "input-pixel", type: "number", min: 1, max: 2, value: data.config?.advance_per_group ?? data.tournament.config?.advance_per_group ?? pv.advance, "aria-label": t("tournament.advance_per_group") });
    const out = el("ul", { class: "grid gap-1 text-sm" });
    async function load() {
      try {
        const r = await api("GET", `/api/tournaments/${selected}/bracket-preview?group_size=${gs.value}&advance_per_group=${ad.value}`);
        out.replaceChildren(el("li", { class: "font-bold" }, t("tournament.preview_players", { n: r.players })),
          ...(r.rounds || []).map((x) => el("li", {}, x.is_final ? t("tournament.preview_final", { n: x.sizes?.[0] ?? "" }) : t("tournament.preview_round", { n: x.idx, groups: x.groups, sizes: (x.sizes || []).join(", "), adv: x.advancing, per: ad.value }))));
      } catch (err) { out.replaceChildren(el("li", { class: "text-danger" }, errorText(err))); }
    }
    const again = () => { clearTimeout(previewTimer); previewTimer = setTimeout(load, 300); };
    gs.addEventListener("input", again); ad.addEventListener("input", again);
    // Guardar: PATCH /config (só no lobby) e refresca a pré-visualização
    const save = el("button", { type: "button", class: "btn-pixel btn-pixel--accent", onclick: async () => {
      try { await api("PATCH", `/api/tournaments/${selected}/config`, { group_size: Number(gs.value), advance_per_group: Number(ad.value) }); toast(t("common.saved"), "success"); await load(); }
      catch (err) { toast(errorText(err), "error"); }
    } }, t("tournament.save_config"));
    box.append(el("h3", {}, t("tournament.preview_title")), el("div", { class: "grid grid-cols-2 gap-2" }, lab(t("tournament.group_size"), gs), lab(t("tournament.advance_per_group"), ad)), save, out);
    load();
    return box;
  }

  function controls() {
    if (isElim()) return elimControls();
    const tour = data.tournament, rounds = data.rounds || [];
    const cur = tour.current_round;
    const nextPending = rounds.find((r) => r.state === "pending");
    const nextLabel = nextPending ? (nextPending.is_boss ? t("tournament.ctl_start_boss") : t("tournament.ctl_start_round", { n: nextPending.idx })) : "";
    const big = "btn-pixel btn-pixel--lg min-h-[64px]";
    const st = tour.state;
    const start = () => call("POST", `/rounds/${nextPending.idx}/start`);
    const btns = [];
    if ((st === "lobby" || st === "between_rounds") && nextPending) {
      // Iniciar ronda: um toque. Só o Boss pede confirmação.
      btns.push(nextPending.is_boss
        ? confirmButton(`▶ ${nextLabel}`, t("tournament.ctl_tap_confirm"), start, `${big} btn-pixel--accent`)
        : el("button", { type: "button", class: `${big} btn-pixel--accent`, onclick: start }, `▶ ${nextLabel}`));
    }
    if (st === "round_active") btns.push(el("button", { type: "button", class: big, onclick: () => call("POST", `/rounds/${cur}/pause`) }, `⏸ ${t("tournament.ctl_pause")}`));
    if (st === "round_paused") btns.push(el("button", { type: "button", class: `${big} btn-pixel--accent`, onclick: () => call("POST", `/rounds/${cur}/resume`) }, `▶ ${t("tournament.ctl_resume")}`));
    if (st === "round_active" || st === "round_paused") {
      btns.push(el("button", { type: "button", class: big, onclick: () => call("POST", `/rounds/${cur}/extend`, { seconds: 120 }) }, `⏱ ${t("tournament.ctl_extend")}`));
      btns.push(confirmButton(`⏹ ${t("tournament.ctl_close")}`, t("tournament.ctl_tap_confirm"), () => call("POST", `/rounds/${cur}/close`), `${big} btn-pixel--danger`));
    }
    if (st !== "finished") btns.push(confirmButton(`🏁 ${t("tournament.ctl_finish")}`, t("tournament.ctl_tap_confirm"), () => call("POST", "/finish"), `${big} btn-pixel--danger`));
    const curRound = rounds.find((r) => r.idx === cur);
    return el("section", { class: "panel-pixel grid gap-3" },
      el("div", { class: "flex flex-wrap items-center gap-2" },
        el("span", { class: "badge-pixel" }, t(`tournament.state_${st}`)),
        curRound ? el("span", { class: "text-sm" }, `${pick(curRound.title)}${curRound.state === "paused" ? ` · ${fmtClock(curRound.remaining_s || 0)}` : ""}`) : null),
      el("div", { class: "grid gap-2 sm:grid-cols-2" }, btns));
  }

  // ---------- Editor de rondas ----------
  const numInput = (value, onInput, attrs = {}) => {
    const i = el("input", { class: "input-pixel", type: "number", value, ...attrs });
    i.addEventListener("input", () => onInput(Number(i.value)));
    return i;
  };
  const titleOf = (slug) => { const p = problems?.find((x) => x.id === slug); return p ? `${p.estado === "rascunho" ? `[${t("tournament.draft")}] ` : ""}${pick(p.titulo)}` : slug; };

  async function ensureProblems() {
    if (problems) return;
    try { problems = (await api("GET", "/api/problems")).problems || []; } catch (err) { toast(errorText(err), "error"); problems = []; }
  }

  function openEditor(r) {
    editing = r.idx; picking = false;
    draft = { title: { pt: pick({ pt: r.title?.pt }), en: pick({ en: r.title?.en }) }, points: r.points, multiplier: r.multiplier, duration_min: Math.round((r.duration_s || 600) / 60), slugs: [...(r.problem_slugs || [])] };
    ensureProblems().then(render);
    render();
  }

  async function saveEditor() {
    try {
      await api("PUT", `/api/tournaments/${selected}/rounds/${editing}`, isElim()
        ? { problem_slugs: draft.slugs, duration_s: Math.round(draft.duration_min * 60) }
        : { title: draft.title, problem_slugs: draft.slugs, points: draft.points, multiplier: draft.multiplier, duration_s: Math.round(draft.duration_min * 60) });
      editing = null; picking = false;
      toast(t("common.saved"), "success");
    } catch (err) { toast(errorText(err), "error"); }
    await reload(true);
  }

  function pickerView() {
    const all = problems || [];
    const blocos = [...new Set(all.map((p) => p.bloco))].sort();
    const sel = (key, opts, label) => {
      const s = el("select", { class: "input-pixel", "aria-label": label }, el("option", { value: "" }, label), opts.map((o) => el("option", { value: o, selected: String(filters[key]) === String(o) }, String(o))));
      s.addEventListener("change", () => { filters[key] = s.value; render(); });
      return s;
    };
    const q = el("input", { class: "input-pixel", type: "search", value: filters.q, placeholder: t("tournament.admin_search"), "aria-label": t("tournament.admin_search") });
    q.addEventListener("input", () => { filters.q = q.value; paintResults(); });
    const results = el("ul", { class: "grid max-h-80 gap-1 overflow-y-auto" });
    function paintResults() {
      const needle = filters.q.trim().toLowerCase();
      const rows = all.filter((p) => (!isElim() || ["programa", "funcao", "bug"].includes(p.tipo)) && (!filters.bloco || p.bloco === filters.bloco) && (!filters.tipo || p.tipo === filters.tipo)
        && (!filters.dificuldade || String(p.dificuldade) === filters.dificuldade)
        && (!needle || `${p.titulo.pt} ${p.titulo.en} ${p.id}`.toLowerCase().includes(needle))).slice(0, 80);
      results.replaceChildren(...rows.map((p) => el("li", {}, el("button", {
        type: "button", class: "btn-pixel btn-pixel--ghost w-full justify-between text-left", disabled: draft.slugs.includes(p.id),
        onclick: () => { if (isElim()) draft.slugs = [p.id]; else draft.slugs.push(p.id); render(); },
      }, el("span", { class: "min-w-0 truncate" }, p.estado === "rascunho" ? `[${t("tournament.draft")}] ` : "", pick(p.titulo)), el("span", { class: "shrink-0 text-xs" }, `${stars(p.dificuldade)} ${t(`tournament.tipo_${p.tipo}`)} · B${p.bloco}`)))));
      if (!rows.length) results.replaceChildren(el("li", { class: "text-sm text-muted" }, t("tournament.admin_no_problems")));
    }
    paintResults();
    return el("div", { class: "panel-pixel panel-pixel--inset grid gap-2" },
      el("div", { class: "grid gap-2 sm:grid-cols-4" }, q, sel("bloco", blocos, t("tournament.admin_filter_bloco")), sel("tipo", isElim() ? TIPOS.slice(0, 3) : TIPOS, t("tournament.admin_filter_tipo")), sel("dificuldade", [1, 2, 3, 4, 5], t("tournament.admin_filter_stars"))),
      results,
      el("button", { type: "button", class: "btn-pixel btn-pixel--ghost", onclick: () => { picking = false; render(); } }, t("tournament.admin_picker_done")));
  }

  function editorView(r) {
    const slugRows = draft.slugs.map((s, i) => el("li", { class: "flex items-center gap-1 bg-surface-2 p-1" },
      el("span", { class: "min-w-0 flex-1 truncate text-sm" }, `${i + 1}. ${titleOf(s)}`),
      el("button", { type: "button", class: "btn-pixel btn-pixel--ghost", "aria-label": t("tournament.admin_up"), disabled: i === 0, onclick: () => { [draft.slugs[i - 1], draft.slugs[i]] = [draft.slugs[i], draft.slugs[i - 1]]; render(); } }, "↑"),
      el("button", { type: "button", class: "btn-pixel btn-pixel--ghost", "aria-label": t("tournament.admin_remove"), onclick: () => { draft.slugs.splice(i, 1); render(); } }, "✕")));
    const tpt = el("input", { class: "input-pixel", value: draft.title.pt, maxlength: 60 });
    const ten = el("input", { class: "input-pixel", value: draft.title.en, maxlength: 60 });
    tpt.addEventListener("input", () => { draft.title.pt = tpt.value; });
    ten.addEventListener("input", () => { draft.title.en = ten.value; });
    return el("div", { class: "grid gap-3 bg-surface-2 p-3" },
      isElim() ? null : el("div", { class: "grid gap-2 sm:grid-cols-2" },
        el("label", { class: "grid gap-1 text-sm" }, el("span", {}, `${t("tournament.admin_round_title")} (PT)`), tpt),
        el("label", { class: "grid gap-1 text-sm" }, el("span", {}, `${t("tournament.admin_round_title")} (EN)`), ten)),
      el("div", { class: "grid grid-cols-3 gap-2" },
        isElim() ? null : el("label", { class: "grid gap-1 text-sm" }, el("span", {}, t("tournament.admin_points")), numInput(draft.points, (v) => { draft.points = v; }, { min: 0, max: 1000 })),
        isElim() ? null : el("label", { class: "grid gap-1 text-sm" }, el("span", {}, t("tournament.admin_multiplier")), numInput(draft.multiplier, (v) => { draft.multiplier = v; }, { min: 1, max: 10, step: 0.5 })),
        el("label", { class: "grid gap-1 text-sm" }, el("span", {}, t("tournament.admin_minutes")), numInput(draft.duration_min, (v) => { draft.duration_min = v; }, { min: 1, max: 180 }))),
      el("ul", { class: "grid gap-1" }, slugRows),
      picking ? pickerView() : el("button", { type: "button", class: "btn-pixel btn-pixel--ghost", onclick: () => { picking = true; render(); } }, `＋ ${t("tournament.admin_add_problem")}`),
      el("div", { class: "flex gap-2" },
        el("button", { type: "button", class: "btn-pixel btn-pixel--accent flex-1", onclick: saveEditor }, t("common.save")),
        el("button", { type: "button", class: "btn-pixel btn-pixel--ghost flex-1", onclick: () => { editing = null; picking = false; render(); } }, t("tournament.cancel"))));
  }

  function roundsView() {
    const rows = (data.rounds || []).map((r) => {
      const pending = r.state === "pending";
      return el("li", { class: "grid gap-2" },
        el("div", { class: "flex items-center gap-2" },
          el("span", { class: "min-w-0 flex-1 text-sm" }, isElim() ? `${r.idx}. ${roundTitleOf(r)} · ${Math.round((r.duration_s || 0) / 60)} min · ${(r.problems?.[0] ? pick(r.problems[0].titulo) : "—")}` : `${r.idx}. ${pick(r.title)}${r.is_boss ? " 👹" : ""} · ${r.points}×${r.multiplier} · ${Math.round((r.duration_s || 0) / 60)} min · ${(r.problem_slugs || []).length}`),
          el("span", { class: "badge-pixel" }, t(`tournament.round_state_${r.state}`)),
          (r.problem_slugs || []).length < (isElim() || r.is_boss ? 1 : 3) ? el("span", { class: "badge-pixel text-warning" }, `⚠ ${t("tournament.missing_missions")}`) : null,
          pending && editing !== r.idx ? el("button", { type: "button", class: "btn-pixel btn-pixel--ghost", onclick: () => openEditor(r) }, t("tournament.admin_edit")) : null),
        editing === r.idx ? editorView(r) : null);
    });
    return el("section", { class: "panel-pixel grid gap-2" }, el("h3", {}, t("tournament.admin_rounds")), el("ul", { class: "grid gap-2" }, rows));
  }

  // ---------- Presença ----------
  function presenceView() {
    const pres = data.players || [];
    const on = pres.filter((p) => p.online).length;
    const teams = data.teams || [];
    const moveSelect = (p) => {
      if (data.tournament.mode !== "agencias" || data.tournament.state !== "lobby" || !teams.length) return null;
      const s = el("select", { class: "input-pixel", "aria-label": t("tournament.admin_move") },
        el("option", { value: "" }, t("tournament.admin_move")), teams.filter((x) => x.id !== p.team_id).map((x) => el("option", { value: x.id }, x.name)));
      s.addEventListener("change", async () => { if (s.value) { await call("POST", `/teams/${s.value}/move`, { user_id: p.user_id }); } });
      return s;
    };
    return el("section", { class: "panel-pixel grid gap-2" },
      el("h3", {}, t("tournament.admin_presence", { on, total: pres.length })),
      el("ul", { class: "grid gap-1 text-sm sm:grid-cols-2" }, pres.map((p) => el("li", { class: "flex items-center gap-2" },
        el("span", { "aria-label": p.online ? t("tournament.conn_online") : t("tournament.conn_offline") }, p.online ? "🟢" : "🔴"),
        el("span", { class: "min-w-0 flex-1 truncate" }, p.display_name), moveSelect(p)))),
      pres.length ? null : el("p", { class: "text-sm text-muted" }, t("tournament.admin_no_players")));
  }

  function render() {
    if (!data) { detail.replaceChildren(); return; }
    const tour = data.tournament;
    const projectorUrl = `/pages/projector/projector.html?id=${tour.id}`;
    // Não recriar o editor a meio da escrita: só repinta tudo quando não se está a editar (o poll é pausado)
    detail.replaceChildren(
      el("section", { class: "panel-pixel grid gap-2" },
        el("h3", { class: "text-lg" }, tour.name),
        el("p", { class: "text-sm" }, `${t("tournament.admin_join_code")}: `, el("strong", { class: "text-2xl text-accent" }, tour.join_code || "")),
        el("p", { class: "text-sm text-muted" }, t(`tournament.mode_${tour.mode}`)),
        el("a", { class: "btn-pixel btn-pixel--accent", href: projectorUrl, target: "_blank", rel: "noopener" }, `📽 ${t("tournament.admin_open_projector")}`)),
      ...(isElim() ? [controls(), data.tournament.state === "lobby" ? previewView() : null, groupsView(), roundsView(), presenceView()] : [controls(), roundsView(), presenceView()]).filter(Boolean));
  }

  document.addEventListener("localechange", () => { paintShell(); loadList(); render(); });
  return { setClasses, setActiveClass };
}
