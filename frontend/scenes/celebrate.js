// Celebração em ecrã inteiro: partículas quadradas (confete e fogo-de-artifício) em canvas 2D de baixa resolução.
// celebrate(el, { kind: "solve" | "boss" | "podium" }) -> Promise que resolve quando a camada se remove (2 a 3 s).
// Não precisa do three.js. Com prefers-reduced-motion mostra só um quadro estático durante ~1,2 s.
import { prefersReducedMotion, cssColor } from "./scene-base.js";

const DURATION = { solve: 1900, boss: 3000, podium: 3200 };
const PX = 4; // cada "pixel" da celebração tem 4 px de ecrã

export function celebrate(el, { kind = "solve" } = {}) {
  return new Promise((resolve) => {
    const layer = document.createElement("canvas");
    layer.className = "celebrate-layer";
    layer.setAttribute("aria-hidden", "true");
    (el || document.body).append(layer);
    const W = Math.ceil(innerWidth / PX), H = Math.ceil(innerHeight / PX);
    layer.width = W; layer.height = H;
    const ctx = layer.getContext("2d");
    const pal = ["--c-accent", "--c-accent-2", "--c-gold", "--c-team-0", "--c-team-1", "--c-team-3", "--c-team-4", "--c-team-5", "--c-team-7"].map(cssColor);
    const rnd = (a, b) => a + Math.random() * (b - a), pick = () => pal[Math.floor(Math.random() * pal.length)];
    const parts = [];
    const burst = (cx, cy, n, speed) => { for (let i = 0; i < n; i++) { const a = (i / n) * 6.283 + rnd(0, .3), s = rnd(speed * .5, speed); parts.push({ x: cx, y: cy, vx: Math.cos(a) * s, vy: Math.sin(a) * s, g: 22, life: rnd(.9, 1.5), c: pick(), s: 2 }); } };
    const confetti = (n, fromTop) => { for (let i = 0; i < n; i++) parts.push(fromTop
      ? { x: rnd(0, W), y: rnd(-H * .3, 0), vx: rnd(-6, 6), vy: rnd(14, 30), g: 4, life: rnd(1.6, 2.8), c: pick(), s: Math.random() < .3 ? 3 : 2 }
      : { x: W / 2 + rnd(-6, 6), y: H * .75, vx: rnd(-34, 34), vy: rnd(-70, -35), g: 70, life: rnd(1, 1.7), c: pick(), s: Math.random() < .3 ? 3 : 2 }); };
    let done = false;
    const end = () => { if (done) return; done = true; layer.remove(); resolve(); };

    if (prefersReducedMotion()) { // quadro estático
      confetti(60, true); parts.forEach((p) => { p.y = rnd(0, H); ctx.fillStyle = p.c; ctx.fillRect(p.x | 0, p.y | 0, p.s, p.s); });
      setTimeout(end, 1200);
      return;
    }
    const total = DURATION[kind] ?? DURATION.solve;
    setTimeout(end, total + 500); // rede de segurança: separador escondido não pára o rAF a tempo
    const t0 = performance.now(); let last = t0, nextBurst = 0, raf = 0;
    if (kind === "solve") confetti(70, false);
    function frame(now) {
      const dt = Math.min(0.05, (now - last) / 1000); last = now;
      const el_ = now - t0;
      if (kind !== "solve" && el_ < total - 900 && el_ >= nextBurst) {
        burst(rnd(W * .15, W * .85), rnd(H * .15, H * .5), 28, 45);
        if (kind === "podium") confetti(24, true);
        nextBurst = el_ + 420;
      }
      ctx.clearRect(0, 0, W, H);
      for (const p of parts) {
        p.life -= dt; if (p.life <= 0) continue;
        p.vy += p.g * dt; p.x += p.vx * dt; p.y += p.vy * dt;
        ctx.globalAlpha = p.life < .3 ? Math.floor(p.life / .1) / 3 : 1; // desvanece em degraus
        ctx.fillStyle = p.c; ctx.fillRect(p.x | 0, p.y | 0, p.s, p.s);
      }
      ctx.globalAlpha = 1;
      if (el_ >= total) end(); else raf = requestAnimationFrame(frame);
    }
    raf = requestAnimationFrame(frame);
    document.addEventListener("visibilitychange", () => { if (document.hidden) { cancelAnimationFrame(raf); end(); } }, { once: true });
  });
}
