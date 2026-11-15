# Feedback amigável: traduz a "família" de erro clássico devolvida pelo runner numa chave i18n
# e os requisitos não cumpridos em chaves + parâmetros. Tabela pequena e fácil de estender.
import re

HINT_KEYS = {
    "zero_division": "feedback.zero_division",
    "int_float_input": "feedback.int_float_input",
    "int_conversion": "feedback.int_conversion",
    "float_conversion": "feedback.float_conversion",
    "str_plus_int": "feedback.str_plus_int",
    "input_is_text": "feedback.input_is_text",
    "recursion": "feedback.recursion",
    "uninitialized_variable": "feedback.uninitialized_variable",
    "missing_function": "feedback.missing_function",
    "index_error": "feedback.index_error",
    "too_many_inputs": "feedback.too_many_inputs",
    "import_blocked": "feedback.import_blocked",
    "syntax": "feedback.syntax",
    "infinite_loop": "feedback.infinite_loop",
    "too_slow": "feedback.too_slow",
    "output_limit": "feedback.output_limit",
    "memory": "feedback.memory",
    "div_vs_floordiv": "feedback.div_vs_floordiv",
    "return_none": "feedback.return_none",
}
REQUIREMENT_KEYS = {
    "usa": "requirement.usa", "proibe": "requirement.proibe",
    "define_funcao": "requirement.define_funcao", "recursiva": "requirement.recursiva",
}
CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
RESULT_KEYS = ("status", "passed", "total", "cases", "unmet_requirements", "feedback", "hint_family", "error", "runtime_ms", "peak_mem_kb")
VISIBLE_CASE_KEYS = ("index", "visible", "status", "passed", "input", "expected", "actual", "error", "runtime_ms")
HIDDEN_CASE_KEYS = ("index", "visible", "status", "passed", "runtime_ms")  # nunca entradas/saídas escondidas


def hint_key(family: str | None) -> str | None:
    return HINT_KEYS.get(family or "")


def clean(obj):
    """Texto vindo do runner pode ter NUL/controlo (o JSONB do Postgres rejeita \\u0000): troca por U+FFFD."""
    if isinstance(obj, str):
        return CONTROL_RE.sub("\ufffd", obj.encode("utf-8", "replace").decode("utf-8"))
    if isinstance(obj, list):
        return [clean(x) for x in obj]
    if isinstance(obj, dict):
        return {(clean(k) if isinstance(k, str) else k): clean(v) for k, v in obj.items()}
    return obj


def sanitize_result(resp: dict) -> dict:
    """Lista branca do que a API devolve ao aluno (defesa em profundidade além do runner)."""
    resp = clean(resp)
    out = {k: resp.get(k) for k in RESULT_KEYS}
    out["cases"] = [
        {k: c.get(k) for k in (VISIBLE_CASE_KEYS if c.get("visible") else HIDDEN_CASE_KEYS)} for c in resp.get("cases") or []
    ]
    out["hint_key"] = hint_key(resp.get("hint_family"))
    out["requirement_keys"] = [dict(u, key=REQUIREMENT_KEYS.get(u.get("kind"), "requirement.usa")) for u in resp.get("unmet_requirements") or []]
    return out
