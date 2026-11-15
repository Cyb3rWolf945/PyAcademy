# Correção na app dos tipos sem código (quiz, decomposição, traçar): índices escolhidos ou texto normalizado.
# Estes tipos não passam pelo runner. Só se devolve certo/errado por pergunta, nunca a resposta certa.
import re
import unicodedata

from app.i18n import pick
from app.services.problems import ProblemSpec


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.casefold())
    return re.sub(r"\s+", " ", "".join(c for c in s if not unicodedata.combining(c))).strip()


def valid_answers(spec: ProblemSpec, answers) -> bool:
    if not isinstance(answers, list) or len(answers) != len(spec.perguntas):
        return False
    for q, a in zip(spec.perguntas, answers):
        if q.resposta is not None:
            if not (isinstance(a, list) and all(isinstance(i, int) and not isinstance(i, bool) and 0 <= i < len(q.opcoes) for i in a)):
                return False
        elif not (isinstance(a, str) and len(a) <= 500):
            return False
    return True


def grade(spec: ProblemSpec, answers: list, locale: str) -> dict:
    results = []
    for q, a in zip(spec.perguntas, answers):
        if q.resposta is not None:
            ok = set(a) == set(q.resposta)
        else:
            ok = norm(a) == norm(pick(q.resposta_texto.model_dump() if hasattr(q.resposta_texto, "model_dump") else q.resposta_texto, locale))
        results.append(ok)
    passed = sum(results)
    status = "accepted" if passed == len(results) else "wrong_answer"
    return {"status": status, "passed": passed, "total": len(results), "result": {"status": status, "passed": passed, "total": len(results), "questions": results}}
