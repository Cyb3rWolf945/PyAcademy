// Script minúsculo no <head> (externo, por causa da CSP): escolhe e aplica o tema ANTES do primeiro pixel, sem "flash".
// Ordem: tema fixado (pyarena.pinned) > tema desta visita (sessionStorage) > sorteio diferente do último.
try {
  const T = ["floresta", "masmorra", "oceano", "deserto", "neve", "noite"], L = localStorage, S = sessionStorage;
  const pinned = L.getItem("pyarena.pinned"), cur = S.getItem("pyarena.theme");
  let n = T.includes(pinned) ? pinned : T.includes(cur) ? cur : null;
  if (!n) { const c = T.filter((x) => x !== L.getItem("pyarena.theme.last")); n = c[Math.floor(Math.random() * c.length)]; }
  S.setItem("pyarena.theme", n); L.setItem("pyarena.theme.last", n);
  document.documentElement.dataset.theme = n;
} catch (_) { /* sem storage: fica o tema por omissão do HTML */ }
