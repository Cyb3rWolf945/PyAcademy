# Cliente do runner (HTTP na rede "sandbox"): monta os pedidos a partir do problema e chama /run e /generate.
# Usa só a stdlib (urllib em thread) para não acrescentar dependências à app.
import asyncio
import hashlib
import json
import urllib.error
import urllib.request

from app.config import settings
from app.services.problems import ProblemSpec


class RunnerError(Exception):
    """Runner inacessível ou com resposta inválida (o trabalho volta à fila)."""


class GeneratedMissing(Exception):
    """Faltam os args/devolve calculados dos `args_gerador` deste problema."""


def _post(path: str, body: dict, timeout: float, url: str | None = None, token: str | None = None) -> dict:
    req = urllib.request.Request(
        (url or settings.runner_url).rstrip("/") + path, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "X-Runner-Token": token if token is not None else settings.runner_token},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - URL interno configurado
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise RunnerError(f"runner http {exc.code}") from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise RunnerError(str(exc)) from exc


def post_sync(path: str, body: dict, timeout: float | None = None, **kw) -> dict:
    return _post(path, body, timeout or settings.runner_timeout_s, **kw)


async def post(path: str, body: dict, timeout: float | None = None) -> dict:
    return await asyncio.to_thread(_post, path, body, timeout or settings.runner_timeout_s)


def reference_code(spec: ProblemSpec, locale: str = "pt-PT") -> str:
    ref = spec.solucao_referencia
    return ref if isinstance(ref, str) else (ref.en if locale == "en" else ref.pt)


def generator_exprs(spec: ProblemSpec) -> list[tuple[int, str]]:
    return [(i, c.args_gerador) for i, c in enumerate(spec.testes) if c.args_gerador is not None]


def generated_hash(spec: ProblemSpec) -> str:
    ref = reference_code(spec)
    blob = json.dumps([ref, spec.assinatura, spec.limite_tempo_s, generator_exprs(spec)], sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def build_generate_request(spec: ProblemSpec) -> dict:
    return {
        "code": reference_code(spec), "assinatura": spec.assinatura, "limite_tempo_s": spec.limite_tempo_s,
        "exprs": [e for _, e in generator_exprs(spec)],
    }


def items_to_generated(spec: ProblemSpec, items: list[dict]) -> dict:
    idx = [i for i, _ in generator_exprs(spec)]
    return {"hash": generated_hash(spec), "items": {str(i): it for i, it in zip(idx, items)}}


def build_run_request(spec: ProblemSpec, code: str, locale: str, generated: dict | None = None) -> dict:
    """Pedido ao /run. Os testes com gerador usam os valores calculados (têm de existir e estar em dia)."""
    cases = [dict(c.model_dump(mode="json", exclude_none=True), visible=True) for c in spec.exemplos]
    for i, c in enumerate(spec.testes):
        d = c.model_dump(mode="json", exclude_none=True)
        if c.args_gerador is not None:
            item = ((generated or {}).get("items") or {}).get(str(i))
            if (generated or {}).get("hash") != generated_hash(spec) or item is None:
                raise GeneratedMissing(spec.id)
            d = {"args": item["args"], "devolve": item["devolve"]}
        cases.append(dict(d, visible=False))
    return {
        "code": code, "locale": locale, "assinatura": spec.assinatura, "comparacao": spec.comparacao,
        "ordem_importa": spec.ordem_importa, "limite_tempo_s": spec.limite_tempo_s, "requisitos": spec.requisitos,
        "erros_comuns": [e.model_dump(mode="json", exclude_none=True) for e in spec.erros_comuns], "cases": cases,
    }
