// Temporizador de ronda: conta até ends_at corrigido pela diferença server_now - Date.now(). Continua a contar offline.
// Fica vermelho (timer-pixel--danger) nos últimos 60 s. Em pausa mostra o tempo restante parado.
import { el } from "./dom.js";
import { t } from "../services/i18n.js";

export const fmtClock = (s) => {
  s = Math.max(0, Math.ceil(s));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
};

// mountTimer(host, {className}) -> {set({ends_at, remaining_s, paused, server_now}), setOffset(ms), remaining(), destroy()}
export function mountTimer(host, { className = "", onExpire } = {}) {
  const clock = el("span", { class: `timer-pixel ${className}`, role: "timer" });
  const note = el("span", { class: "block text-xs text-muted" });
  host.replaceChildren(el("div", { class: "grid justify-items-center" }, clock, note));
  let offset = 0; // servidor - cliente, em ms
  let endsAt = null;
  let frozen = null; // segundos restantes quando em pausa
  let expired = false;
  let lastShown = "";

  const remaining = () => (frozen != null ? frozen : endsAt == null ? null : (endsAt - (Date.now() + offset)) / 1000);

  function paint() {
    const r = remaining();
    if (r == null) { clock.textContent = "--:--"; note.textContent = ""; return; }
    const text = fmtClock(r);
    if (text !== lastShown) { clock.textContent = text; lastShown = text; }
    clock.classList.toggle("timer-pixel--danger", r <= 60 && r > 0);
    note.textContent = frozen != null ? t("tournament.timer_paused") : r <= 0 ? t("tournament.timer_over") : "";
    if (r <= 0 && frozen == null && !expired) { expired = true; onExpire?.(); }
  }

  const iv = setInterval(paint, 250);
  paint();
  return {
    set({ ends_at, remaining_s, paused, server_now }) {
      if (server_now) { const s = Date.parse(server_now); if (!Number.isNaN(s)) offset = s - Date.now(); }
      expired = false;
      if (paused) { frozen = remaining_s ?? 0; endsAt = null; }
      else { frozen = null; endsAt = ends_at ? Date.parse(ends_at) : null; }
      paint();
    },
    setOffset(ms) { offset = ms; },
    remaining,
    destroy() { clearInterval(iv); host.replaceChildren(); },
  };
}
