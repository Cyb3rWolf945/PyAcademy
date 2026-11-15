// Navegação principal com ícones pixel: barra inferior no telemóvel, barra lateral em ecrãs largos (lg:).
import { el } from "./dom.js";
import { t } from "../services/i18n.js";

const ITEMS = [
  ["nav.world", "world", "/pages/home/home.html"],
  ["nav.duel", "duel", "/pages/soon/soon.html?m=duel"],
  ["nav.tournament", "tournament", "/pages/tournament/tournament.html"],
  ["nav.ranking", "ranking", "/pages/soon/soon.html?m=ranking"],
  ["nav.profile", "profile", "/pages/profile/profile.html"],
];

export function mountBottomNav(host) {
  const here = location.pathname;
  const nav = el("nav", { class: "nav-pixel", "aria-label": "PyArena" });
  for (const [key, icon, href] of ITEMS) {
    const active = href.split("?")[0] === here;
    nav.append(el("a", { href, "aria-current": active ? "page" : null },
      el("img", { class: "sprite", src: `/assets/sprites/icons/${icon}.png`, width: 28, height: 28, alt: "" }),
      el("span", { "data-i18n": key }, t(key))));
  }
  host.replaceChildren(nav);
}
