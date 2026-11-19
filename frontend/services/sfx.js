// Sons curtos dos avisos, sintetizados no browser (sem ficheiros): a torradeira a saltar, o "ding" e a torrada a voltar para dentro.
// Só tocam depois do primeiro gesto do utilizador (regra dos browsers) e podem ser desligados no perfil.
const KEY = "pyarena.sound", VOLUME = .16, MIN_GAP_MS = 90;
let ctx = null, last = 0;

export function soundEnabled() {
  try { return localStorage.getItem(KEY) !== "off"; } catch (_) { return true; }
}
export function setSoundEnabled(on) {
  try { on ? localStorage.removeItem(KEY) : localStorage.setItem(KEY, "off"); } catch (_) { /* vale só nesta página */ }
}

function unlock() {
  const Ctx = window.AudioContext || window.webkitAudioContext;
  if (!Ctx) return;
  ctx ??= new Ctx();
  if (ctx.state === "suspended") ctx.resume().catch(() => {});
}
addEventListener("pointerdown", unlock, { capture: true, passive: true });
addEventListener("keydown", unlock, { capture: true });

// Uma nota: tipo de onda, frequência inicial e final, início (s), duração (s) e volume relativo
function note(type, from, to, at, dur, vol = 1) {
  const t0 = ctx.currentTime + at, osc = ctx.createOscillator(), gain = ctx.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(from, t0);
  osc.frequency.exponentialRampToValueAtTime(to, t0 + dur);
  gain.gain.setValueAtTime(VOLUME * vol, t0);
  gain.gain.exponentialRampToValueAtTime(.0001, t0 + dur);
  osc.connect(gain).connect(ctx.destination);
  osc.start(t0);
  osc.stop(t0 + dur + .02);
}

function ready() {
  if (!ctx || ctx.state !== "running" || !soundEnabled()) return false;
  const now = performance.now();
  if (now - last < MIN_GAP_MS) return false;
  last = now;
  return true;
}

// A torrada salta (mola) e depois vem o som próprio de cada tipo de aviso
export function playToastIn(kind = "info") {
  if (!ready()) return;
  note("square", 170, 880, 0, .1, .7);
  if (kind === "error") { note("sawtooth", 260, 190, .14, .2, .8); note("sawtooth", 200, 110, .36, .34, .8); }
  else if (kind === "warning") { note("triangle", 988, 980, .14, .12); note("triangle", 988, 980, .3, .16); }
  else if (kind === "success") { note("triangle", 1047, 1040, .13, .1); note("triangle", 1319, 1310, .22, .1); note("triangle", 1568, 1560, .31, .34); }
  else note("triangle", 1568, 1550, .14, .36);
}

// A torrada desce para dentro da torradeira e a alavanca dá um estalido
export function playToastOut() {
  if (!ready()) return;
  note("triangle", 460, 130, 0, .15, .6);
  note("square", 120, 70, .14, .04, .5);
}
