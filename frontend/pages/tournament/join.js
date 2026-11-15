// Entrar num torneio com o código de 6 letras (também aceita ?code= no URL e entra logo).
import { el } from "../../components/dom.js";
import { icon } from "../../components/icon.js";
import { api, errorText } from "../../services/api.js";
import { t } from "../../services/i18n.js";

export function mountJoin(host, { code = "", error = "", guest = false, onJoined }) {
  const input = el("input", { class: "input-pixel text-center font-pixel text-2xl uppercase tracking-widest", name: "join_code", maxlength: 6, autocapitalize: "characters", autocomplete: "off", required: true, value: code.toUpperCase(), "aria-label": t("tournament.join_code") });
  const name = guest ? el("input", { class: "input-pixel", name: "display_name", maxlength: 40, autocomplete: "nickname", required: true, placeholder: t("tournament.guest_name") }) : null;
  const msg = el("p", { class: "min-h-5 text-sm text-danger", role: "alert" }, error);
  const btn = el("button", { class: "btn-pixel btn-pixel--accent btn-pixel--lg", type: "submit" }, t("tournament.join_button"));
  const form = el("form", { class: "panel-pixel grid gap-3" },
    el("h2", { class: "flex items-center gap-3 text-lg" },
      el("a", { href: "/", "aria-label": "PyArena" }, icon("trophy", "anim-bob")),
      t("tournament.join_title")),
    el("p", { class: "text-sm text-muted" }, t("tournament.join_help")),
    ...(guest ? [name] : []), input, msg, btn);

  async function join() {
    const c = input.value.trim().toUpperCase();
    if (!c) return;
    btn.disabled = true; msg.textContent = "";
    try {
      const path = guest ? "/api/auth/tournament-guest" : "/api/tournaments/join";
      const body = guest ? { join_code: c, display_name: name.value } : { join_code: c };
      const res = await api("POST", path, body, { idempotent: true });
      onJoined(res.tournament_id);
    } catch (err) { msg.textContent = errorText(err); btn.disabled = false; }
  }
  form.addEventListener("submit", (e) => { e.preventDefault(); join(); });
  host.replaceChildren(form);
  if (code.length === 6 && !error && (!guest || name.value.trim())) join();
  return { update() {}, destroy() { host.replaceChildren(); } };
}
