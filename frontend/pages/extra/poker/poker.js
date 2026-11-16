// Poker (Extra): arranque. 1.º acesso = ecrã de consentimento (pontos reais de score); depois lista de mesas ou, com
// ?table=ID, a mesa. As fichas vêm do saldo de poker; o servidor é quem manda em tudo (cartas, vez, pontos).
import { bootPage } from "../../../services/page.js";
import { api, errorText } from "../../../services/api.js";
import { t } from "../../../services/i18n.js";
import { el } from "../../../components/dom.js";
import { toast } from "../../../components/toast.js";
import { mountLobby } from "./lobby.js";
import { mountTablePage } from "./table-page.js";

const me = await bootPage({ access: "user", nav: true });

const view = document.getElementById("view");
let current = null;

function show(fn) { current?.destroy?.(); current = fn(); }

async function main() {
  let info = null;
  try { info = await api("GET", "/api/extra/poker/me"); } catch (err) { view.replaceChildren(el("p", { class: "panel-pixel text-danger" }, errorText(err))); return; }
  const consented = info.consent ?? info.consented ?? info.opt_in ?? info.accepted ?? false;
  if (!consented && me.role !== "teacher") { showConsent(); return; }
  route(info);
}

function showConsent() {
  const accept = el("button", { type: "button", class: "btn-pixel btn-pixel--accent btn-pixel--lg" }, t("poker.consent_accept"));
  const back = el("a", { class: "btn-pixel btn-pixel--ghost", href: "/pages/extra/extra.html" }, t("poker.consent_back"));
  const box = el("section", { class: "panel-pixel grid gap-3 max-w-xl mx-auto", "aria-labelledby": "consent-h" },
    el("h2", { id: "consent-h", class: "text-lg" }, t("poker.consent_title")),
    el("p", {}, t("poker.consent_text")),
    el("ul", { class: "grid list-disc gap-1 pl-5 text-sm" }, ...["consent_1", "consent_2", "consent_3", "consent_4"].map((k) => el("li", {}, t(`poker.${k}`)))),
    el("div", { class: "flex flex-wrap gap-2" }, accept, back));
  accept.addEventListener("click", async () => {
    accept.disabled = true;
    try { await api("POST", "/api/extra/poker/consent", {}); main(); }
    catch (err) { toast(errorText(err), "error"); accept.disabled = false; }
  });
  document.addEventListener("localechange", () => showConsent(), { once: true });
  show(() => { view.replaceChildren(box); return { destroy() { view.replaceChildren(); } }; });
}

function route(info) {
  const id = new URLSearchParams(location.search).get("table");
  if (id) show(() => mountTablePage(view, { id, info, me, goLobby: () => { history.pushState(null, "", location.pathname); route(info); } }));
  else show(() => mountLobby(view, { info, me, open: (tid) => { history.pushState(null, "", `?table=${tid}`); route(info); } }));
}
addEventListener("popstate", () => main());

main();
