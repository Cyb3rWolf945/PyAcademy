// Score total do aluno no canto superior direito, usando o mesmo livro de pontos do leaderboard.
import { el } from "./dom.js";
import { api } from "../services/api.js";
import { t } from "../services/i18n.js";

export function mountScoreHud(host, user) {
  if (!host || !user || user.role === "teacher") return { refresh() {} };
  const value = el("span", { class: "font-pixel text-xs text-accent", "aria-live": "polite" }, "0");
  const root = el("span", { class: "chip score-hud", title: t("score.total") },
    el("img", { class: "sprite", src: "/assets/sprites/icons/coin.png", width: 20, height: 20, alt: "" }),
    el("span", { class: "sr-only" }, t("score.total")), value);
  host.replaceChildren(root);
  const label = root.querySelector(".sr-only");
  const paintLabel = () => { root.title = t("score.total"); label.textContent = t("score.total"); };
  const refresh = async () => {
    try {
      const data = await api("GET", "/api/leaderboard/me?period=all");
      value.textContent = new Intl.NumberFormat(user.locale === "en" ? "en-GB" : "pt-PT").format(data.points ?? 0);
    } catch (_) {
      value.textContent = "0";
    }
  };
  document.addEventListener("scorechange", refresh);
  document.addEventListener("localechange", paintLabel);
  refresh();
  return {
    refresh,
    destroy() {
      document.removeEventListener("scorechange", refresh);
      document.removeEventListener("localechange", paintLabel);
    },
  };
}
