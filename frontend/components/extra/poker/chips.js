// Fichas em pixel: valor em fichas por denominação (1, 5, 25, 100, 500) desenhadas com DOM/CSS (blocos com listras).
import { el } from "../../dom.js";

const DENOMS = [[500, "pk-chip--c5"], [100, "pk-chip--c4"], [25, "pk-chip--c3"], [5, "pk-chip--c2"], [1, "pk-chip--c1"]];
const nf = () => new Intl.NumberFormat(document.documentElement.lang === "en" ? "en-GB" : "pt-PT");
export const fmt = (n) => nf().format(Math.round(n || 0));

// Decompõe um valor em fichas (máx. `max` desenhadas, para não encher o ecrã)
export function chipList(amount, max = 5) {
  const out = [];
  let left = Math.max(0, Math.round(amount));
  for (const [v, cls] of DENOMS) {
    while (left >= v && out.length < max) { out.push(cls); left -= v; }
  }
  if (!out.length && amount > 0) out.push(DENOMS[DENOMS.length - 1][1]);
  return out;
}

const COLOR = { "pk-chip--c1": "white", "pk-chip--c2": "red", "pk-chip--c3": "blue", "pk-chip--c4": "green", "pk-chip--c5": "black" };
// Ficha: sprite do design (assets/sprites/chips/<cor>-16.png); a cor também fica na classe (reserva em CSS se a imagem faltar)
export const chipImg = (cls, size = 16) => el("img", { class: `pk-chip ${cls}`, src: `/assets/sprites/chips/${COLOR[cls]}-${size}.png`, width: size, height: size, alt: "" });

// chips(amount, {label, max}) -> pilha de fichas + número ("42")
export function chips(amount, { label = true, max = 5, cls = "" } = {}) {
  const list = chipList(amount, max);
  const stack = el("span", { class: "pk-chips", "aria-hidden": "true" }, ...list.map((c) => chipImg(c)));
  return el("span", { class: `pk-chipwrap ${cls}` }, stack, label ? el("b", { class: "pk-amt" }, fmt(amount)) : null);
}
