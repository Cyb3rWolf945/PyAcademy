// Verificação em Node: lê o vetor partilhado com o backend e confirma que o gerador JS dá o mesmo resultado.
// Correr (na raiz do projeto): docker run --rm -v "$PWD":/w -w /w node:20-alpine node frontend/components/extra/bitabit/check_vectors.mjs
import { readFileSync } from "node:fs";
import { mulberry32, generateRows, rowScore } from "./rng.js";

const path = new URL("../../../../backend/tests/fixtures/bitabit_vectors.json", import.meta.url);
const data = JSON.parse(readFileSync(path, "utf8"));
let bad = 0, checks = 0;
const fail = (...a) => { bad++; console.error(...a); };
for (const c of data.vectors) {
  const rng = mulberry32(c.seed);
  c.rng.forEach((f, i) => { checks++; const v = rng(); if (v !== f) fail("rng", c.seed, i, v, f); });
  const got = generateRows(c.seed, c.rows.length);
  c.rows.forEach((r, i) => {
    checks++;
    const g = got[i];
    if (g.row !== r.k || g.level !== r.level || g.bits !== r.bits || g.kind !== r.kind || g.value !== r.value) fail("row", c.seed, i, g, r);
  });
}
for (const s of data.score.cases) { checks++; const v = rowScore(s.bits, s.level, s.t_ms); if (v !== s.score) fail("score", s, v); }
console.log(bad ? `FALHOU: ${bad} diferenças` : `OK: ${checks} verificações iguais ao Python (${data.vectors.length} seeds)`);
process.exit(bad ? 1 : 0);
