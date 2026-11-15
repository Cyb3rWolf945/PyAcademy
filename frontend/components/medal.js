// Medalha pixel do top 3: 1.º ouro, 2.º bronze, 3.º cobre (nunca prata). Com um pequeno "bob" em steps() (parado com reduced-motion).
import { el } from "./dom.js";
import { t } from "../services/i18n.js";

const KIND = ["gold", "bronze", "copper"];
// rank 1..3 -> <img> (ou null). opts.size 32|64 escolhe o ficheiro; opts.cls acrescenta classes (tamanho).
export function medalImg(rank, { size = 32, cls = "medal", bob = true } = {}) {
  const kind = KIND[rank - 1];
  if (!kind) return null;
  return el("img", { class: `${cls}${bob ? " anim-bob" : ""}`, src: `/assets/sprites/medals/${kind}-${size}.png`, width: size, height: size, alt: t(`medal.${kind}`) });
}
