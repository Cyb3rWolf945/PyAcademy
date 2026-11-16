// Gerador determinístico do Bit a Bit: PRNG mulberry32 + sequência de linhas a partir da seed do servidor.
// TEM de dar exatamente o mesmo resultado que backend/app/services/bitabit.py (especificação no topo desse ficheiro
// e vetores partilhados em backend/tests/fixtures/bitabit_vectors.json; verificação: check_vectors.mjs).
//   Linha k: 2 chamadas ao PRNG (u1 -> tipo: u1 < 0.5 ? "b2d" : "d2b"; u2 -> valor = 1 + floor(u2 * (2^bits - 1))).
//   Nível = floor(k / 10) + 1; bits = 4 (nível 1), 6 (nível 2), 8 (nível 3+); no máximo 80 linhas.
//   Pontos de uma linha certa: (bits*5 + max(0, 20 - floor(t_ms/300))) * nível; pontos do dia = floor(pontuação / 100).

export function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export const ROWS_PER_LEVEL = 10;
export const MAX_ROWS = 80;
export const MIN_MS_PER_ROW = 300;
// parâmetros só do cliente (ritmo do jogo): linhas visíveis e velocidade de subida (linhas por segundo)
export const DEFAULTS = { rows_per_level: ROWS_PER_LEVEL, max_rows: MAX_ROWS, capacity: 7, base_speed: 0.14, speed_step: 0.035, max_speed: 0.45 };

export const bitsForLevel = (level) => (level <= 1 ? 4 : level === 2 ? 6 : 8);
export const levelOfRow = (k, rpl = ROWS_PER_LEVEL) => Math.floor(k / rpl) + 1;

export function nextRow(rng, k, cfg = DEFAULTS) {
  const level = levelOfRow(k, cfg.rows_per_level ?? ROWS_PER_LEVEL);
  const bits = bitsForLevel(level);
  const u1 = rng(), u2 = rng();
  return { row: k, level, bits, kind: u1 < 0.5 ? "b2d" : "d2b", value: 1 + Math.floor(u2 * (2 ** bits - 1)) };
}

export function generateRows(seed, count = MAX_ROWS, cfg = DEFAULTS) {
  const rng = mulberry32(seed);
  return Array.from({ length: count }, (_, k) => nextRow(rng, k, cfg));
}

export const rowScore = (bits, level, tMs) => (bits * 5 + Math.max(0, 20 - Math.floor(tMs / 300))) * level;
