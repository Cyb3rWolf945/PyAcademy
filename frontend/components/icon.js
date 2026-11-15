// Ícone pixel (sprite 16x16 ampliado) para títulos e estados vazios: icon("crown", "anim-bob") -> <img>.
import { el } from "./dom.js";

export const icon = (name, cls = "") => el("img", { class: `sprite sprite--sm ${cls}`.trim(), src: `/assets/sprites/icons/${name}.png`, width: 24, height: 24, alt: "" });
