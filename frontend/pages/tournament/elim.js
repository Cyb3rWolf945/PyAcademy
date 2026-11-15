// Eliminatória (aluno): ecrã da ronda (exercício + painel do grupo + temporizador), modo espectador para eliminados
// e ecrã entre rondas ("Venceste o grupo!" / "Foste eliminado"). O painel mostra testes passados e tentativas, nunca código.
import { el } from "../../components/dom.js";
import { icon } from "../../components/icon.js";
import { t } from "../../services/i18n.js";
import { mountTimer } from "../../components/timer.js";
import { missionCard } from "../../components/mission-card.js";
import { mountBracket, memberRow } from "../../components/bracket.js";
import { onQueueEvent, queuedSubmissions } from "../../services/storage.js";
import { mountMission } from "../challenge/mission.js";
import { fmtPoints } from "../challenge/lib.js";
import { currentRound, roundTitle } from "./ui.js";
import { celebrateSafe } from "./fx.js";

export const myGroup = (snap, round) => round?.groups?.find((g) => g.id === snap.me?.group_id)
  || round?.groups?.find((g) => g.members?.some((m) => m.user_id === snap.me?.user_id)) || null;

// Painel do grupo: adversários com barra X/Y testes e tentativas, 🏆 no vencedor
function groupPanel(group, meId, { compact = false } = {}) {
  if (!group) return el("p", { class: "text-sm text-muted" }, t("tournament.no_group"));
  const winners = (group.members || []).filter((m) => m.status === "winner");
  return el("div", { class: "grid gap-1" },
    group.decided && winners.length
      ? el("p", { class: "bg-success/25 p-2 text-sm font-bold" }, `🏆 ${t("tournament.group_won_by", { name: winners.map((w) => w.display_name).join(", ") })}`) : null,
    ...(group.members || []).map((m) => memberRow(m, { meId, attempts: !compact })));
}

export function mountElimRound(host, live) {
  const title = el("h2", { class: "min-w-0 flex-1 text-lg" });
  const badge = el("span", { class: "badge-pixel", hidden: true });
  const timerHost = el("div");
  const pausedBanner = el("p", { class: "bg-warning p-2 text-center text-sm text-accent-text", role: "status", hidden: true }, t("tournament.paused_banner"));
  const head = el("section", { class: "panel-pixel grid gap-2" }, el("div", { class: "flex items-center gap-2" }, title, badge), timerHost, pausedBanner);
  const banner = el("section", { class: "panel-pixel grid gap-2", hidden: true });
  const queueBanner = el("p", { class: "bg-surface-2 p-2 text-center text-sm text-warning", role: "status", hidden: true });
  const exercise = el("section", { class: "grid gap-2" });
  const groupBox = el("section", { class: "panel-pixel grid gap-2" });
  const pointsLine = el("p", { class: "text-sm text-accent" });
  const bracketHost = el("div");
  const bracketBox = el("section", { class: "panel-pixel grid gap-2" }, el("h3", { class: "text-base" }, t("tournament.bracket")), bracketHost);
  host.replaceChildren(head, banner, queueBanner, exercise, groupBox, pointsLine, bracketBox);

  const timer = mountTimer(timerHost, { className: "text-4xl" });
  const bracket = mountBracket(bracketHost, { meId: live.snap().me?.user_id });
  const missionHost = document.getElementById("mission-host");
  let opened = null, headerExtra = null, wasWinner = false, sig = "";

  const paintQueue = () => { const n = queuedSubmissions().length; queueBanner.hidden = !n; queueBanner.textContent = n ? t("tournament.queue_pending", { n }) : ""; };
  const offQueue = onQueueEvent(paintQueue);
  function closeMission() { opened?.destroy(); opened = null; headerExtra = null; document.body.classList.remove("overflow-hidden"); }

  function open(m) {
    const snap = live.snap();
    closeMission();
    document.body.classList.add("overflow-hidden");
    headerExtra = el("div", { class: "max-h-40 overflow-y-auto bg-surface-2 p-2" });
    opened = mountMission(missionHost, {
      mission: { ...m },
      ctx: {
        tournamentId: snap.tournament.id, roundIdx: currentRound(snap).idx, headerExtra,
        canSubmit: () => live.snap().tournament.state === "round_active",
        onResult: (res) => { if (res.status === "accepted") live.refresh(); },
        onClose: closeMission,
      },
    });
  }

  function update() {
    const snap = live.snap();
    const r = currentRound(snap);
    if (!r) return;
    const me = snap.me || {};
    const paused = snap.tournament.state === "round_paused" || r.state === "paused";
    const group = myGroup(snap, r);
    const eliminated = me.status === "eliminated";
    const winner = !!group?.winners?.includes(me.user_id);
    title.textContent = roundTitle(r);
    badge.hidden = !(r.is_final || eliminated);
    badge.textContent = eliminated ? t("tournament.spectator") : t("tournament.final_round");
    pausedBanner.hidden = !paused;
    timer.set({ ends_at: r.ends_at, remaining_s: r.remaining_s, paused });
    timer.setOffset(live.offset());

    // Banner de estado: venceu / eliminado / à espera
    banner.hidden = !(winner || eliminated);
    if (winner) {
      banner.replaceChildren(el("h3", { class: "font-pixel text-xl text-success" }, t("tournament.you_won_group")),
        el("p", { class: "text-sm" }, r.is_final ? t("tournament.you_won_final") : t("tournament.you_advance", { n: r.idx + 1 })),
        el("p", { class: "text-sm text-muted" }, t("tournament.keep_trying_points")));
      if (!wasWinner) { wasWinner = true; celebrateSafe("solve"); }
    } else if (eliminated) {
      banner.replaceChildren(el("h3", { class: "font-pixel text-lg text-warning" }, t("tournament.eliminated_in", { n: me.eliminated_in_round ?? r.idx })),
        el("p", { class: "text-sm" }, t("tournament.practice_help")));
    }

    const mission = snap.current?.idx === r.idx ? snap.current.mission : null;
    const msig = `${mission?.slug || mission?.id}:${mission?.solved_by_me ? 1 : 0}`;
    if (msig !== sig) {
      sig = msig;
      exercise.replaceChildren(...(mission ? [
        el("p", { class: "text-sm text-muted" }, eliminated ? t("tournament.practice_exercise") : t("tournament.group_exercise")),
        missionCard(mission, { index: 0, onOpen: open })] : []));
    }
    groupBox.replaceChildren(el("h3", { class: "text-base" }, eliminated ? t("tournament.groups_live") : t("tournament.your_group")), ...(eliminated ? [] : [groupPanel(group, me.user_id)]));
    groupBox.hidden = eliminated;
    pointsLine.textContent = t("tournament.my_points_tournament", { points: fmtPoints(snap.my_points_this_tournament || 0) });
    bracket.update(snap);
    if (opened) {
      opened.update(mission);
      headerExtra?.replaceChildren(groupPanel(group, me.user_id, { compact: true }));
    }
    paintQueue();
  }
  document.addEventListener("localechange", update);
  return {
    update,
    destroy() { closeMission(); offQueue(); timer.destroy(); bracket.destroy(); document.removeEventListener("localechange", update); host.replaceChildren(); },
  };
}

