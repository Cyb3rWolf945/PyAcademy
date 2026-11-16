// Torneio (aluno): arranque, ligação ao vivo e troca de ecrã conforme o estado (lobby, ronda, entre rondas, final).
import { bootPage } from "../../services/page.js";
import { api, errorText } from "../../services/api.js";
import { t } from "../../services/i18n.js";
import { toast } from "../../components/toast.js";
import { mountConnectionStatus } from "../../components/connection-status.js";
import { flushQueue, startQueueLoop } from "../../services/storage.js";
import { createLive } from "./live.js";
import { mountJoin } from "./join.js";
import { mountLobby } from "./lobby.js";
import { mountRound } from "./round.js";
import { mountBetween } from "./between.js";
import { mountFinal } from "./final.js";
import { mountElimRound, mountElimBetween } from "./elim.js";
import { fmtPoints } from "../challenge/lib.js";
import { celebrateSafe } from "./fx.js";
import { el } from "../../components/dom.js";

const me = await bootPage({ access: "guest" });

function main() {
  const view = document.getElementById("view");
  if (me?.role === "teacher") {
    mountTeacherHub(view);
    return;
  }
  const params = new URLSearchParams(location.search);
  const conn = mountConnectionStatus(document.getElementById("conn"));
  document.getElementById("conn").hidden = true;
  startQueueLoop();
  flushQueue();

  let live = null, current = null, kind = null;

  function showJoin(error) {
    live?.destroy(); live = null; current?.destroy(); current = null; kind = null;
    document.getElementById("conn").hidden = true;
    document.getElementById("page-title").textContent = "PyArena";
    current = mountJoin(view, { code: params.get("code") || "", error, guest: !me, onJoined: (id) => start(id) });
  }

  async function start(id) {
    live?.destroy();
    current?.destroy(); current = null; kind = null;
    live = createLive(id, {
      onChange: render,
      onStatus: (s) => conn.set(s),
      onEvent: onEvent,
    });
    try { await live.start(); }
    catch (err) {
      live = null;
      history.replaceState(null, "", location.pathname);
      // Um id guardado pode pertencer a outro torneio, turma ou conta. Nesse
      // caso não bloqueamos a entrada atual com um erro de um torneio antigo.
      showJoin(errorText(err));
      return;
    }
    history.replaceState(null, "", `${location.pathname}?id=${id}`);
    document.getElementById("conn").hidden = false;
    render();
  }

  function viewKind(snap) {
    switch (snap.tournament.state) {
      case "lobby": return "lobby";
      case "round_active": case "round_paused": return "round";
      case "between_rounds": return "between";
      default: return "final";
    }
  }

  const factories = { lobby: mountLobby, round: mountRound, between: mountBetween, final: mountFinal };
  const elimFactories = { ...factories, round: mountElimRound, between: mountElimBetween };

  function render() {
    const snap = live?.snap();
    if (!snap) return;
    document.getElementById("page-title").textContent = snap.tournament.name;
    const next = viewKind(snap);
    if (next !== kind) {
      current?.destroy();
      kind = next;
      current = (snap.format === "eliminatoria" ? elimFactories : factories)[next](view, live);
      if (next === "final") celebrateSafe("podium");
    }
    current.update();
  }

  function onEvent(ev) {
    const p = ev.payload || {};
    const snap = live.snap();
    const mine = (key) => key === snap?.me?.participant_key;
    if (ev.type === "points_awarded") { toast(t("tournament.toast_points", { points: fmtPoints(p.points) }), "success"); return; }
    if (ev.type === "champion" && p.user_id === snap?.me?.user_id) celebrateSafe("podium");
    if (ev.type === "group_decided" && snap?.format === "eliminatoria") return;
    if (ev.type === "mission_solved" && mine(p.participant_key)) { toast(t("tournament.toast_my_solve", { points: fmtPoints(p.points) }), "success"); celebrateSafe("solve"); }
    else if (ev.type === "first_bonus") toast(t("tournament.toast_first_bonus", { name: p.name }), "success");
    else if (ev.type === "boss_defeated") { toast(t("tournament.toast_boss", { name: p.name }), "success"); celebrateSafe("boss"); }
    else if (ev.type === "round_started") toast(t("tournament.toast_round_started"), "info");
    else if (ev.type === "round_closed") toast(t("tournament.toast_round_closed"), "info");
  }

  // Ao trocar de idioma, refaz o ecrã atual (exceto com uma missão aberta, para não fechar o editor a meio)
  document.addEventListener("localechange", () => {
    if (!live?.snap() || document.getElementById("mission-host").childElementCount) return;
    current?.destroy(); current = null; kind = null; render();
  });

  const id = params.get("id");
  if (id) start(id);
  else showJoin();
}

function mountTeacherHub(host) {
  const code = el("input", { class: "input-pixel uppercase", name: "join_code", maxlength: 6, required: true, autocapitalize: "characters", autocomplete: "off", "aria-label": t("tournament.teacher_code") });
  const error = el("p", { class: "min-h-5 text-danger", role: "alert" });
  const open = el("button", { class: "btn-pixel btn-pixel--accent", type: "submit" }, t("tournament.teacher_open"));
  const form = el("form", { class: "panel-pixel grid gap-3" },
    el("h2", { class: "text-lg" }, t("tournament.teacher_join_title")),
    el("p", { class: "text-sm text-muted" }, t("tournament.teacher_join_help")),
    code, error, open);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    open.disabled = true;
    error.textContent = "";
    try {
      const result = await api("GET", `/api/tournaments/lookup?join_code=${encodeURIComponent(code.value)}`);
      location.assign(`/pages/projector/projector.html?id=${result.tournament_id}`);
    } catch (err) {
      error.textContent = errorText(err);
      open.disabled = false;
    }
  });
  const create = el("a", { class: "btn-pixel", href: "/pages/admin/admin.html" }, t("tournament.teacher_create"));
  host.replaceChildren(
    el("section", { class: "grid gap-4" },
      form,
      el("section", { class: "panel-pixel grid gap-3" },
        el("h2", { class: "text-lg" }, t("tournament.teacher_create_title")),
        el("p", { class: "text-sm text-muted" }, t("tournament.teacher_create_help")),
        create)));
}

main();
