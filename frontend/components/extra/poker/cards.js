// Cartas de poker em pixel art, desenhadas aqui (originais): naipes em bitmaps minúsculos escalados sem suavização e
// o verso com um padrão próprio. Se houver sprites do design (assets/sprites/cards/*) podem substituir isto mais tarde.
import { el } from "../../dom.js";
import { t } from "../../../services/i18n.js";

const SUITS = {
  s: { name: "spades", red: false, map: ["...X...", "..XXX..", ".XXXXX.", "XXXXXXX", "XXXXXXX", ".XX.XX.", "...X...", "..XXX.."] },
  h: { name: "hearts", red: true, map: [".XX.XX.", "XXXXXXX", "XXXXXXX", ".XXXXX.", "..XXX..", "...X..."] },
  d: { name: "diamonds", red: true, map: ["...X...", "..XXX..", ".XXXXX.", "XXXXXXX", ".XXXXX.", "..XXX..", "...X..."] },
  c: { name: "clubs", red: false, map: ["..XXX..", ".XXXXX.", "..XXX..", "XX.X.XX", "XXXXXXX", "XX.X.XX", "...X...", "..XXX.."] },
};
const NAMES = { spades: "s", hearts: "h", diamonds: "d", clubs: "c", espadas: "s", copas: "h", ouros: "d", paus: "c", "♠": "s", "♥": "h", "♦": "d", "♣": "c" };
const RANKS = { 10: "T", T: "T", J: "J", Q: "Q", K: "K", A: "A", 1: "A" };

// Aceita "As", "Td", "10h", {rank, suit} e devolve {rank: "A", suit: "s"}; null se for inválida
export function normCard(c) {
  if (!c) return null;
  let rank, suit;
  if (typeof c === "string") { suit = c.slice(-1).toLowerCase(); rank = c.slice(0, -1).toUpperCase(); }
  else { rank = String(c.rank ?? c.r ?? "").toUpperCase(); suit = String(c.suit ?? c.s ?? "").toLowerCase(); }
  suit = SUITS[suit] ? suit : NAMES[suit] || suit;
  rank = RANKS[rank] || rank;
  return SUITS[suit] && /^[2-9TJQKA]$/.test(rank) ? { rank, suit } : null;
}

const cache = new Map();
// Data URL (permitida pela CSP: img-src data:) de um bitmap pixel numa cor
function bitmap(map, color, scale = 1) {
  const key = `${map.join("")}|${color}|${scale}`;
  if (cache.has(key)) return cache.get(key);
  const cv = document.createElement("canvas");
  cv.width = map[0].length * scale; cv.height = map.length * scale;
  const g = cv.getContext("2d");
  g.fillStyle = color;
  map.forEach((row, y) => [...row].forEach((ch, x) => { if (ch === "X") g.fillRect(x * scale, y * scale, scale, scale); }));
  const url = cv.toDataURL("image/png");
  cache.set(key, url);
  return url;
}
const suitImg = (suit, cls) => el("img", { class: `pk-suit ${cls || ""}`, src: bitmap(SUITS[suit].map, SUITS[suit].red ? "#c23b3b" : "#1f2a44"), alt: "", width: SUITS[suit].map[0].length, height: SUITS[suit].map.length });

export const rankLabel = (r) => (r === "T" ? "10" : r);
export const cardName = (c) => (c ? `${rankLabel(c.rank)} ${t(`poker.suit_${SUITS[c.suit].name}`)}` : t("poker.card_back"));

// Sprites do design (assets/sprites/cards/{lg|sm}/<valor><naipe>.png, 48×64 e 24×32, escala inteira); se faltar um ficheiro,
// cai para a carta desenhada aqui (naipes em bitmap + texto).
const SPRITE = { xl: ["lg", 2], lg: ["lg", 1], md: ["lg", 1], sm: ["sm", 1], xs: ["sm", 1] };
const spriteName = (c) => `${c.rank === "T" ? "10" : c.rank}${c.suit}`;

function drawnFace(c, size) {
  return [el("span", { class: "pk-rank" }, rankLabel(c.rank)), suitImg(c.suit, "pk-suit--small"), suitImg(c.suit, "pk-suit--big")];
}

// cardEl(card | null, {size: "xs"|"sm"|"md"|"lg"|"xl", down}) -> elemento. card null ou down = verso.
export function cardEl(card, { size = "md", down = false } = {}) {
  const c = normCard(card);
  const [dir, mult] = SPRITE[size] || SPRITE.md;
  const file = !c || down ? "back" : spriteName(c);
  const px = dir === "lg" ? [48, 64] : [24, 32];
  const img = el("img", { class: "pk-sprite", src: `/assets/sprites/cards/${dir}/${file}.png`, width: px[0] * mult, height: px[1] * mult, alt: "" });
  const node = el("div", { class: `pk-card pk-card--${size} pk-card--sprite`, role: "img", "aria-label": !c || down ? t("poker.card_back") : cardName(c), "data-card": c && !down ? `${c.rank}${c.suit}` : "back" }, img);
  img.addEventListener("error", () => { // sprite em falta: carta desenhada
    node.classList.remove("pk-card--sprite");
    if (!c || down) { node.classList.add("pk-card--back"); node.replaceChildren(el("span", { class: "pk-back-mark", "aria-hidden": "true" })); }
    else { node.classList.toggle("is-red", SUITS[c.suit].red); node.replaceChildren(...drawnFace(c, size)); }
  }, { once: true });
  return node;
}

// Espaço vazio para a mesa (cartas comunitárias ainda por sair)
export const cardSlot = (size = "md") => el("div", { class: `pk-card pk-card--${size} pk-card--slot`, "aria-hidden": "true" });
