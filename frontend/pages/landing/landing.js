// Ecrã de entrada: login, registo com código de turma, atalho de torneio e a ilha 3D (carregada depois do primeiro pixel).
import { bootPage } from "../../services/page.js";
import { login, join, homeFor } from "../../services/auth.js";
import { errorText } from "../../services/api.js";
import { currentTheme } from "../../services/theme.js";
import { mountThemeSwitcher } from "../../components/theme-switcher.js";
import { whenIdle } from "../../scenes/lazy.js";

// A cena 3D só arranca com a página já desenhada; o import() não bloqueia nada.
let lobby = null;
// Sem sessão, os edifícios do campus que precisam de conta levam ao formulário de entrada; o torneio abre direto.
function openHotspot(h) {
  if (h.id === "tournament") { location.assign(h.url); return; }
  document.querySelector("#login-form input[name=username]")?.focus();
  import("../../components/toast.js").then(({ toast }) => import("../../services/i18n.js").then(({ t }) => toast(t("campus.login_first"), "info")));
}
whenIdle(async () => {
  const { mountHero } = await import("../../scenes/hero.js");
  lobby = await mountHero(document.getElementById("hero"), { theme: currentTheme(), onHotspot: openHotspot });
});
// Leaderboard: carrega depois do herói, sem atrasar o primeiro pixel
whenIdle(async () => {
  const { mountLeaderboard } = await import("../../components/leaderboard-public.js");
  mountLeaderboard(document.getElementById("leaderboard"), { nav: false });
});
document.addEventListener("themechange", (e) => lobby?.setTheme(e.detail));

await bootPage({ access: "public" });
mountThemeSwitcher(document.querySelector("[data-theme-switch]"));

function wire(form, action) {
  const errorBox = form.querySelector("[data-error]");
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const btn = form.querySelector("button[type=submit]");
    btn.disabled = true;
    errorBox.textContent = "";
    try {
      const user = await action(Object.fromEntries(new FormData(form)));
      location.assign(homeFor(user));
    } catch (err) {
      errorBox.textContent = errorText(err); // textContent: nunca HTML em bruto
      errorBox.classList.add("anim-shake");
      setTimeout(() => errorBox.classList.remove("anim-shake"), 500);
      btn.disabled = false;
    }
  });
}

wire(document.getElementById("login-form"), (v) => login(v.username, v.password));
wire(document.getElementById("join-form"), (v) => join(v));
