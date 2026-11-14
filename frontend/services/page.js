// Arranque comum das páginas: tema, idioma, utilizador (com guarda de acesso) e componentes de navegação.
import { applyTheme } from "./theme.js";
import { getLocale, initialLocale, setLocale } from "./i18n.js";
import { loadMe, homeFor } from "./auth.js";
import { mountLangSwitch } from "../components/lang-switch.js";
import { mountBottomNav } from "../components/bottom-nav.js";

// opts.access: "public" | "user" | "teacher" | "password" (ecrã de mudança obrigatória)
export async function bootPage({ access = "user", nav = false } = {}) {
  applyTheme();
  await setLocale(initialLocale(), { save: false });
  const me = await loadMe();
  if (access === "public") {
    if (me) { location.replace(homeFor(me)); return null; }
  } else {
    if (!me) { location.replace("/"); return null; }
    if (access === "password") {
      if (!me.must_change_password) { location.replace(homeFor(me)); return null; }
    } else if (me.must_change_password) { location.replace(homeFor(me)); return null; }
    if (access === "teacher" && me.role !== "teacher") { location.replace(homeFor(me)); return null; }
    applyTheme(me.preferred_theme);
    if (me.locale !== getLocale()) await setLocale(me.locale);
  }
  document.querySelectorAll("[data-lang-switch]").forEach(mountLangSwitch);
  if (nav) document.querySelectorAll("[data-bottom-nav]").forEach(mountBottomNav);
  return me;
}
