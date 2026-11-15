// Efeitos de celebração: usa scenes/celebrate.js (design) e, se não existir ou falhar, uma explosão 2D simples em DOM.
import { el } from "../../components/dom.js";

const EMOJI = { boss: ["🎉", "⭐", "🏆", "💥"], podium: ["🎉", "🥇", "⭐", "🎊"], solve: ["✨", "⭐", "✅"] };

function fallback(kind) {
  const icons = EMOJI[kind] || EMOJI.solve;
  const layer = el("div", { class: "pointer-events-none fixed inset-0 z-[60] overflow-hidden", "aria-hidden": "true" });
  for (let i = 0; i < (kind === "solve" ? 10 : 28); i++) {
    const p = el("span", { class: "anim-float-up absolute text-3xl" }, icons[i % icons.length]);
    p.style.left = `${Math.random() * 100}%`;
    p.style.top = `${60 + Math.random() * 40}%`;
    p.style.animationDelay = `${Math.random() * 0.6}s`;
    layer.append(p);
  }
  document.body.append(layer);
  setTimeout(() => layer.remove(), 3500);
}

// kind: "boss" | "podium" | "solve"
export async function celebrateSafe(kind) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches && kind === "solve") return;
  try {
    const m = await import("/scenes/celebrate.js");
    await m.celebrate(document.body, { kind });
  } catch (_) { fallback(kind); }
}
