// Projetor da eliminatória: bracket ao vivo em ecrã grande (colunas por ronda), temporizador gigante,
// ecrã entre rondas e campeão com celebração + pódio (3D com reserva 2D).
import { el } from "../../components/dom.js";
import { t } from "../../services/i18n.js";
import { mountTimer } from "../../components/timer.js";
import { mountPoster } from "./bracket-poster.js";
import { pick } from "../challenge/lib.js";
import { currentRound, roundTitle } from "../tournament/ui.js";
import { celebrateSafe } from "../tournament/fx.js";

export function elimRoundView(live, stage) {
  const title = el("h2", { class: "min-w-0 flex-1 font-pixel text-[2.4vw]" });
  const sub = el("p", { class: "text-[1.4vw] text-muted" });
  const timerHost = el("div");
  const bracketHost = el("div", { class: "h-full overflow-hidden" });
  const top = el("div", { class: "flex items-center gap-[2vw]" }, el("div", { class: "min-w-0 flex-1" }, title, sub), timerHost);
  stage.replaceChildren(el("div", { class: "grid h-full grid-rows-[auto_1fr] gap-[1.5vh]" }, top, bracketHost));
  const timer = mountTimer(timerHost, { className: "text-[5vw] leading-none" });
  const bracket = mountPoster(bracketHost);
  return {
    update() {
      const snap = live.snap();
      const r = currentRound(snap);
      if (!r) return;
      const paused = snap.tournament.state === "round_paused" || r.state === "paused";
      title.textContent = `${roundTitle(r)}${r.is_final ? " 🏁" : ""}`;
      const decided = (r.groups || []).filter((g) => g.decided).length;
      sub.textContent = paused ? `⏸ ${t("tournament.paused_banner")}` : t("projector.groups_decided", { x: decided, y: (r.groups || []).length });
      timer.set({ ends_at: r.ends_at, remaining_s: r.remaining_s, paused });
      timer.setOffset(live.offset());
      bracket.update(snap);
    },
    destroy() { timer.destroy(); bracket.destroy(); stage.replaceChildren(); },
  };
}

export function elimBetweenView(live, stage) {
  const head = el("h2", { class: "font-pixel text-[3vw]" });
  const bracketHost = el("div", { class: "h-full overflow-hidden" });
  stage.replaceChildren(el("div", { class: "grid h-full grid-rows-[auto_1fr] gap-[1.5vh]" }, head, bracketHost));
  const bracket = mountPoster(bracketHost);
  return {
    update() {
      const snap = live.snap();
      const r = currentRound(snap);
      head.textContent = `${t("tournament.round_finished", { title: roundTitle(r) })} · ${t("projector.alive_count", { n: snap.alive_count ?? "?" })}`;
      bracket.update(snap);
    },
    destroy() { bracket.destroy(); stage.replaceChildren(); },
  };
}

export function elimFinalView(live, stage) {
  const title = el("h2", { class: "text-center font-pixel text-[3.6vw] text-gold" });
  const posterHost = el("div", { class: "h-full min-h-0" });
  stage.replaceChildren(el("div", { class: "grid h-full grid-rows-[auto_1fr] gap-[1.5vh]" }, title, posterHost));
  const poster = mountPoster(posterHost);
  let celebrated = false;
  return {
    update() {
      const snap = live.snap();
      title.textContent = snap.champion ? `🏆 ${t("tournament.champion_is", { name: snap.champion.display_name })}` : t("tournament.final_title");
      poster.update(snap);
      if (snap.champion && !celebrated) { celebrated = true; celebrateSafe("podium"); }
    },
    destroy() { poster.destroy(); stage.replaceChildren(); },
  };
}
