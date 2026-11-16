# Bit a Bit: gerador determinístico das linhas a partir de uma seed (o MESMO algoritmo em Python e em JavaScript),
# validação das respostas e pontuação. ESPECIFICAÇÃO DO GERADOR (o frontend tem de a seguir à letra):
#
#   PRNG mulberry32 (seed é um inteiro de 32 bits sem sinal), cada chamada devolve um número em [0, 1):
#       function mulberry32(a) {
#         return function () {
#           a |= 0; a = (a + 0x6D2B79F5) | 0;
#           let t = Math.imul(a ^ (a >>> 15), 1 | a);
#           t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
#           return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
#         };
#       }
#   Linha k (k = 0, 1, 2, ... por ordem; o PRNG é consumido SEMPRE por esta ordem, 2 chamadas por linha):
#       nível  = floor(k / ROWS_PER_LEVEL) + 1                    (ROWS_PER_LEVEL = 10)
#       bits   = 4 se nível 1, 6 se nível 2, 8 se nível >= 3
#       u1 = rng(); u2 = rng()
#       kind   = "b2d" se u1 < 0.5 senão "d2b"                    (b2d: dados os bits, escreve o número; d2b: dado o número, liga os bits)
#       value  = 1 + floor(u2 * (2^bits - 1))                      (inteiro em [1, 2^bits - 1])
#   Máximo MAX_ROWS = 80 linhas. A resposta de uma linha é sempre o valor decimal (em d2b, o decimal dos bits ligados).
#   Pontuação de uma linha certa: (bits * 5 + max(0, 20 - floor(t_ms / 300))) * nível.  Pontos = floor(pontuação / 100), máx. 50/dia.
#   Vetores de teste partilhados: backend/tests/fixtures/bitabit_vectors.json.
import math

MASK = 0xFFFFFFFF
ROWS_PER_LEVEL = 10
MAX_ROWS = 80
MIN_MS_PER_ROW = 300
POINTS_DIV = 100


def _imul(a: int, b: int) -> int:
    return (a * b) & MASK


def mulberry32(seed: int):
    a = seed & MASK

    def rng() -> float:
        nonlocal a
        a = (a + 0x6D2B79F5) & MASK
        t = _imul(a ^ (a >> 15), 1 | a)
        t = ((t + _imul(t ^ (t >> 7), 61 | t)) & MASK) ^ t
        return ((t ^ (t >> 14)) & MASK) / 4294967296

    return rng


def level_of(k: int) -> int:
    return k // ROWS_PER_LEVEL + 1


def bits_of(level: int) -> int:
    return 4 if level == 1 else 6 if level == 2 else 8


def rows(seed: int, n: int = MAX_ROWS) -> list[dict]:
    rng = mulberry32(seed)
    out = []
    for k in range(n):
        level = level_of(k)
        bits = bits_of(level)
        u1, u2 = rng(), rng()
        out.append({"k": k, "level": level, "bits": bits, "kind": "b2d" if u1 < 0.5 else "d2b", "value": 1 + math.floor(u2 * (2 ** bits - 1))})
    return out


def config() -> dict:
    return {"rows_per_level": ROWS_PER_LEVEL, "max_rows": MAX_ROWS, "min_ms_per_row": MIN_MS_PER_ROW, "points_div": POINTS_DIV,
            "daily_cap": 50, "bits_by_level": {"1": 4, "2": 6, "3+": 8}}


def row_score(bits: int, level: int, t_ms: int) -> int:
    return (bits * 5 + max(0, 20 - t_ms // 300)) * level


class Implausible(Exception):
    pass


def evaluate(seed: int, answers: list[dict], elapsed_ms: int) -> tuple[int, int]:
    """(pontuação, nº de linhas certas) recalculadas no servidor. Levanta Implausible se as respostas forem
    impossíveis (linha repetida/fora de alcance, tempo < mínimo por linha, ou mais tempo gasto do que o decorrido)."""
    if not isinstance(answers, list) or len(answers) > MAX_ROWS:
        raise Implausible("shape")
    seq = rows(seed)
    seen: set[int] = set()
    total_t, score, right = 0, 0, 0
    for a in answers:
        if not isinstance(a, dict) or not all(isinstance(a.get(k), int) and not isinstance(a.get(k), bool) for k in ("row", "value", "t_ms")):
            raise Implausible("shape")
        r, t = a["row"], a["t_ms"]
        if not 0 <= r < MAX_ROWS or r in seen:
            raise Implausible("row")
        if t < MIN_MS_PER_ROW:
            raise Implausible("too_fast")
        seen.add(r)
        total_t += t
        if a["value"] == seq[r]["value"]:
            score += row_score(seq[r]["bits"], seq[r]["level"], t)
            right += 1
    if total_t > elapsed_ms + 3000:
        raise Implausible("time")
    return score, right
