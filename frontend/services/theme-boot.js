// Script minúsculo carregado no <head> (sem inline, por causa da CSP): aplica o tema guardado antes do primeiro pixel.
try {
  const saved = localStorage.getItem("pyarena.theme");
  if (saved && /^[a-z0-9-]+$/.test(saved)) document.documentElement.dataset.theme = saved;
} catch (_) { /* sem localStorage: fica o tema por omissão do HTML */ }
