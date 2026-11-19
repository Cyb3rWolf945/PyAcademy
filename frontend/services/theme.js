// Temas: sorteio por visita (diferente do último), "fixar" (local + servidor), troca em direto e evento "themechange".
// O theme-boot.js (no <head>) já aplicou o tema antes de desenhar; aqui está a lógica que as páginas e componentes usam.
import { currentUser, savePreferences } from "./auth.js";

export const THEMES = ["campus", "floresta", "masmorra", "oceano", "deserto", "neve", "noite", "tropico"];
export const DEFAULT_THEME = "campus";
const K_PIN = "pyarena.pinned", K_LAST = "pyarena.theme.last", K_VISIT = "pyarena.theme", K_UNSYNC = "pyarena.pin.unsynced";

const get = (store, key) => { try { return store.getItem(key); } catch (_) { return null; } };
const set = (store, key, val) => { try { val == null ? store.removeItem(key) : store.setItem(key, val); } catch (_) { /* ignora */ } };
const valid = (n) => THEMES.includes(n);

export const currentTheme = () => (valid(document.documentElement.dataset.theme) ? document.documentElement.dataset.theme : DEFAULT_THEME);
export const pinnedTheme = () => { const p = get(localStorage, K_PIN); return valid(p) ? p : null; };
export const randomTheme = (exclude = null) => {
  const pool = THEMES.filter((n) => n !== exclude);
  return pool[Math.floor(Math.random() * pool.length)];
};

// Aplica o tema só nesta visita (não fixa). Avisa os componentes (ex.: a ilha 3D) com o evento "themechange".
export function setTheme(name) {
  if (!valid(name)) name = DEFAULT_THEME;
  document.documentElement.dataset.theme = name;
  set(sessionStorage, K_VISIT, name);
  set(localStorage, K_LAST, name);
  const bg = getComputedStyle(document.documentElement).getPropertyValue("--c-bg").trim();
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", bg || "#16241a");
  document.dispatchEvent(new CustomEvent("themechange", { detail: name }));
  return name;
}

// Fixa um tema: local (funciona sem sessão) e, com sessão, no servidor (preferred_theme). Devolve true se o servidor aceitou.
export async function pinTheme(name = currentTheme()) {
  if (!valid(name)) return false;
  set(localStorage, K_PIN, name);
  setTheme(name);
  if (!currentUser()) return true;
  // Se o servidor recusar (ou estiver offline) a cópia local fica marcada como "por sincronizar" e não é apagada pelo applyTheme(null)
  try { await savePreferences({ preferred_theme: name }); set(localStorage, K_UNSYNC, null); return true; } catch (_) { set(localStorage, K_UNSYNC, "1"); return false; }
}

// Volta ao modo aleatório (opcionalmente sorteia logo outro tema).
export async function unpinTheme({ reroll = false } = {}) {
  set(localStorage, K_PIN, null);
  set(localStorage, K_UNSYNC, null);
  if (reroll) setTheme(randomTheme(currentTheme()));
  if (!currentUser()) return true;
  try { await savePreferences({ preferred_theme: null }); return true; } catch (_) { return false; }
}

// Compatível com services/page.js e profile.js:
//   applyTheme()          -> garante um tema válido (o boot já o escolheu)
//   applyTheme("noite")   -> o servidor/perfil diz que está fixado: aplica e guarda a cópia local
//   applyTheme(null)      -> o servidor/perfil diz "automático": tira a cópia local (o tema atual fica até à próxima visita)
export function applyTheme(name) {
  if (name === undefined) { setTheme(currentTheme()); return; }
  if (valid(name)) { set(localStorage, K_PIN, name); setTheme(name); return; }
  if (get(localStorage, K_UNSYNC) && pinnedTheme()) { pinTheme(pinnedTheme()); return; } // volta a tentar sincronizar
  set(localStorage, K_PIN, null);
}
