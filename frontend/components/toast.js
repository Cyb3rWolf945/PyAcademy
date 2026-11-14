// Avisos curtos (toasts) no canto do ecrã. O texto entra por textContent.
import { el } from "./dom.js";

let box = null;

export function toast(message, kind = "info") {
  if (!box) {
    box = el("div", { class: "fixed inset-x-0 top-0 z-50 flex flex-col items-center gap-2 p-3 pointer-events-none", "aria-live": "polite" });
    document.body.append(box);
  }
  const colors = kind === "error" ? "bg-danger text-accent-text" : kind === "success" ? "bg-success text-accent-text" : "bg-surface-2 text-text";
  const node = el("div", { class: `panel-pixel pointer-events-auto max-w-sm w-full text-sm ${colors}`, role: kind === "error" ? "alert" : "status" }, message);
  box.append(node);
  setTimeout(() => node.remove(), 4500);
}
