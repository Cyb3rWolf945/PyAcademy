// Script minúsculo no <head> (externo, por causa da CSP): escolhe e aplica o tema ANTES do primeiro pixel, sem "flash".
// Ordem: tema fixado (pyarena.pinned) > tema desta visita (sessionStorage) > campus por omissão.
try {
  const T = ["campus", "floresta", "masmorra", "oceano", "deserto", "neve", "noite"], L = localStorage, S = sessionStorage;
  const pinned = L.getItem("pyarena.pinned"), cur = S.getItem("pyarena.theme");
  let n = T.includes(pinned) ? pinned : T.includes(cur) ? cur : null;
  if (!n) n = "campus"; // por omissão: Campus IPT (o sorteio só acontece quando se carrega em "Aleatório")
  S.setItem("pyarena.theme", n); L.setItem("pyarena.theme.last", n);
  document.documentElement.dataset.theme = n;
  if (L.getItem("pyarena.nav") === "1") document.documentElement.classList.add("nav-collapsed"); // menu lateral recolhido
} catch (_) { /* sem storage: fica o tema por omissão do HTML */ }
