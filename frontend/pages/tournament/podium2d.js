// Pódio 2D em DOM (reserva quando a cena 3D não existe ou falha; também serve o ecrã do aluno).
import { el } from "../../components/dom.js";
import { TEAM_BG } from "./ui.js";
import { fmtPoints } from "../challenge/lib.js";

const MEDAL = ["🥇", "🥈", "🥉"];
const HEIGHT = ["h-40", "h-28", "h-20"];
const HEIGHT_BIG = ["h-[26vh]", "h-[18vh]", "h-[12vh]"];
const MEDAL_BG = ["bg-gold", "bg-silver", "bg-bronze"];

// top3: [{name, points, color_idx?}] -> elemento. big = projetor (texto grande)
export function podium2d(top3, { big = false } = {}) {
  // Ordem visual clássica: 2.º | 1.º | 3.º
  const order = [1, 0, 2].filter((i) => top3[i]);
  const col = (i) => el("div", { class: `${big ? "max-w-[30vw]" : "max-w-[11rem]"} flex min-w-0 flex-1 flex-col items-center justify-end gap-1 anim-pop` },
    el("span", { class: big ? "text-[5vw]" : "text-3xl", "aria-hidden": "true" }, MEDAL[i]),
    el("span", { class: `max-w-full truncate font-pixel font-bold ${big ? "text-[3.2vw] [text-shadow:0_0.2vw_0_var(--c-border)]" : "text-sm"}` }, top3[i].name),
    el("span", { class: `font-pixel text-accent ${big ? "text-[3.6vw] [text-shadow:0_0.2vw_0_var(--c-border)]" : "text-xs"}` }, fmtPoints(top3[i].points)),
    el("div", { class: `w-full ${big ? HEIGHT_BIG[i] : HEIGHT[i]} ${top3[i].color_idx != null ? TEAM_BG[top3[i].color_idx % 8] : MEDAL_BG[i]} flex items-start justify-center pt-1 font-pixel text-accent-text` }, `${i + 1}`));
  return el("div", { class: "flex items-end justify-center gap-2" }, order.map(col));
}