// Entre rondas: resultado do meu grupo e bracket
export function mountElimBetween(host, live) {
  const head = el("section", { class: "panel-pixel grid gap-2" });
  const bracketHost = el("div");
  host.replaceChildren(head, el("section", { class: "panel-pixel grid gap-2" }, el("h3", { class: "text-base" }, t("tournament.bracket")), bracketHost));
  const bracket = mountBracket(bracketHost, { meId: live.snap().me?.user_id });
  let celebrated = false;

  function update() {
    const snap = live.snap();
    const r = currentRound(snap);
    const me = snap.me || {};
    const group = myGroup(snap, r);
    const won = me.status === "alive" && !!group?.winners?.includes(me.user_id);
    const kids = [];
    if (me.status === "eliminated") {
      kids.push(el("h2", { class: "flex items-center gap-2 font-pixel text-lg text-warning" }, icon("shield"), t("tournament.eliminated_in", { n: me.eliminated_in_round ?? r?.idx })),
        el("p", { class: "text-sm" }, t("tournament.practice_help")));
    } else if (won) {
      kids.push(el("h2", { class: "flex items-center gap-2 font-pixel text-xl text-success anim-pop" }, icon("crown", "anim-bob"), t("tournament.you_won_group")),
        el("p", { class: "text-sm" }, t("tournament.you_advance", { n: (r?.idx ?? 0) + 1 })));
      if (!celebrated) { celebrated = true; celebrateSafe("solve"); }
    }
    kids.push(el("p", { class: "text-sm text-accent" }, t("tournament.my_points_tournament", { points: fmtPoints(snap.my_points_this_tournament || 0) })),
      el("p", { class: "text-sm text-muted" }, t("tournament.waiting_next_draw")));
    head.replaceChildren(...kids);
    bracket.update(snap);
  }
  document.addEventListener("localechange", update);
  return { update, destroy() { bracket.destroy(); document.removeEventListener("localechange", update); host.replaceChildren(); } };
}
