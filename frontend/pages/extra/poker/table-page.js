// Página de uma mesa: liga ao tempo real, mostra a mesa, o ecrã de buy-in ao escolher um lugar e o botão de levantar.
import { el } from "../../../components/dom.js";
import { api, errorText } from "../../../services/api.js";
import { t } from "../../../services/i18n.js";
import { toast } from "../../../components/toast.js";
import { mountConnectionStatus } from "../../../components/connection-status.js";
import { createLive } from "../../../components/extra/poker/live.js";
import { mountTable } from "../../../components/extra/poker/table.js";
import { fmt } from "../../../components/extra/poker/chips.js";

export function mountTablePage(host, { id, info, me, goLobby }) {
  const connHost = document.getElementById("conn");
  connHost.hidden = false;
  const conn = mountConnectionStatus(connHost);
  const title = document.getElementById("page-title");
  const head = el("div", { class: "flex flex-wrap items-center gap-2" });
  const live_ = el("div", { class: "sr-only", role: "status", "aria-live": "polite" });
  const stage = el("div");
  const dialogHost = document.getElementById("dialog-host");
  host.replaceChildren(head, stage, live_);
  const say = (m) => { live_.textContent = ""; setTimeout(() => { live_.textContent = m; }, 20); };

  let tableView = null, destroyed = false;
  const live = createLive(id, {
    onChange: () => { render(); },
    onStatus: (s) => conn.set(s),
    onEvent: (ev) => tableView?.onEvent(ev),
  });

  function render() {
    const snap = live.snap();
    if (!snap || destroyed) return;
    title.textContent = snap.table?.name ?? t("poker.title");
    const seated = snap.me?.seat != null;
    head.replaceChildren(...[
      el("button", { type: "button", class: "btn-pixel btn-pixel--ghost", onclick: () => back() }, `← ${t("poker.back")}`),
      el("span", { class: "text-sm text-muted" }, t("poker.blinds_n", { sb: snap.table?.small_blind ?? 1, bb: snap.table?.big_blind ?? 2 })),
      seated ? el("button", { type: "button", class: "btn-pixel btn-pixel--ghost ml-auto", onclick: leave }, t("poker.leave")) : null].filter(Boolean));
    tableView?.update();
  }

  async function back() { if (live.snap()?.me?.seat != null && !confirm(t("poker.leave_confirm"))) return; await live.leave().catch(() => {}); goLobby(); }
  async function leave() { try { await live.leave(); toast(t("poker.left"), "info"); } catch (err) { toast(errorText(err), "error"); } }

  // ---- buy-in ----
  async function askBuyIn(seat) {
    let meInfo = info;
    try { meInfo = await api("GET", "/api/extra/poker/me"); } catch (_) { /* usa o que já temos */ }
    const bal = meInfo.balance ?? meInfo.available ?? 0;
    const min = meInfo.buy_in_min ?? 10, max = meInfo.buy_in_max ?? Math.min(200, Math.floor(bal * 0.5));
    if (meInfo.can_play === false || max < min) { toast(t(meInfo.reason ? `poker.reason_${meInfo.reason}` : "poker.no_balance"), "error"); return; }
    let val = Math.min(max, Math.max(min, Math.round((min + max) / 2)));
    const out = el("output", { class: "font-pixel text-xl text-accent" }, fmt(val));
    const slider = el("input", { type: "range", class: "pk-slider", min: String(min), max: String(max), step: "1", value: String(val), "aria-label": t("poker.buy_in") });
    slider.addEventListener("input", () => { val = Number(slider.value); out.textContent = fmt(val); });
    const ok = el("button", { type: "button", class: "btn-pixel btn-pixel--accent btn-pixel--lg" }, t("poker.sit_confirm"));
    const cancel = el("button", { type: "button", class: "btn-pixel btn-pixel--ghost" }, t("tournament.cancel"));
    const dlg = el("div", { class: "pk-dialog", role: "dialog", "aria-modal": "true", "aria-labelledby": "bi-h" },
      el("div", { class: "panel-pixel grid gap-3" },
        el("h2", { id: "bi-h", class: "text-lg" }, t("poker.buy_in_title", { n: seat + 1 })),
        el("p", { class: "text-sm" }, t("poker.buy_in_help", { min: fmt(min), max: fmt(max), bal: fmt(bal) })), out, slider,
        el("div", { class: "flex gap-2" }, ok, cancel)));
    const close = () => dialogHost.replaceChildren();
    cancel.addEventListener("click", close);
    dlg.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
    ok.addEventListener("click", async () => {
      ok.disabled = true;
      try { await live.sit(seat, val); close(); say(t("poker.seated")); } catch (err) { toast(errorText(err), "error"); ok.disabled = false; }
    });
    dialogHost.replaceChildren(dlg);
    slider.focus();
  }

  (async () => {
    try { await live.start(); } catch (err) { toast(errorText(err), "error"); goLobby(); return; }
    tableView = mountTable(stage, live, { onSit: askBuyIn, say });
    render();
  })();

  const onLocale = () => render();
  document.addEventListener("localechange", onLocale);
  return {
    destroy() {
      destroyed = true; document.removeEventListener("localechange", onLocale);
      live.destroy(); tableView?.destroy(); conn.destroy(); connHost.hidden = true; dialogHost.replaceChildren(); host.replaceChildren();
      document.getElementById("page-title").textContent = t("poker.title");
    },
  };
}
