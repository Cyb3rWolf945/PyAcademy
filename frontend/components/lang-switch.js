// Seletor 🇵🇹/🇬🇧 em botões pixel: troca o idioma sem recarregar e, se houver sessão, guarda-o no perfil.
import { el } from "./dom.js";
import { api } from "../services/api.js";
import { getLocale, setLocale } from "../services/i18n.js";
import { currentUser } from "../services/auth.js";

const OPTIONS = [["pt-PT", "🇵🇹", "PT"], ["en", "🇬🇧", "EN"]];

export function mountLangSwitch(host) {
  const buttons = OPTIONS.map(([code, flag, label]) =>
    el("button", {
      type: "button", class: "btn-pixel secondary !px-2", "data-code": code, "aria-label": label,
      onclick: async () => {
        await setLocale(code);
        if (currentUser()) api("PATCH", "/api/me/preferences", { locale: code }).catch(() => {});
      },
    }, el("span", { "aria-hidden": "true" }, flag), el("span", { class: "hidden sm:inline" }, label)),
  );
  const refresh = () => buttons.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.code === getLocale())));
  host.replaceChildren(...buttons);
  refresh();
  document.addEventListener("localechange", refresh);
}
