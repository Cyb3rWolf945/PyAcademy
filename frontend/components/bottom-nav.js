// Navegação principal com ícones pixel: barra inferior no telemóvel, barra lateral em ecrãs largos (lg:).
import { el } from "./dom.js";
import { t } from "../services/i18n.js";

const ITEMS = [
  ["nav.academy", "m1", "/pages/academy/academy.html", "academy"],
  ["nav.duel", "duel", "/pages/soon/soon.html?m=duel"],
  ["nav.tournament", "tournament", "/pages/tournament/tournament.html"],
  ["nav.ranking", "ranking", "/pages/soon/soon.html?m=ranking"],
  ["nav.extra", "extra", "/pages/extra/extra.html"],
  ["nav.profile", "profile", "/pages/profile/profile.html"],
];

export function mountBottomNav(host) {
  const here = location.pathname;
  const nav = el("nav", { class: "nav-pixel", "aria-label": "PyArena" });
  // Botão de recolher/expandir (só aparece em ecrãs largos). O estado fica em localStorage e na classe nav-collapsed do <html>.
  const root = document.documentElement;
  const toggle = el("button", { type: "button", class: "nav-toggle", "aria-expanded": "true", "aria-controls": "main-nav" },
    el("span", { class: "nav-toggle-label", "data-i18n": "nav.collapse" }, t("nav.collapse")), el("span", { class: "chev", "aria-hidden": "true" }, "«"));
  const paint = () => {
    const collapsed = root.classList.contains("nav-collapsed");
    toggle.setAttribute("aria-expanded", String(!collapsed));
    const key = collapsed ? "nav.expand" : "nav.collapse";
    toggle.setAttribute("aria-label", t(key)); toggle.title = t(key);
    toggle.firstChild.dataset.i18n = key; toggle.firstChild.textContent = t(key);
    toggle.lastChild.textContent = collapsed ? "»" : "«";
  };
  toggle.addEventListener("click", () => {
    const collapsed = root.classList.toggle("nav-collapsed");
    try { collapsed ? localStorage.setItem("pyarena.nav", "1") : localStorage.removeItem("pyarena.nav"); } catch (_) { /* ignora */ }
    paint();
  });
  document.addEventListener("localechange", paint);
  nav.id = "main-nav";
  nav.append(toggle);
  for (const [key, icon, href, dir] of ITEMS) {
    const active = href.split("?")[0] === here || (href === "/pages/extra/extra.html" && here.startsWith("/pages/extra/")) || (dir === "academy" && here.startsWith("/pages/module/"));
    nav.append(el("a", { href, "aria-current": active ? "page" : null, title: t(key), "data-title-key": key },
      el("img", { class: "sprite", src: dir ? `/assets/sprites/academy/${icon}.png` : `/assets/sprites/icons/${icon}.png`, width: 28, height: 28, alt: "" }),
      el("span", { "data-i18n": key }, t(key))));
  }
  host.replaceChildren(nav);
  paint();
  document.addEventListener("localechange", () => nav.querySelectorAll("a[data-title-key]").forEach((a) => { a.title = t(a.dataset.titleKey); }));
}
