# Feedback específico: (1) `erros_comuns` do problema (output do aluno igual a um erro conhecido)
# e (2) uma pequena tabela de famílias de erros clássicos (devolve só um código; a app traduz).
import re

import compare


def match_problem_error(erros: list[dict], case: dict, actual, funcao: bool, mode: str, ordered: bool, locale: str):
    """Devolve a `mensagem` {pt,en} do primeiro erro comum cujo output coincide com o obtido."""
    for erro in erros or []:
        if erro.get("quando_stdin") is not None and erro["quando_stdin"] != case.get("stdin"):
            continue
        if erro.get("quando_args") is not None and erro["quando_args"] != case.get("args"):
            continue
        if funcao:
            if "devolve" in erro and compare.values_equal(erro["devolve"], actual, mode, ordered):
                return erro["mensagem"]
        elif erro.get("stdout") is not None and compare.compare_output(mode, compare.pick(erro["stdout"], locale), actual):
            return erro["mensagem"]
    return None


def classify(status: str, error: dict | None, code: str, expected=None, actual=None) -> str | None:
    """Família do erro clássico (ou None). Usa a mensagem completa, mas só devolve o código."""
    etype, msg = (error or {}).get("type"), (error or {}).get("message", "")
    if status == "runtime_error":
        if etype == "ZeroDivisionError":
            return "zero_division"
        if etype == "ValueError" and "invalid literal for int()" in msg:
            return "int_float_input" if re.search(r"[.,]\d", msg) else "int_conversion"
        if etype == "ValueError" and "could not convert string to float" in msg:
            return "float_conversion"
        if etype == "TypeError" and ("can only concatenate str" in msg or ("unsupported operand" in msg and "'str'" in msg)):
            return "str_plus_int"
        if etype == "TypeError" and "not supported between" in msg and "'str'" in msg:
            return "input_is_text"
        if etype == "RecursionError":
            return "recursion"
        if etype in ("NameError", "UnboundLocalError"):
            return "missing_function" if "function '" in msg else "uninitialized_variable"
        if etype == "IndexError":
            return "index_error"
        if etype == "EOFError":
            return "too_many_inputs"
        if etype == "ImportError":
            return "import_blocked"
        if etype == "SyntaxError":
            return "syntax"
    if status == "time_limit":
        return "infinite_loop" if re.search(r"^\s*while\b", code, re.M) else "too_slow"
    if status == "output_limit":
        return "output_limit"
    if status == "memory_limit":
        return "memory"
    if status == "wrong_answer":
        if isinstance(actual, str) and isinstance(expected, str):
            if re.search(r"\d\.0\b", actual) and not re.search(r"\d\.\d", expected) and "/" in code:
                return "div_vs_floordiv"
        if actual is None and expected is not None:
            return "return_none"
    return None
