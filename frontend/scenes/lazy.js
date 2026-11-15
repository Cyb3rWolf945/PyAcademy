// Carrega uma cena 3D só depois do primeiro pixel (evento load + tempo livre do browser), para o LCP não esperar pelo three.js.
export function whenIdle(fn) {
  const run = () => (window.requestIdleCallback ? requestIdleCallback(fn, { timeout: 2500 }) : setTimeout(fn, 300));
  if (document.readyState === "complete") run(); else addEventListener("load", run, { once: true });
}
