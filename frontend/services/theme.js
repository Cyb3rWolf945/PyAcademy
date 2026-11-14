// Temas: aplica o tema escolhido (perfil > localStorage > omissão) e guarda a escolha.
export const THEMES = ["floresta"];
export const DEFAULT_THEME = "floresta";

// name = tema fixado pelo aluno, ou null para "automático" (rotativo nas fases futuras)
export function applyTheme(name = null) {
  let theme = name;
  if (!theme) {
    try { theme = localStorage.getItem("pyarena.theme"); } catch (_) { /* ignora */ }
  }
  if (!THEMES.includes(theme)) theme = DEFAULT_THEME;
  document.documentElement.dataset.theme = theme;
  try {
    if (name) localStorage.setItem("pyarena.theme", name);
    else localStorage.removeItem("pyarena.theme");
  } catch (_) { /* ignora */ }
}
