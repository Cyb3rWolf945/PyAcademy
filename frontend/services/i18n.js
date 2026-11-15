// Traduções: t("chave", {vars}), idioma inicial (guardado > browser > pt-PT) e troca sem recarregar.
const LOCALES = ["pt-PT", "en"];
let dict = {};
let locale = "pt-PT";

export const getLocale = () => locale;

export function initialLocale() {
  let saved = null;
  try { saved = localStorage.getItem("pyarena.locale"); } catch (_) { /* ignora */ }
  if (LOCALES.includes(saved)) return saved;
  return (navigator.language || "").toLowerCase().startsWith("en") ? "en" : "pt-PT";
}

export function t(key, vars = {}) {
  const s = dict[key] ?? key;
  return s.replace(/\{(\w+)\}/g, (_, k) => (k in vars ? String(vars[k]) : `{${k}}`));
}

// Aplica as traduções aos elementos com data-i18n / data-i18n-placeholder / data-i18n-aria
export function applyI18n(root = document) {
  root.querySelectorAll("[data-i18n]").forEach((e) => { e.textContent = t(e.dataset.i18n); });
  root.querySelectorAll("[data-i18n-placeholder]").forEach((e) => { e.placeholder = t(e.dataset.i18nPlaceholder); });
  root.querySelectorAll("[data-i18n-aria]").forEach((e) => { e.setAttribute("aria-label", t(e.dataset.i18nAria)); });
}

export async function setLocale(next, { save = true } = {}) {
  if (!LOCALES.includes(next)) next = "pt-PT";
  // Ficheiro base + um ficheiro por área (i18n/<area>/<locale>.json, listadas em i18n/areas.json).
  const get = (url) => fetch(url, { credentials: "same-origin" }).then((r) => (r.ok ? r.json() : {})).catch(() => ({}));
  const areas = await get("/i18n/areas.json");
  const parts = await Promise.all([get(`/i18n/${next}.json`), ...(Array.isArray(areas) ? areas : []).map((a) => get(`/i18n/${a}/${next}.json`))]);
  dict = Object.assign({}, ...parts);
  locale = next;
  document.documentElement.lang = next === "en" ? "en" : "pt-PT";
  if (save) { try { localStorage.setItem("pyarena.locale", next); } catch (_) { /* ignora */ } }
  applyI18n();
  document.dispatchEvent(new CustomEvent("localechange", { detail: next }));
}
