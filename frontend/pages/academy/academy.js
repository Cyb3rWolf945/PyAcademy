// Academia: módulos em sequência vertical a partir de GET /api/academy (progresso, pontos, desbloqueio), com resumo no topo.
// Moldura pixel art, texto limpo. Estados de erro/vazio amigáveis se a API falhar. Animações GSAP via services/motion.js.
import { bootPage } from "../../services/page.js";
import { t } from "../../services/i18n.js";
import { api, errorText } from "../../services/api.js";
import { el } from "../../components/dom.js";
import { mountThemeSwitcher } from "../../components/theme-switcher.js";
import { enter, motion } from "../../services/motion.js";
import { pick } from "../challenge/lib.js";

// estado da API -> estado visual (done | current | open | locked) e ícone
const VIS = { done: "done", in_progress: "current", open: "open", locked: "locked" };
const STATE_ICON = { done: "✅", current: "▶", open: "▶", locked: "🔒" };
const STATE_KEY = { done: "ui.state.done", current: "ui.state.current", open: "ui.state.open", locked: "ui.state.locked" };
const UNLOCK = { teacher: "ui.unlock.teacher", prev_done: "ui.unlock.prev_done", always: "ui.unlock.always" };

const stars = (n) => el("span", { class: "stars", role: "img", "aria-label": `${t("ui.card.difficulty")} ${n}/4` },
  ...[1, 2, 3, 4].map((i) => el("span", { class: i <= n ? "" : "stars__off", "aria-hidden": "true" }, "★")));

function card(m) {
  const soon = m.em_breve || !m.n_secoes;
  const state = soon ? "locked" : VIS[m.estado] || "locked";
  const clickable = !soon && state !== "locked";
  const Tag = clickable ? "a" : "div";
  const attrs = { class: `acad-card acad-card--${state}`, ...(clickable ? { href: `/pages/module/module.html?id=${encodeURIComponent(m.id)}` } : { "aria-disabled": "true" }) };
  const reason = soon ? null : state === "locked" ? t("ui.unlock.prev") : m.motivo && UNLOCK[m.motivo] && m.motivo !== "always" && state === "open" ? t(UNLOCK[m.motivo]) : null;
  const pct = Math.round(m.pct || 0);
  const bar = el("div", { class: "xp-bar", role: "progressbar", "aria-valuemin": "0", "aria-valuemax": "100", "aria-valuenow": String(pct), "aria-label": `${pct}%` });
  bar.style.setProperty("--v", String(pct));
  const num = String(m.id).startsWith("m") ? String(m.id).toUpperCase() : "✚";
  return el(Tag, attrs,
    el("div", { class: "acad-card__top" },
      el("span", { class: "acad-num" }, num),
      el("h3", { class: "acad-card__title" }, pick(m.titulo)),
      el("span", { class: `badge-pixel acad-state acad-state--${state}` }, soon ? t("ui.soon") : [el("span", { "aria-hidden": "true" }, STATE_ICON[state]), ` ${t(STATE_KEY[state])}`])),
    el("div", { class: "acad-card__body" },
      el("img", { class: "sprite acad-card__icon", src: `/assets/sprites/academy/${m.icone || m.id}.png`, width: 64, height: 64, alt: "" }),
      el("p", { class: "acad-card__desc" }, pick(m.descricao))),
    soon ? null : el("div", { class: "acad-meta" }, stars(m.dificuldade || 1), el("span", { class: "chip" }, t("ui.card.sections", { n: m.n_secoes })),
      el("span", { class: "chip" }, el("img", { src: "/assets/sprites/icons/coin.png", width: 20, height: 20, alt: "" }), t("ui.card.points", { got: m.pontos_ganhos ?? 0, max: m.pontos_possiveis ?? 0 }))),
    soon ? null : el("div", { class: "acad-progress" }, bar, el("b", { class: "acad-pct" }, `${pct}%`)),
    el("div", { class: "acad-card__foot" },
      m.peca ? el("span", { class: `acad-seal${state === "done" ? "" : " acad-seal--off"}` },
        el("img", { class: "sprite", src: `/assets/sprites/academy/peca-${m.peca}.png`, width: 32, height: 32, alt: "" }),
        el("span", {}, t("ui.card.badge", { name: t(`ui.piece.${m.peca}`) }))) : null,
      reason ? el("p", { class: "acad-unlock" }, el("span", { "aria-hidden": "true" }, state === "locked" ? "🔒 " : "🎓 "), reason) : null));
}

