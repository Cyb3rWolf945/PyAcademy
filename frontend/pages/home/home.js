// Hub do aluno: saudação, nível/XP (provisório), cartões de modo, seletor de tema e a ilha 3D do cabeçalho.
import { bootPage } from "../../services/page.js";
import { t } from "../../services/i18n.js";
import { currentTheme } from "../../services/theme.js";
import { mountThemeSwitcher } from "../../components/theme-switcher.js";
import { toast } from "../../components/toast.js";
import { whenIdle } from "../../scenes/lazy.js";

let lobby = null;
whenIdle(async () => {
  const { mountLobby } = await import("../../scenes/lobby-island.js");
  lobby = await mountLobby(document.getElementById("hero"), { theme: currentTheme() });
});
document.addEventListener("themechange", (e) => lobby?.setTheme(e.detail));

const me = await bootPage({ access: "user", nav: true });
if (me) {
  mountThemeSwitcher(document.querySelector("[data-theme-switch]"));
  const welcome = document.getElementById("welcome");
  const level = document.getElementById("level");
  const xpText = document.getElementById("xp-text");
  const bar = document.getElementById("xp-bar");
  // Provisório: o XP real chega com o modo Mundo. Os valores vêm do utilizador se existirem.
  const lvl = me.level ?? 1, xp = me.xp ?? 0, next = me.xp_next ?? 100;
  bar.style.setProperty("--v", String(Math.min(100, Math.round((xp / next) * 100))));
  bar.setAttribute("aria-valuenow", String(Math.round((xp / next) * 100)));
  const render = () => {
    welcome.textContent = t("home.welcome", { name: me.display_name });
    level.textContent = t("home.level", { n: lvl });
    xpText.textContent = t("home.xp", { xp, next });
    bar.setAttribute("aria-label", t("home.xp", { xp, next }));
  };
  render();
  document.addEventListener("localechange", render);
  if (me.role === "teacher") document.getElementById("admin-link").hidden = false;
  document.querySelectorAll("[data-soon]").forEach((b) => b.addEventListener("click", () => {
    toast(t("mode.soon_toast"), "info");
    b.classList.remove("anim-shake"); void b.offsetWidth; b.classList.add("anim-shake");
  }));
}
