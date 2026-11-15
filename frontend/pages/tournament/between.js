// Ecrã entre rondas: resultado até agora, a tua posição e a pré-visualização da próxima ronda.
import { el } from "../../components/dom.js";
import { icon } from "../../components/icon.js";
import { t } from "../../services/i18n.js";
import { mountLeaderboard } from "../../components/leaderboard.js";
import { fmtPoints } from "../challenge/lib.js";
import { currentRound, nextRound, roundTitle, myRow } from "./ui.js";

export function mountBetween(host, live) {
  const head = el("section", { class: "panel-pixel grid gap-2" });
  const lbHost = el("div");
  const board = el("section", { class: "panel-pixel grid gap-2" }, el("h3", { class: "text-base" }, t("tournament.leaderboard")), lbHost);
  host.replaceChildren(head, board);
  const lb = mountLeaderboard(lbHost, { meKey: live.snap().me?.participant_key, limit: 8 });

  function update() {
    const snap = live.snap();
    const done = currentRound(snap);
    const next = nextRound(snap);
    const mine = myRow(snap);
    head.replaceChildren(...[
      el("h2", { class: "flex items-center gap-2 text-lg" }, icon(done ? "scroll" : "clock"), done ? t("tournament.round_finished", { title: roundTitle(done) }) : t("tournament.between_title")),
      mine ? el("p", { class: "text-accent" }, t("tournament.your_rank", { rank: mine.rank, points: fmtPoints(mine.points) })) : null,
      next
        ? el("div", { class: "grid gap-1 bg-surface-2 p-3" },
          el("p", { class: "text-xs text-muted" }, t("tournament.next_round")),
          el("p", { class: "font-bold" }, `${roundTitle(next)}${next.is_boss ? ` · ${t("tournament.boss")}` : ""}`),
          el("p", { class: "text-sm text-muted" }, next.is_boss ? t("tournament.boss_help") : t("tournament.next_round_info", { n: next.mission_count, points: next.points * (next.multiplier || 1) })))
        : el("p", { class: "text-muted" }, t("tournament.no_more_rounds")),
      el("p", { class: "text-sm text-muted" }, t("tournament.waiting_teacher"))].filter(Boolean));
    lb.setMe(snap.me?.participant_key);
    lb.update(snap.leaderboard, snap.teams);
  }
  document.addEventListener("localechange", update);
  return { update, destroy() { document.removeEventListener("localechange", update); host.replaceChildren(); } };
}
