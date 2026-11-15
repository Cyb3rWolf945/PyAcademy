// Cartão de missão da ronda: título, estrelas, tipo e estado (por resolver / resolvida / bloqueada).
import { el } from "./dom.js";
import { t } from "../services/i18n.js";
import { pick, stars } from "../pages/challenge/lib.js";

// missionCard(mission, {index, locked, onOpen}) -> <button>
export function missionCard(mission, { index = 0, locked = false, onOpen } = {}) {
  const solved = !!mission.solved_by_me;
  const cls = `card-mission ${solved ? "card-mission--solved" : ""} ${locked ? "card-mission--locked" : ""}`;
  const status = locked ? "🔒" : solved ? "" : "▶"; // o visto de "resolvida" vem do design (.card-mission--solved)
  return el("button", {
    type: "button", class: `${cls} flex min-h-[64px] w-full items-center gap-3 bg-surface p-3 text-left`,
    disabled: locked, "data-slug": mission.slug || mission.id,
    onclick: () => { if (!locked) onOpen?.(mission); },
  },
  el("span", { class: "font-pixel text-accent", "aria-hidden": "true" }, `#${index + 1}`),
  el("span", { class: "grid min-w-0 flex-1 gap-1" },
    el("span", { class: "truncate font-bold" }, pick(mission.titulo)),
    el("span", { class: "flex flex-wrap items-center gap-2 text-xs text-muted" },
      el("span", { class: "stars text-gold" }, stars(mission.dificuldade)),
      el("span", { class: "badge-pixel" }, t(`tournament.tipo_${mission.tipo}`)),
      mission.hints_opened ? el("span", {}, `💡 ${mission.hints_opened}`) : null)),
  el("span", { class: "text-xl", "aria-label": t(solved ? "tournament.mission_solved" : "tournament.mission_open") }, status));
}
