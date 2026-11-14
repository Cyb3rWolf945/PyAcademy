// Mostra o nome do modo (duelo, torneio, ranking) com a mensagem "em breve".
import { bootPage } from "../../services/page.js";
import { t } from "../../services/i18n.js";

const MODES = ["duel", "tournament", "ranking"];
await bootPage({ access: "user", nav: true });
const param = new URLSearchParams(location.search).get("m");
const mode = MODES.includes(param) ? param : "duel"; // só valores conhecidos
const title = document.getElementById("mode-title");
const render = () => { title.textContent = t(`nav.${mode}`); };
render();
document.addEventListener("localechange", render);
