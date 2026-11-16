// Chiptune em Web Audio para o Bit a Bit: efeitos curtos e um baixo em ciclo. Desligado por omissão; sem ficheiros externos.
let ctx = null;
let loop = 0;
let step = 0;

function audio() {
  if (!ctx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    ctx = new AC();
  }
  if (ctx.state === "suspended") ctx.resume().catch(() => {});
  return ctx;
}

function blip(freq, start, dur, { type = "square", vol = 0.05, to = null } = {}) {
  const c = audio(); if (!c) return;
  const o = c.createOscillator(), g = c.createGain(), at = c.currentTime + start;
  o.type = type;
  o.frequency.setValueAtTime(freq, at);
  if (to) o.frequency.linearRampToValueAtTime(to, at + dur);
  g.gain.setValueAtTime(0.0001, at);
  g.gain.exponentialRampToValueAtTime(vol, at + 0.01);
  g.gain.exponentialRampToValueAtTime(0.0001, at + dur);
  o.connect(g).connect(c.destination);
  o.start(at); o.stop(at + dur + 0.02);
}

const SFX = {
  toggle: () => blip(660, 0, 0.05, { type: "square", vol: 0.03 }),
  key: () => blip(440, 0, 0.04, { type: "triangle", vol: 0.03 }),
  clear: () => { blip(523, 0, 0.08); blip(784, 0.08, 0.14); },
  wrong: () => blip(180, 0, 0.22, { type: "sawtooth", vol: 0.05, to: 110 }),
  level: () => [523, 659, 784, 1047].forEach((f, i) => blip(f, i * 0.08, 0.12)),
  over: () => [392, 330, 262, 196].forEach((f, i) => blip(f, i * 0.16, 0.2, { type: "triangle", vol: 0.06 })),
};

export function createAudio() {
  let on = false;
  const bass = [110, 110, 165, 110, 147, 147, 196, 147];
  const music = () => { blip(bass[step++ % bass.length], 0, 0.16, { type: "triangle", vol: 0.035 }); if (step % 2 === 0) blip(bass[step % bass.length] * 4, 0.02, 0.05, { vol: 0.015 }); };
  return {
    get on() { return on; },
    set(v) { on = v; if (!v) this.stopMusic(); },
    play(name) { if (on) SFX[name]?.(); },
    startMusic() { if (on && !loop) loop = setInterval(music, 240); },
    stopMusic() { clearInterval(loop); loop = 0; },
  };
}
