// Sirene de polícia sintetizada no browser (Web Audio): sem ficheiros de som. O áudio fica agendado de uma só vez,
// por isso continua a tocar mesmo com a janela escondida, onde os temporizadores do browser abrandam.
const SIREN_S = 10, LOW = 620, HIGH = 1480, SWEEP_S = 1.1;
let ctx = null, voice = null;

// Os browsers só deixam tocar som depois de um gesto do utilizador: chamar isto no primeiro toque ou tecla.
export function unlockSiren() {
  const Ctx = window.AudioContext || window.webkitAudioContext;
  if (!Ctx) return;
  ctx ??= new Ctx();
  if (ctx.state === "suspended") ctx.resume().catch(() => {});
}

export function stopSiren() {
  if (!voice) return;
  for (const osc of voice) { try { osc.stop(); } catch (_) { /* já parou */ } }
  voice = null;
}

export function playSiren() {
  unlockSiren();
  if (!ctx) return;
  stopSiren();
  const start = ctx.currentTime + .02, end = start + SIREN_S;
  const master = ctx.createGain();
  master.gain.setValueAtTime(1, start);
  master.gain.setValueAtTime(1, end - .08);
  master.gain.linearRampToValueAtTime(0, end);
  // O compressor mantém o som no máximo sem distorcer ao somar as duas vozes
  const comp = ctx.createDynamicsCompressor();
  comp.threshold.value = -18; comp.ratio.value = 12; comp.attack.value = .002; comp.release.value = .1;
  master.connect(comp).connect(ctx.destination);
  voice = [["square", 1], ["sawtooth", 1.012]].map(([type, ratio]) => {
    const osc = ctx.createOscillator();
    osc.type = type;
    osc.frequency.setValueAtTime(LOW * ratio, start);
    for (let at = start, up = true; at < end; at += SWEEP_S, up = !up) osc.frequency.exponentialRampToValueAtTime((up ? HIGH : LOW) * ratio, at + SWEEP_S);
    osc.connect(master);
    osc.start(start);
    osc.stop(end);
    return osc;
  });
}
