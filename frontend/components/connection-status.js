// Indicador de ligação em tempo real: 🟢 online · 🟡 a reconectar · 🔴 offline (com texto para leitores de ecrã).
import { el } from "./dom.js";
import { t } from "../services/i18n.js";

const ICON = { online: "🟢", reconnecting: "🟡", offline: "🔴" };

export function mountConnectionStatus(host, { showLabel = true } = {}) {
  const icon = el("span", { "aria-hidden": "true" }, ICON.reconnecting);
  const label = el("span", { class: showLabel ? "hidden text-xs text-muted sm:inline" : "sr-only" });
  const box = el("span", { class: "inline-flex min-h-[44px] items-center gap-1", role: "status" }, icon, label);
  host.replaceChildren(box);
  let current = "reconnecting";
  const paint = () => { icon.textContent = ICON[current]; label.textContent = t(`tournament.conn_${current}`); box.setAttribute("aria-label", label.textContent); box.title = label.textContent; };
  document.addEventListener("localechange", paint);
  paint();
  return {
    set(status) { if (ICON[status]) { current = status; paint(); } },
    destroy() { document.removeEventListener("localechange", paint); host.replaceChildren(); },
  };
}
