# Avalia uma submissão: corre cada caso no sandbox, compara (no pai), verifica requisitos e monta a resposta.
# NUNCA devolve entradas/saídas esperadas dos testes escondidos: só passou/falhou e o estado.
import ast
import json

import compare
import erros_comuns
import requirements

MAX_CODE = 20 * 1024
MAX_STDIN = 64 * 1024
SEVERITY_OK = "ok"


class BadRequest(ValueError):
    pass


def _fn_name(assinatura: str) -> str:
    sig = assinatura.strip()
    if sig.startswith("def "):
        sig = sig[4:]
    return sig.split("(")[0].strip()


def _clip(value, limit=2000):
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    return value if len(text) <= limit else text[:limit] + "…"


def _check_request(req: dict) -> None:
    if not isinstance(req.get("code"), str) or not isinstance(req.get("cases"), list) or not req["cases"]:
        raise BadRequest("code and cases are required")
    if len(req["code"].encode("utf-8")) > MAX_CODE:
        raise BadRequest("code too large")
    if req.get("assinatura") is not None and not isinstance(req["assinatura"], str):
        raise BadRequest("bad assinatura")


def evaluate(req: dict, sandbox) -> dict:
    _check_request(req)
    code, locale = req["code"], req.get("locale", "pt-PT")
    funcao = bool(req.get("assinatura"))
    mode = req.get("comparacao", "texto")
    ordered = req.get("ordem_importa", True)
    limit = float(req.get("limite_tempo_s", 2))
    limit = min(max(limit, 0.1), 10.0)
    fn = _fn_name(req["assinatura"]) if funcao else None
    cases = req["cases"]
    resp = {
        "status": "accepted", "passed": 0, "total": len(cases), "cases": [], "unmet_requirements": [],
        "feedback": None, "hint_family": None, "error": None, "runtime_ms": 0, "peak_mem_kb": 0,
    }
    try:
        ast.parse(code, "<aluno>")
    except (SyntaxError, ValueError) as exc:
        resp["status"] = "compile_error"
        resp["error"] = {"type": type(exc).__name__, "message": str(getattr(exc, "msg", exc))[:300], "line": getattr(exc, "lineno", None)}
        resp["hint_family"] = "syntax"
        return resp

    first_fail = None
    for index, case in enumerate(cases):
        visible = bool(case.get("visible"))
        stdin = case.get("stdin") or ""
        if len(stdin.encode()) > MAX_STDIN:
            raise BadRequest("stdin too large")
        job = {"mode": "funcao" if funcao else "programa", "code": code, "fn": fn, "args": case.get("args") or [], "limit_s": limit}
        run = sandbox.run(job, stdin)
        expected = compare.pick(case.get("stdout"), locale) if not funcao else case.get("devolve")
        actual = run.value if funcao else run.stdout
        status = run.status
        passed = False
        if status == "ok":
            passed = compare.values_equal(expected, actual, mode, ordered) if funcao else compare.compare_output(mode, expected, actual)
            status = "ok" if passed else "wrong_answer"
        resp["passed"] += passed
        resp["runtime_ms"] = max(resp["runtime_ms"], run.runtime_ms)
        resp["peak_mem_kb"] = max(resp["peak_mem_kb"], run.peak_mem_kb)
        detail = {"index": index, "visible": visible, "status": status, "passed": passed, "runtime_ms": run.runtime_ms}
        if visible:
            detail.update({
                "input": case.get("args") if funcao else stdin, "expected": _clip(expected),
                "actual": _clip(actual), "error": run.error,
            })
        resp["cases"].append(detail)
        if not passed and first_fail is None:
            first_fail = (status, run.error, expected, actual, case, visible)
        if not passed and status == "wrong_answer" and resp["feedback"] is None:
            resp["feedback"] = erros_comuns.match_problem_error(req.get("erros_comuns"), case, actual, funcao, mode, ordered, locale)

    if first_fail:
        status, error, expected, actual, _case, visible = first_fail
        resp["status"] = status
        resp["hint_family"] = erros_comuns.classify(status, error, code, expected if visible else None, actual if visible else None)
        if error:  # a mensagem pode conter dados do teste: só sai se o caso for visível
            resp["error"] = error if visible else {"type": error.get("type"), "line": error.get("line")}
        return resp

    unmet = requirements.check(code, req.get("requisitos"))
    if unmet:
        resp["status"], resp["unmet_requirements"] = "requirements_unmet", unmet
    return resp


def generate(req: dict, sandbox) -> dict:
    """Calcula args + valor esperado dos `args_gerador` com a solução de referência (código do autor)."""
    exprs, code = req.get("exprs"), req.get("code")
    if not isinstance(exprs, list) or not isinstance(code, str) or not req.get("assinatura"):
        raise BadRequest("exprs, code and assinatura are required")
    limit = min(float(req.get("limite_tempo_s", 2)) * (len(exprs) + 1) + 5, 120.0)
    run = sandbox.run({"mode": "gerar", "code": code, "fn": _fn_name(req["assinatura"]), "exprs": exprs, "args": [], "limit_s": limit})
    if run.status != "ok" or run.items is None:
        return {"status": run.status if run.status != "ok" else "runtime_error", "error": run.error, "items": []}
    return {"status": "ok", "error": None, "items": run.items}
