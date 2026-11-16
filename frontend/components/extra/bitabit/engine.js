// Motor do Bit a Bit, sem DOM: linhas a subir (posição em "linhas" desde o fundo), pontuação, níveis e fim de jogo.
// A vista chama tick(dtMs) a cada frame e submit(valor); o motor avisa por callbacks (onSpawn/onClear/onWrong/onLevel/onOver).
// t_ms de cada resposta = tempo de jogo (sem pausas) desde que a linha ficou "a vez" (a mais antiga), >= 300 ms, como o servidor exige.
import { mulberry32, nextRow, rowScore, DEFAULTS, MIN_MS_PER_ROW } from "./rng.js";

export function createEngine({ seed, config = {}, ...hooks }) {
  const cfg = { ...DEFAULTS, ...config };
  const rng = mulberry32(seed);
  const rpl = cfg.rows_per_level;
  const s = { pending: [], spawned: 0, cleared: 0, score: 0, streak: 0, best_streak: 0, mistakes: 0, ms: 0, turnStart: 0, over: false, answers: [] };
  const emit = (name, ...a) => hooks[name]?.(...a);

  const level = () => Math.min(Math.floor(s.cleared / rpl) + 1, Math.ceil(cfg.max_rows / rpl));
  const speed = () => Math.min(cfg.max_speed, cfg.base_speed + cfg.speed_step * (level() - 1)); // linhas por segundo

  function spawn(p = 0) {
    const row = { ...nextRow(rng, s.spawned++, cfg), p, born: s.ms };
    if (!s.pending.length) s.turnStart = s.ms;
    s.pending.push(row);
    emit("onSpawn", row);
  }

  function end(reason) {
    if (s.over) return;
    s.over = true;
    emit("onOver", reason);
  }

  function tick(dtMs) {
    if (s.over) return;
    s.ms += dtMs;
    const dp = (speed() * dtMs) / 1000;
    for (const r of s.pending) r.p += dp;
    const newest = s.pending[s.pending.length - 1];
    if (s.spawned < cfg.max_rows) {
      if (!newest) spawn(0);
      else if (newest.p >= 1) spawn(newest.p - 1);
    }
    if (s.pending[0]?.p >= cfg.capacity - 1) end("top");
  }

  // value: o número escolhido (d2b: valor dos bits ligados; b2d: o que o aluno escreveu)
  function submit(value) {
    const row = s.pending[0];
    if (s.over || !row) return null;
    if (Number(value) !== row.value) {
      s.streak = 0; s.mistakes++;
      emit("onWrong", row);
      return { ok: false, row };
    }
    const t_ms = Math.max(MIN_MS_PER_ROW, Math.round(s.ms - Math.max(row.born, s.turnStart)));
    const gained = rowScore(row.bits, row.level, t_ms);
    s.streak++; s.best_streak = Math.max(s.best_streak, s.streak);
    s.score += gained; s.cleared++;
    s.pending.shift();
    s.turnStart = s.ms;
    s.answers.push({ row: row.row, value: row.value, t_ms });
    emit("onClear", row, gained);
    if (s.cleared % rpl === 0 && s.cleared < cfg.max_rows) emit("onLevel", level());
    if (s.cleared >= cfg.max_rows) end("done");
    return { ok: true, row, gained };
  }

  return {
    cfg, tick, submit, end,
    get state() { return s; },
    get level() { return level(); },
    get rowsLeft() { return rpl - (s.cleared % rpl); },
    get active() { return s.pending[0] ?? null; },
  };
}
