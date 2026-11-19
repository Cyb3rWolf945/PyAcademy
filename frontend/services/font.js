// Tipo de letra: a letra pixel é a de omissão; "clara" e "leitura" são alternativas para quem tem dificuldade em lê-la.
// O theme-boot.js aplica a escolha antes do primeiro pixel; aqui fica a troca em direto e a cópia local.
export const FONTS = ["clara", "leitura"];
const KEY = "pyarena.font";

// applyFont("leitura") aplica e guarda; applyFont(null) volta à letra pixel.
export function applyFont(name) {
  const font = FONTS.includes(name) ? name : null;
  if (font) document.documentElement.dataset.font = font;
  else delete document.documentElement.dataset.font;
  try { font ? localStorage.setItem(KEY, font) : localStorage.removeItem(KEY); } catch (_) { /* sem storage: vale só nesta página */ }
}
