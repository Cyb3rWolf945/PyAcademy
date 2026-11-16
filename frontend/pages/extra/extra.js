// Hub "Extra": cartões do Poker e do Bit a Bit com o saldo/progresso do aluno, regras curtas e definições da turma (professor).
// Os dados vêm de /api/extra/*; enquanto um endpoint não existir (404) o cartão mostra "ainda não disponível" e continua utilizável.
import { bootPage } from "../../services/page.js";
import { t } from "../../services/i18n.js";
import { api, errorText } from "../../services/api.js";
import { el } from "../../components/dom.js";
import { toast } from "../../components/toast.js";
import { mountThemeSwitcher } from "../../components/theme-switcher.js";
import { fmtPoints } from "../challenge/lib.js";

const first = (o, keys, d = null) => { for (const k of keys) if (o && o[k] != null) return o[k]; return d; };
const safe = async (path) => { try { return await api("GET", path); } catch (err) { return { __err: err }; } };

function gameCard({ tone, icon, title, tag, desc, href, stats }) {
  return el("a", { class: "extra-card", "data-tone": tone, href },
    el("div", { class: "extra-card__top" }, el("img", { class: "sprite extra-card__icon", src: `/assets/sprites/icons/${icon}.png`, width: 64, height: 64, alt: "" }),
      el("div", {}, el("h2", { class: "extra-card__title" }, title), el("p", { class: "extra-card__tag" }, tag))),
    el("p", { class: "extra-card__desc" }, desc),
    el("div", { class: "extra-stats" }, stats),
    el("span", { class: "btn-pixel btn-pixel--accent extra-card__cta" }, t("hub.play")));
}
const chip = (label, value) => el("span", { class: "chip" }, label ? el("small", {}, label) : null, el("b", {}, value));

function pokerStats(d) {
  if (!d || d.__err) return [el("span", { class: "extra-note" }, t("hub.unavailable"))];
  if (first(d, ["enabled", "poker_enabled"]) === false) return [el("span", { class: "extra-note" }, t("hub.poker.off"))];
  const bal = first(d, ["balance", "available", "saldo", "available_balance"], 0);
  const loss = first(d, ["loss_today", "today_loss", "perda_hoje"], 0), lim = first(d, ["loss_limit", "daily_loss_limit", "limite"], 100);
  const kids = [chip(t("hub.poker.balance"), `${fmtPoints(bal)} pts`), el("span", { class: "extra-note" }, t("hub.poker.loss", { loss: fmtPoints(loss), limit: fmtPoints(lim) }))];
  if (first(d, ["consented", "accepted", "consent"]) === false) kids.push(el("span", { class: "extra-note" }, t("hub.poker.consent")));
  return kids;
}
function bitStats(d) {
  if (!d || d.__err) return [el("span", { class: "extra-note" }, t("hub.unavailable"))];
  const x = first(d, ["today_points", "points_today", "today"], 0), max = first(d, ["today_max", "max_today", "daily_cap"], 50), best = first(d, ["best", "record"], 0);
  return [chip(null, t("hub.bit.today", { x: fmtPoints(x), max: fmtPoints(max) })), chip(null, t("hub.bit.best", { n: fmtPoints(best) }))];
}

// Painel do professor: renderiza controlos para os campos que o servidor devolve e envia só o que mudou (PATCH)
const LIMIT_KEYS = { loss_limit: "hub.teacher.loss_limit", daily_loss_limit: "hub.teacher.loss_limit", buy_in_min: "hub.teacher.buy_in_min", buy_in_max: "hub.teacher.buy_in_max" };
function teacherPanel(settings) {
  const form = el("form", { class: "panel-pixel grid gap-3 extra-teacher" }, el("h2", {}, t("hub.teacher.title")));
  const inputs = {};
  if ("poker_enabled" in settings) {
    inputs.poker_enabled = el("input", { type: "checkbox", checked: !!settings.poker_enabled });
    form.append(el("label", { class: "extra-check" }, inputs.poker_enabled, el("span", {}, t("hub.teacher.poker_enabled"))));
  }
  if ("poker_source" in settings) {
    inputs.poker_source = el("select", { class: "input-pixel" }, el("option", { value: "torneios" }, t("hub.teacher.source_torneios")), el("option", { value: "todos" }, t("hub.teacher.source_todos")));
    inputs.poker_source.value = settings.poker_source;
    form.append(el("label", { class: "grid gap-1" }, el("span", {}, t("hub.teacher.source")), inputs.poker_source));
  }
  for (const [k, key] of Object.entries(LIMIT_KEYS)) if (typeof settings[k] === "number") {
    inputs[k] = el("input", { class: "input-pixel", type: "number", min: "0", step: "1", value: String(settings[k]) });
    form.append(el("label", { class: "grid gap-1" }, el("span", {}, t(key)), inputs[k]));
  }
  if ("students_can_create_tables" in settings) {
    inputs.students_can_create_tables = el("input", { type: "checkbox", checked: !!settings.students_can_create_tables });
    form.append(el("label", { class: "extra-check" }, inputs.students_can_create_tables, el("span", {}, t("hub.teacher.students_create"))));
  }
  form.append(el("button", { type: "submit", class: "btn-pixel" }, t("hub.teacher.save")));
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const body = {};
    for (const [k, inp] of Object.entries(inputs)) body[k] = inp.type === "checkbox" ? inp.checked : inp.type === "number" ? Number(inp.value) : inp.value;
    try { await api("PATCH", "/api/extra/settings", body); toast(t("hub.teacher.saved"), "success"); } catch (err) { toast(errorText(err), "error"); }
  });
  return Object.keys(inputs).length ? form : null;
}

const me = await bootPage({ access: "user", nav: true });
if (me) {
  mountThemeSwitcher(document.querySelector("[data-theme-switch]"));
  const root = document.getElementById("extra");
  const render = async () => {
    const [poker, bit, settings] = await Promise.all([safe("/api/extra/poker/me"), safe("/api/extra/bitabit/me"), me.role === "teacher" ? safe("/api/extra/settings") : null]);
    const cards = el("div", { class: "extra-grid" },
      gameCard({ tone: "1", icon: "poker", title: t("hub.poker.title"), tag: t("hub.poker.tag"), desc: t("hub.poker.desc"), href: "/pages/extra/poker/poker.html", stats: pokerStats(poker) }),
      gameCard({ tone: "4", icon: "bitabit", title: t("hub.bit.title"), tag: t("hub.bit.tag"), desc: t("hub.bit.desc"), href: "/pages/extra/bitabit/bitabit.html", stats: bitStats(bit) }));
    const rules = el("section", { class: "panel-pixel" }, el("h2", {}, t("hub.rules.title")), el("ul", { class: "extra-rules clean" }, [1, 2, 3, 4].map((n) => el("li", {}, t(`hub.rules.${n}`)))));
    const parts = [el("p", { class: "extra-sub" }, t("hub.subtitle")), cards, rules];
    if (settings && !settings.__err) { const tp = teacherPanel(settings); if (tp) parts.push(tp); }
    root.replaceChildren(...parts);
  };
  await render();
  document.addEventListener("localechange", render);
}
