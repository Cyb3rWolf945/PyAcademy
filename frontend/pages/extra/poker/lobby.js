// Lista de mesas da turma + criar mesa + o meu saldo de poker (disponível, perda de hoje). Só alunos da mesma turma jogam;
// o professor pode observar. Atualiza de 10 em 10 s (sem WebSocket na lista).
import { el } from "../../../components/dom.js";
import { api, errorText } from "../../../services/api.js";
import { t } from "../../../services/i18n.js";
import { toast } from "../../../components/toast.js";
import { fmt } from "../../../components/extra/poker/chips.js";

export function mountLobby(host, { info, me, open }) {
  let data = info, tables = [], settings = null, timer = null, destroyed = false;
  const summary = el("section", { class: "panel-pixel grid gap-2" });
  const list = el("section", { class: "grid gap-2", "aria-live": "polite" });
  const createBox = el("form", { class: "panel-pixel grid gap-3" });
  host.replaceChildren(summary, list, createBox);

  async function load() {
    try {
      const [a, b, c] = await Promise.all([api("GET", "/api/extra/poker/me"), api("GET", "/api/extra/poker/tables"), api("GET", "/api/extra/settings").catch(() => null)]);
      data = a; tables = b.tables || []; settings = c;
      if (!destroyed) paint();
    } catch (err) { toast(errorText(err), "error"); }
  }

  function paint() {
    const bal = data.balance ?? data.available ?? 0;
    const lossToday = data.today_lost ?? data.loss_today ?? 0, limit = data.daily_loss_limit ?? settings?.poker_daily_loss_limit ?? 100;
    summary.replaceChildren(...[
      el("h2", { class: "text-lg" }, t("poker.balance_title")),
      el("p", { class: "font-pixel text-2xl text-accent" }, t("poker.balance_n", { n: fmt(bal) })),
      el("p", { class: "text-sm text-muted" }, t("poker.loss_today", { n: fmt(lossToday), limit: fmt(limit) })),
      settings && settings.poker_enabled === false ? el("p", { class: "text-sm text-danger" }, t("poker.disabled")) : null,
      el("p", { class: "text-xs text-muted" }, t("poker.balance_help"))].filter(Boolean));
    list.replaceChildren(el("h2", { class: "text-lg" }, t("poker.tables")), ...(tables.length ? tables.map(row) : [el("p", { class: "panel-pixel text-sm text-muted" }, t("poker.no_tables"))]));
    const canCreate = me.role === "teacher" || settings?.students_can_create !== false;
    createBox.hidden = !canCreate || settings?.poker_enabled === false;
    if (!createBox.dataset.built) { build(); createBox.dataset.built = "1"; }
  }

  const row = (tb) => {
    const seated = tb.seated ?? tb.players ?? tb.players_count ?? 0;
    return el("div", { class: "panel-pixel flex flex-wrap items-center gap-3" },
      el("div", { class: "min-w-0 flex-1" },
        el("strong", { class: "block truncate" }, tb.name),
        el("span", { class: "text-xs text-muted" }, t("poker.table_meta", { seated, max: tb.max_seats, sb: tb.small_blind ?? 1, bb: tb.big_blind ?? 2 }))),
      el("button", { type: "button", class: "btn-pixel btn-pixel--accent", onclick: () => open(tb.id) }, me.role === "teacher" ? t("poker.watch") : t("poker.join_table")));
  };

  function build() {
    const name = el("input", { class: "input-pixel", name: "name", maxlength: 40, required: true, value: t("poker.default_table_name"), "aria-label": t("poker.table_name") });
    const seats = el("select", { class: "input-pixel", "aria-label": t("poker.max_seats") }, ...[2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => el("option", { value: n, selected: n === 6 }, String(n))));
    createBox.replaceChildren(el("h3", { class: "text-base" }, t("poker.create_table")),
      el("label", { class: "grid gap-1 text-sm" }, el("span", {}, t("poker.table_name")), name),
      el("label", { class: "grid gap-1 text-sm" }, el("span", {}, t("poker.max_seats")), seats),
      el("p", { class: "text-xs text-muted" }, t("poker.blinds_fixed")),
      el("button", { class: "btn-pixel btn-pixel--accent", type: "submit" }, t("poker.create")));
    createBox.onsubmit = async (ev) => {
      ev.preventDefault();
      try { const r = await api("POST", "/api/extra/poker/tables", { name: name.value.trim(), max_seats: Number(seats.value) }); await load(); if (r?.id ?? r?.table?.id) open(r.id ?? r.table.id); }
      catch (err) { toast(errorText(err), "error"); }
    };
  }

  const onLocale = () => { createBox.dataset.built = ""; paint(); };
  document.addEventListener("localechange", onLocale);
  load();
  timer = setInterval(() => { if (document.visibilityState === "visible") load(); }, 10000);
  return { destroy() { destroyed = true; clearInterval(timer); document.removeEventListener("localechange", onLocale); host.replaceChildren(); } };
}
