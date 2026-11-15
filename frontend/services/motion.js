// Animação com GSAP (vendorizado em vendor/gsap/), carregado só quando há movimento permitido e depois do primeiro pixel.
// API ESTÁVEL (usada também pelo bracket e pelo projetor):
//   motion()                      -> Promise<{gsap, Flip} | null>  (ScrollTrigger só se carrega dentro de revealOnScroll)  (null com prefers-reduced-motion ou se falhar)
//   enter(targets, opts?)         -> Promise<void>   entrada escalonada em steps (opts: y, duration, stagger, delay)
//   countTo(el, to, opts?)        -> Promise<void>   contador animado em el.textContent (opts: from, duration, format(n))
//   flipReorder(items, mutate, o?)-> Promise<void>   Flip: guarda posições, corre mutate() (que reordena o DOM) e anima (opts: duration, flash)
//   podiumReveal({blocks, medals, onDone}) -> Promise<void>   3.º -> 2.º -> 1.º: blocos crescem, medalhas caem; no fim chama onDone
//   pulse(el)                     -> Promise<void>   "pop" curto para destacar algo
//   revealOnScroll(targets)       -> Promise<void>   ScrollTrigger, uma só vez (só landing)
//   scope(root)                   -> {add(fn), revert()}  gsap.context para limpar ao desmontar
// Se motion() devolver null, TODAS as funções aplicam o estado final de imediato (nada fica escondido) e resolvem.
// Nunca HTML em bruto; o GSAP só escreve em element.style (CSSOM), permitido pela CSP.
const FILES = ["gsap.min.js", "Flip.min.js"];
let loading = null;
let stLoading = null;

// A CSP proíbe style.cssText = "..." e setAttribute("style"); o GSAP/Flip usam-nos em elementos auxiliares. Este shim aplica as propriedades uma a uma (CSSOM).
function patchCssText() {
  const d = Object.getOwnPropertyDescriptor(CSSStyleDeclaration.prototype, "cssText");
  if (!d || d.set?.__csp) return;
  const set = function (v) {
    for (let i = this.length - 1; i >= 0; i--) this.removeProperty(this[i]);
    String(v || "").split(";").forEach((decl) => {
      const k = decl.indexOf(":"); if (k < 1) return;
      const val = decl.slice(k + 1).trim(), prio = /!important$/.test(val) ? "important" : "";
      this.setProperty(decl.slice(0, k).trim(), val.replace(/\s*!important$/, ""), prio);
    });
  };
  set.__csp = true;
  Object.defineProperty(CSSStyleDeclaration.prototype, "cssText", { get: d.get, set, configurable: true });
  const attr = Element.prototype.setAttribute; // o Flip também usa setAttribute("style", ...)
  Element.prototype.setAttribute = function (n, v) { return String(n).toLowerCase() === "style" ? void (this.style.cssText = v) : attr.call(this, n, v); };
}

export const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

const loadScript = (src) => new Promise((res, rej) => {
  const s = document.createElement("script");
  s.src = src; s.async = true; s.onload = () => res(); s.onerror = () => rej(new Error(src));
  document.head.append(s);
});

export function motion() {
  if (reducedMotion()) return Promise.resolve(null);
  loading ||= (async () => {
    try {
      patchCssText();
      await loadScript(`/vendor/gsap/${FILES[0]}`);
      await Promise.all(FILES.slice(1).map((f) => loadScript(`/vendor/gsap/${f}`)));
      const { gsap, Flip } = window;
      gsap.registerPlugin(Flip);
      gsap.defaults({ ease: "steps(6)", duration: 0.4 });
      return { gsap, Flip, ScrollTrigger: null };
    } catch (_) { return null; }
  })();
  return loading;
}

const list = (t) => (t instanceof Element ? [t] : Array.from(t || []));
const done = (tween) => new Promise((r) => tween.eventCallback("onComplete", r));
const fmtDefault = (n) => new Intl.NumberFormat(document.documentElement.lang || undefined).format(Math.round(n));

export async function enter(targets, { y = 16, duration = 0.4, stagger = 0.06, delay = 0 } = {}) {
  const els = list(targets); if (!els.length) return;
  const m = await motion(); if (!m) return;
  await done(m.gsap.from(els, { y, autoAlpha: 0, ease: "steps(5)", duration, stagger, delay, snap: { y: 4 }, clearProps: "transform,opacity,visibility" }));
}

export async function countTo(el, to, { from = 0, duration = 0.8, format = fmtDefault } = {}) {
  const m = await motion();
  if (!m || from === to) { el.textContent = format(to); return; }
  const o = { v: from };
  await done(m.gsap.to(o, { v: to, duration, ease: "steps(12)", snap: { v: 1 }, onUpdate: () => { el.textContent = format(o.v); } }));
  el.textContent = format(to);
}

export async function flipReorder(items, mutate, { duration = 0.5 } = {}) {
  const m = await motion();
  if (!m) { mutate(); return; }
  const els = list(typeof items === "function" ? items() : items);
  const state = m.Flip.getState(els);
  mutate();
  const tween = m.Flip.from(state, {
    duration, ease: "steps(6)", absolute: true, nested: false,
    onEnter: (e) => m.gsap.fromTo(e, { autoAlpha: 0, scale: 0.8 }, { autoAlpha: 1, scale: 1, ease: "steps(4)", duration: 0.3 }),
  });
  await new Promise((r) => tween.eventCallback("onComplete", r));
}

export async function podiumReveal({ blocks = [], medals = [], onDone } = {}) {
  const m = await motion();
  if (!m) { onDone?.(); return; }
  const tl = m.gsap.timeline();
  blocks.forEach((b, i) => {
    tl.from(b, { scaleY: 0, transformOrigin: "50% 100%", ease: "steps(8)", duration: 0.5 }, i * 0.55);
    if (medals[i]) tl.from(medals[i], { y: -48, autoAlpha: 0, ease: "steps(6)", duration: 0.4, snap: { y: 4 } }, i * 0.55 + 0.4);
  });
  await new Promise((r) => tl.eventCallback("onComplete", () => { onDone?.(); r(); }));
}

export async function pulse(el) {
  const m = await motion(); if (!m) return;
  await done(m.gsap.fromTo(el, { scale: 1 }, { scale: 1.12, yoyo: true, repeat: 1, duration: 0.18, ease: "steps(3)", clearProps: "transform" }));
}

export async function revealOnScroll(targets) {
  const els = list(targets); const m = await motion(); if (!m || !els.length) return;
  stLoading ||= loadScript("/vendor/gsap/ScrollTrigger.min.js").then(() => { m.gsap.registerPlugin(window.ScrollTrigger); });
  try { await stLoading; } catch (_) { return; }
  els.forEach((e) => m.gsap.from(e, { y: 20, autoAlpha: 0, ease: "steps(5)", duration: 0.45, clearProps: "transform,opacity,visibility", scrollTrigger: { trigger: e, start: "top 90%", once: true } }));
}

export function scope(root) {
  let ctx = null;
  return {
    async add(fn) { const m = await motion(); if (!m) return; ctx ||= m.gsap.context(() => {}, root); ctx.add(fn); },
    revert() { ctx?.revert(); ctx = null; },
  };
}
