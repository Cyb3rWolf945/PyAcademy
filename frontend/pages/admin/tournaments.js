// Secção "Torneios" do painel do professor: criar, editar rondas (seletor de problemas), painel de controlo grande,
// presença dos alunos e ligação ao projetor. Os botões perigosos pedem um segundo toque para confirmar.
import { api, errorText } from "../../services/api.js";
import { t, getLocale } from "../../services/i18n.js";
import { el } from "../../components/dom.js";
import { toast } from "../../components/toast.js";
import { pick, stars } from "../challenge/lib.js";
import { fmtClock } from "../../components/timer.js";

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
  const createForm = el("form", { class: "grid gap-3" });
  const list = el("ul", { class: "grid gap-2" });
  const detail = el("div", { class: "grid gap-3" });
  const heading = el("h2", { class: "text-lg" });
  // Textos do cabeçalho e do formulário: refeitos quando o idioma muda (os campos mantêm o valor)
  function paintShell() {
    heading.textContent = t("tournament.admin_title");
    const mode = modeSelect.value;
    modeSelect.replaceChildren(el("option", { value: "agencias" }, t("tournament.mode_agencias")), el("option", { value: "individual" }, t("tournament.mode_individual")));
    if (mode) modeSelect.value = mode;
    createForm.replaceChildren(
      el("h3", {}, t("tournament.admin_new")),
      el("label", { class: "grid gap-1 text-sm" }, el("span", {}, t("tournament.admin_class")), classSelect),
      el("label", { class: "grid gap-1 text-sm" }, el("span", {}, t("tournament.admin_name")), nameInput),
      el("label", { class: "grid gap-1 text-sm" }, el("span", {}, t("tournament.admin_mode")), modeSelect),
      el("button", { class: "btn-pixel btn-pixel--accent", type: "submit" }, t("tournament.admin_create")));
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

  createForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      const res = await api("POST", "/api/tournaments", { class_id: Number(classSelect.value), name: nameInput.value.trim(), mode: modeSelect.value });
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
  function controls() {
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
      await api("PUT", `/api/tournaments/${selected}/rounds/${editing}`, {
        title: draft.title, problem_slugs: draft.slugs, points: draft.points, multiplier: draft.multiplier, duration_s: Math.round(draft.duration_min * 60),
      });
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
      const rows = all.filter((p) => (!filters.bloco || p.bloco === filters.bloco) && (!filters.tipo || p.tipo === filters.tipo)
        && (!filters.dificuldade || String(p.dificuldade) === filters.dificuldade)
        && (!needle || `${p.titulo.pt} ${p.titulo.en} ${p.id}`.toLowerCase().includes(needle))).slice(0, 80);
      results.replaceChildren(...rows.map((p) => el("li", {}, el("button", {
        type: "button", class: "btn-pixel btn-pixel--ghost w-full justify-between text-left", disabled: draft.slugs.includes(p.id),
        onclick: () => { draft.slugs.push(p.id); render(); },
      }, el("span", { class: "min-w-0 truncate" }, p.estado === "rascunho" ? `[${t("tournament.draft")}] ` : "", pick(p.titulo)), el("span", { class: "shrink-0 text-xs" }, `${stars(p.dificuldade)} ${t(`tournament.tipo_${p.tipo}`)} · B${p.bloco}`)))));
      if (!rows.length) results.replaceChildren(el("li", { class: "text-sm text-muted" }, t("tournament.admin_no_problems")));
    }
    paintResults();
    return el("div", { class: "panel-pixel panel-pixel--inset grid gap-2" },
      el("div", { class: "grid gap-2 sm:grid-cols-4" }, q, sel("bloco", blocos, t("tournament.admin_filter_bloco")), sel("tipo", TIPOS, t("tournament.admin_filter_tipo")), sel("dificuldade", [1, 2, 3, 4, 5], t("tournament.admin_filter_stars"))),
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
      el("div", { class: "grid gap-2 sm:grid-cols-2" },
        el("label", { class: "grid gap-1 text-sm" }, el("span", {}, `${t("tournament.admin_round_title")} (PT)`), tpt),
        el("label", { class: "grid gap-1 text-sm" }, el("span", {}, `${t("tournament.admin_round_title")} (EN)`), ten)),
      el("div", { class: "grid grid-cols-3 gap-2" },
        el("label", { class: "grid gap-1 text-sm" }, el("span", {}, t("tournament.admin_points")), numInput(draft.points, (v) => { draft.points = v; }, { min: 0, max: 1000 })),
        el("label", { class: "grid gap-1 text-sm" }, el("span", {}, t("tournament.admin_multiplier")), numInput(draft.multiplier, (v) => { draft.multiplier = v; }, { min: 1, max: 10, step: 0.5 })),
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
          el("span", { class: "min-w-0 flex-1 text-sm" }, `${r.idx}. ${pick(r.title)}${r.is_boss ? " 👹" : ""} · ${r.points}×${r.multiplier} · ${Math.round((r.duration_s || 0) / 60)} min · ${(r.problem_slugs || []).length}`),
          el("span", { class: "badge-pixel" }, t(`tournament.round_state_${r.state}`)),
          (r.problem_slugs || []).length < (r.is_boss ? 1 : 3) ? el("span", { class: "badge-pixel text-warning" }, `⚠ ${t("tournament.missing_missions")}`) : null,
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
      controls(), roundsView(), presenceView());
  }

  document.addEventListener("localechange", () => { paintShell(); loadList(); render(); });
  return { setClasses };
}
