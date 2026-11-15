// Sons curtos em Web Audio para as celebrações pixel art, sem ficheiros externos.
let context = null;

function audioContext() {
  if (!context) {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return null;
    context = new AudioContext();
  }
  return context;
}

export function playVictory() {
  const ctx = audioContext();
  if (!ctx) return;
  if (ctx.state === "suspended") ctx.resume().catch(() => {});
  const now = ctx.currentTime;
  const notes = [523.25, 659.25, 783.99, 1046.5];
  const gain = ctx.createGain();
  gain.gain.setValueAtTime(0.0001, now);
  gain.connect(ctx.destination);
  notes.forEach((frequency, index) => {
    const oscillator = ctx.createOscillator();
    const start = now + index * 0.09;
    oscillator.type = "square";
    oscillator.frequency.setValueAtTime(frequency, start);
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(0.08, start + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.16);
    oscillator.connect(gain);
    oscillator.start(start);
    oscillator.stop(start + 0.17);
  });
  setTimeout(() => gain.disconnect(), 700);
}
