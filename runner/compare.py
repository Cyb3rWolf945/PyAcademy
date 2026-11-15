# Comparação do output do aluno com o esperado. Corre SEMPRE no processo pai (servidor do runner),
# nunca dentro do processo do aluno. Modos: texto (tolerante), numeros (extrai números) e exato.
import math
import re
import unicodedata

NUM_RE = re.compile(r"(?<![\w.,)])[-+]?(?:\d+(?:[.,]\d+)?|\.\d+)(?:[eE][-+]?\d+)?")


def lang_of(locale: str) -> str:
    return "en" if str(locale).lower().startswith("en") else "pt"


def pick(text, locale: str):
    """Texto esperado: str igual nas duas línguas, ou {pt, en}."""
    if isinstance(text, dict):
        key = lang_of(locale)
        return text.get(key) or text.get("pt") or text.get("en") or ""
    return "" if text is None else text


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def normalize_text(s: str) -> list[str]:
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in s.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return [strip_accents(ln.casefold()) for ln in lines]


def extract_numbers(s: str) -> list[float]:
    out = []
    for m in NUM_RE.finditer(s):
        try:
            out.append(float(m.group().replace(",", ".")))
        except ValueError:
            pass
    return out


def num_close(a: float, b: float, abs_tol: float = 0.01, rel_tol: float = 1e-6) -> bool:
    if math.isnan(a) or math.isnan(b):
        return math.isnan(a) and math.isnan(b)
    return math.isclose(a, b, rel_tol=rel_tol, abs_tol=abs_tol)


def compare_output(mode: str, expected: str, actual: str) -> bool:
    """Compara stdout de programas."""
    if mode == "exato":
        strip = lambda s: s[:-1] if s.endswith("\n") else s  # noqa: E731
        return strip(expected) == strip(actual)
    if mode == "numeros":
        exp = extract_numbers(expected)
        if exp:
            act = extract_numbers(actual)
            return len(exp) == len(act) and all(num_close(a, b) for a, b in zip(exp, act))
    return normalize_text(expected) == normalize_text(actual)  # texto (e numeros sem números esperados)


def _is_num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def values_equal(expected, actual, mode: str = "texto", ordered: bool = True) -> bool:
    """Comparação profunda de valores devolvidos por funções (com tolerância em floats)."""
    if _is_num(expected) and _is_num(actual):
        return num_close(float(expected), float(actual), abs_tol=0.01 if mode == "numeros" else 1e-6)
    if isinstance(expected, bool) or isinstance(actual, bool):
        return expected is actual
    if isinstance(expected, str) and isinstance(actual, str):
        return expected == actual if mode == "exato" else normalize_text(expected) == normalize_text(actual)
    if isinstance(expected, (list, tuple)) and isinstance(actual, (list, tuple)):
        if len(expected) != len(actual):
            return False
        if ordered:
            return all(values_equal(e, a, mode, ordered) for e, a in zip(expected, actual))
        return _multiset_equal(list(expected), list(actual), mode, ordered)
    if isinstance(expected, dict) and isinstance(actual, dict):
        ek, ak = {str(k): v for k, v in expected.items()}, {str(k): v for k, v in actual.items()}
        return ek.keys() == ak.keys() and all(values_equal(ek[k], ak[k], mode, ordered) for k in ek)
    return expected is None and actual is None


def _multiset_equal(exp: list, act: list, mode: str, ordered: bool) -> bool:
    if all(_is_num(x) for x in exp + act):
        return all(num_close(a, b, 1e-6 if mode != "numeros" else 0.01) for a, b in zip(sorted(exp), sorted(act)))
    if all(isinstance(x, str) for x in exp + act) and mode == "exato":
        return sorted(exp) == sorted(act)
    left = list(act)
    for e in exp:  # emparelhamento guloso (O(n^2)), suficiente para listas pequenas/médias
        for i, a in enumerate(left):
            if values_equal(e, a, mode, ordered):
                del left[i]
                break
        else:
            return False
    return True
