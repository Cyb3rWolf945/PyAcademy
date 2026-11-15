// Seletor de tema compacto: botão com a paleta que abre um popover com 6 amostras + "Aleatório" e "Fixar".
// Usa-se na home e na landing (e pode usar-se no perfil: mountThemeSwitcher(document.querySelector("[data-theme-switch]"))).
import { el } from "./dom.js";
import { t } from "../services/i18n.js";
import { THEMES, currentTheme, pinnedTheme, setTheme, pinTheme, unpinTheme } from "../services/theme.js";

export function mountThemeSwitcher(host) {
  const btn = el("button", { type: "button", class: "btn-pixel secondary !px-2", "aria-haspopup": "dialog", "aria-expanded": "false", "aria-label": t("theme.switch"), "data-i18n-aria": "theme.switch" },
    el("img", { class: "sprite sprite--sm", src: "/assets/sprites/icons/palette.png", width: 24, height: 24, alt: "" }));
  const swatches = THEMES.map((name) => el("button", { type: "button", class: "theme-swatch", "data-name": name, onclick: () => setTheme(name) },
    el("span", { class: "theme-chip", "data-theme": name }), el("span", { "data-i18n": `theme.${name}` }, t(`theme.${name}`))));
  const random = el("button", { type: "button", class: "btn-pixel secondary", "data-i18n": "theme.random", onclick: () => unpinTheme({ reroll: true }).then(refresh) }, t("theme.random"));
  const pin = el("button", { type: "button", class: "btn-pixel", "data-i18n": "theme.pin", onclick: () => pinTheme(currentTheme()).then(refresh) }, t("theme.pin"));
  const pop = el("div", { class: "theme-pop panel-pixel", role: "dialog", "aria-label": t("theme.switch"), "data-i18n-aria": "theme.switch", hidden: true },
    el("div", { class: "theme-grid" }, swatches), el("div", { class: "theme-row" }, random, pin));
  host.classList.add("theme-switcher");
  host.replaceChildren(btn, pop);

  function refresh() {
    const cur = currentTheme(), pinned = pinnedTheme();
    swatches.forEach((s) => s.setAttribute("aria-pressed", String(s.dataset.name === cur)));
    pin.setAttribute("aria-pressed", String(pinned === cur));
    random.setAttribute("aria-pressed", String(!pinned));
  }
  const close = () => { pop.hidden = true; btn.setAttribute("aria-expanded", "false"); };
  btn.addEventListener("click", () => {
    pop.hidden = !pop.hidden;
    btn.setAttribute("aria-expanded", String(!pop.hidden));
    if (!pop.hidden) { refresh(); swatches.find((s) => s.getAttribute("aria-pressed") === "true")?.focus(); }
  });
  document.addEventListener("pointerdown", (e) => { if (!pop.hidden && !host.contains(e.target)) close(); });
  host.addEventListener("keydown", (e) => { if (e.key === "Escape") { close(); btn.focus(); } });
  document.addEventListener("themechange", refresh);
  refresh();
}
