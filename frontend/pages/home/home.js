// Hub do aluno (placeholder): mostra a saudação e, se for professor, o atalho para o painel.
import { bootPage } from "../../services/page.js";
import { t } from "../../services/i18n.js";

const me = await bootPage({ access: "user", nav: true });
if (me) {
  const welcome = document.getElementById("welcome");
  const render = () => { welcome.textContent = t("home.welcome", { name: me.display_name }); };
  render();
  document.addEventListener("localechange", render);
  if (me.role === "teacher") document.getElementById("admin-link").hidden = false;
}
