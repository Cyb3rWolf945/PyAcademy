// Avisos curtos (toasts) em estilo pixel (.toast-pixel) no topo do ecrã. O texto entra por textContent.
import { el } from "./dom.js";

let box = null;

export function toast(message, kind = "info") {
  if (!box) {
    box = el("div", { class: "fixed inset-x-0 top-0 z-50 flex flex-col items-center gap-3 p-3 pt-[max(0.75rem,env(safe-area-inset-top))] pointer-events-none", "aria-live": "polite" });
    document.body.append(box);
  }
  const mod = kind === "error" ? " toast-pixel--error" : kind === "success" ? " toast-pixel--success" : "";
  const node = el("div", { class: `toast-pixel anim-pop${mod}`, role: kind === "error" ? "alert" : "status" }, message);
  box.append(node);
  setTimeout(() => node.remove(), 4500);
}
