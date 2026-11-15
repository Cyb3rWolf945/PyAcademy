// Ecrã da ronda (aluno): cabeçalho com temporizador, cartões de missão, mini-ranking e a vista de missão em ecrã inteiro.
import { el } from "../../components/dom.js";
import { t } from "../../services/i18n.js";
import { mountTimer } from "../../components/timer.js";
import { mountLeaderboard } from "../../components/leaderboard.js";
import { missionCard } from "../../components/mission-card.js";
import { onQueueEvent, queuedSubmissions } from "../../services/storage.js";
import { mountMission } from "../challenge/mission.js";
import { mountAgencyPicker } from "./lobby.js";
import { fmtPoints } from "../challenge/lib.js";
import { currentRound, roundTitle, myRow, myTeam, TEAM_BG } from "./ui.js";

export function mountRound(host, live) {
  const title = el("h2", { class: "min-w-0 flex-1 text-lg" });
  const badge = el("span", { class: "badge-pixel", hidden: true }, t("tournament.boss"));
  const timerHost = el("div");
  const pausedBanner = el("p", { class: "bg-warning p-2 text-center text-sm text-accent-text", role: "status", hidden: true }, t("tournament.paused_banner"));
  const queueBanner = el("p", { class: "bg-surface-2 p-2 text-center text-sm text-warning", role: "status", hidden: true });
  const head = el("section", { class: "panel-pixel grid gap-2" }, el("div", { class: "flex items-center gap-2" }, title, badge), timerHost, pausedBanner);
  const agency = el("p", { class: "flex items-center gap-2 text-sm" });
  const noAgency = el("section", { class: "grid gap-2", hidden: true }, el("p", { class: "bg-warning p-2 text-sm text-accent-text", role: "alert" }, t("tournament.no_agency_warning")));
  const pickerHost = el("div", { class: "grid gap-3" });
  noAgency.append(pickerHost);
  let picker = null;
  const progress = el("p", { class: "text-sm text-muted" });
  const missions = el("section", { class: "grid gap-2" });
  const scoreLine = el("p", { class: "text-sm" });
  const lbHost = el("div");
  const board = el("section", { class: "panel-pixel grid gap-2" }, el("h3", { class: "text-base" }, t("tournament.leaderboard")), scoreLine, lbHost);
  host.replaceChildren(head, queueBanner, noAgency, agency, progress, missions, board);

  const snap0 = live.snap();
  const timer = mountTimer(timerHost, { className: "text-4xl" });
  const lb = mountLeaderboard(lbHost, { meKey: snap0.me?.participant_key, limit: 5 });
  const missionHost = document.getElementById("mission-host");
  let opened = null;
  let sig = "";

  function paintQueue() {
    const n = queuedSubmissions().length;
    queueBanner.hidden = n === 0;
    queueBanner.textContent = n ? t("tournament.queue_pending", { n }) : "";
  }
  const offQueue = onQueueEvent(paintQueue);

  function closeMission() { opened?.destroy(); opened = null; document.body.classList.remove("overflow-hidden"); }

  function open(m) {
    const snap = live.snap();
    const r = currentRound(snap);
    closeMission();
    document.body.classList.add("overflow-hidden");
    opened = mountMission(missionHost, {
      mission: { ...m },
      ctx: {
        tournamentId: snap.tournament.id, roundIdx: r.idx,
        canSubmit: () => live.snap().tournament.state === "round_active",
        onResult: (res) => { if (res.status === "accepted") live.refresh(); },
        onClose: closeMission,
        onTeamRequired: () => { closeMission(); live.refresh(); }, // sem agência: volta ao ecrã da ronda, que mostra o aviso
      },
    });
  }

  function update() {
    const snap = live.snap();
    const r = currentRound(snap);
    if (!r) return;
    const paused = snap.tournament.state === "round_paused" || r.state === "paused";
    title.textContent = roundTitle(r);
    badge.hidden = !r.is_boss;
    pausedBanner.hidden = !paused;
    timer.set({ ends_at: r.ends_at, remaining_s: r.remaining_s, paused });
    timer.setOffset(live.offset());

    const team = myTeam(snap);
    noAgency.hidden = !(snap.tournament.mode === "agencias" && !team);
    if (!noAgency.hidden) { picker ??= mountAgencyPicker(pickerHost, live); picker.update(); }
    agency.replaceChildren(...(snap.tournament.mode === "agencias" && team
      ? [el("span", { class: `inline-block h-4 w-4 ${TEAM_BG[team.color_idx % 8]}`, "aria-hidden": "true" }), el("span", {}, t("tournament.your_agency", { name: team.name }))] : []));

    // só mostra missões do snapshot da ronda atual (durante a transição entre rondas podem ser as da anterior)
    const list = snap.current?.idx === r.idx ? snap.current.missions || [] : [];
    const solved = list.filter((m) => m.solved_by_me).length;
    progress.textContent = t("tournament.missions_progress", { x: solved, y: list.length });
    const nextSig = list.map((m) => `${m.slug || m.id}:${m.solved_by_me ? 1 : 0}:${m.hints_opened || 0}`).join("|");
    if (nextSig !== sig) {
      sig = nextSig;
      missions.replaceChildren(...list.map((m, i) => missionCard(m, { index: i, onOpen: open })));
    }
    const mine = myRow(snap);
    scoreLine.textContent = mine ? t("tournament.your_rank", { rank: mine.rank, points: fmtPoints(mine.points) }) : t("tournament.no_points_yet");
    lb.setMe(snap.me?.participant_key);
    lb.update(snap.leaderboard, snap.teams);
    if (opened) { const m = list.find((x) => (x.slug || x.id) === opened.slug); opened.update(m); }
    paintQueue();
  }

  document.addEventListener("localechange", update);
  return {
    update,
    destroy() {
      closeMission(); offQueue(); timer.destroy(); picker?.destroy();
      document.removeEventListener("localechange", update);
      host.replaceChildren();
    },
  };
}
