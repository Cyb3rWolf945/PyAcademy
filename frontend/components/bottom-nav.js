// Navegação principal: barra inferior no telemóvel, barra lateral em ecrãs largos (lg:).
import { el } from "./dom.js";
import { t } from "../services/i18n.js";

const ITEMS = [
  ["nav.world", "🗺️", "/pages/home/home.html"],
  ["nav.duel", "⚔️", "/pages/soon/soon.html?m=duel"],
  ["nav.tournament", "🏆", "/pages/soon/soon.html?m=tournament"],
  ["nav.ranking", "📊", "/pages/soon/soon.html?m=ranking"],
  ["nav.profile", "👤", "/pages/profile/profile.html"],
];

export function mountBottomNav(host) {
  const here = location.pathname;
  const nav = el("nav", {
    class: "fixed inset-x-0 bottom-0 z-40 flex bg-surface pb-[env(safe-area-inset-bottom)] lg:inset-y-0 lg:right-auto lg:w-56 lg:flex-col lg:justify-start lg:gap-1 lg:p-3",
  });
  for (const [key, icon, href] of ITEMS) {
    const active = href.split("?")[0] === here;
    const a = el("a", {
      href, "aria-current": active ? "page" : null,
      class: `flex min-h-[56px] flex-1 flex-col items-center justify-center gap-1 text-xs lg:min-h-[44px] lg:flex-none lg:flex-row lg:justify-start lg:gap-3 lg:px-3 lg:text-sm ${active ? "text-accent" : "text-muted"}`,
    }, el("span", { "aria-hidden": "true" }, icon), el("span", { "data-i18n": key }, t(key)));
    nav.append(a);
  }
  host.replaceChildren(nav);
}