function render(root, data) {
  const mods = data.modules || [];
  const res = data.resumo || {};
  const sum = (icon, label, value, id) => el("div", { class: "acad-sum" }, el("img", { class: "sprite", src: `/assets/sprites/icons/${icon}.png`, width: 32, height: 32, alt: "" }),
    el("div", {}, el("small", {}, label), el("b", { id }, value)));
  const real = mods.filter((m) => String(m.id).startsWith("m"));
  const header = el("section", { class: "panel-pixel acad-head" },
    el("p", { class: "acad-sub" }, t("ui.academy.subtitle")),
    el("div", { class: "acad-sums" }, sum("shield", t("ui.summary.modules"), `${res.modulos_concluidos ?? 0}/${real.length}`), sum("coin", t("ui.summary.points"), String(res.pontos_academia ?? 0), "sum-pts"),
      sum("lightning", t("ui.summary.streak"), t("ui.summary.streak_val", { n: res.sequencia_dias ?? 0 }))));
  const parts = [header];
  const mis = data.missao;
  if (mis && (mis.modulo || mis.module)) {
    const mid = mis.modulo || mis.module;
    const target = mods.find((m) => m.id === mid);
    parts.push(el("section", { class: "acad-mission", "aria-label": t("ui.mission.title") },
      el("img", { class: "sprite sprite--lg anim-bob", src: "/assets/sprites/icons/scroll.png", width: 64, height: 64, alt: "" }),
      el("div", { class: "acad-mission__text" }, el("b", {}, t("ui.mission.title")), el("p", {}, t("ui.mission.text", { module: target ? pick(target.titulo) : mid }))),
      el("a", { class: "btn-pixel btn-pixel--accent", href: `/pages/module/module.html?id=${encodeURIComponent(mid)}` }, t("ui.mission.cta"))));
  }
  const fill = el("span", { class: "acad-fill", "aria-hidden": "true" });
  const lastActive = mods.reduce((i, m, k) => (m.estado === "locked" || m.em_breve || !m.n_secoes ? i : k), 0);
  fill.style.setProperty("--p", String((lastActive + 0.5) / Math.max(1, mods.length)));
  const items = mods.map((m) => {
    const soon = m.em_breve || !m.n_secoes;
    const st = soon ? "locked" : VIS[m.estado] || "locked";
    return el("li", { class: `acad-node acad-node--${st}` }, el("span", { class: "acad-dot", "aria-hidden": "true" }, STATE_ICON[st]), card(m));
  });
  parts.push(el("ol", { class: "acad-track" }, fill, items));
  root.replaceChildren(...parts);
  return { cards: items, fill };
}

function showError(root, err, retry) {
  root.replaceChildren(el("section", { class: "panel-pixel empty-state", role: "alert" },
    el("img", { class: "sprite sprite--lg anim-bob", src: "/assets/sprites/icons/chest.png", width: 64, height: 64, alt: "" }),
    el("p", {}, err?.status === 404 ? t("ui.err.not_ready") : errorText(err)),
    el("button", { type: "button", class: "btn-pixel", onclick: retry }, t("ui.err.retry"))));
}

const me = await bootPage({ access: "user", nav: true });
if (me) {
  mountThemeSwitcher(document.querySelector("[data-theme-switch]"));
  const root = document.getElementById("academy");
  let data = null;
  const load = async () => {
    root.replaceChildren(el("p", { class: "text-center text-muted", role: "status" }, t("ui.loading")));
    try {
      data = await api("GET", "/api/academy");
      const parts = render(root, data);
      const m = await motion();
      if (m) { m.gsap.from(parts.fill, { scaleY: 0, transformOrigin: "50% 0%", duration: 0.9, ease: "steps(10)" }); enter(parts.cards, { y: 20, stagger: 0.07 }); }
    } catch (err) { data = null; showError(root, err, load); }
  };
  await load();
  document.addEventListener("localechange", () => { if (data) render(root, data); });
}
