# Ferramenta: valida o esquema de todos os YAML em backend/problems e CORRE as soluções no runner real.
#   - exemplos + testes têm de passar com a solucao_referencia (por língua, se for {pt, en});
#   - problemas `bug`: o codigo_inicial tem de falhar pelo menos um teste;
#   - algoritmia (nivel_algo): a solucao_ingenua tem de dar "tempo limite" num teste e a referência passar.
# Por omissão fala com o runner em RUNNER_URL (corre dentro do contentor da app). Sai com 1 se houver erros.
import sys
from pathlib import Path

from app.config import settings
from app.services import runner_client as rc
from app.services.problems import CODE_TIPOS, ProblemSpec, iter_problem_files, parse_yaml


def validate(root: Path) -> list[str]:
    """Só o esquema (rápido, sem runner)."""
    errors, seen = [], {}
    for path in iter_problem_files(root):
        try:
            spec = parse_yaml(path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path}: {exc}")
            continue
        if spec.id in seen:
            errors.append(f"{path}: id duplicado '{spec.id}' (já em {seen[spec.id]})")
        seen[spec.id] = path
    return errors


def _code_for(value, locale: str) -> str:
    return value if isinstance(value, str) else (value.en if locale == "en" else value.pt)


def _describe(resp: dict) -> str:
    bad = [c for c in resp.get("cases", []) if not c["passed"]]
    first = bad[0] if bad else {}
    extra = ""
    if first.get("visible"):
        extra = f" (esperado={first.get('expected')!r} obtido={first.get('actual')!r} erro={first.get('error')})"
    elif resp.get("error"):
        extra = f" (erro={resp['error']})"
    return f"{resp['status']} {resp['passed']}/{resp['total']}, caso {first.get('index')}{extra}, unmet={resp.get('unmet_requirements')}"


def run_semantics(path: Path, spec: ProblemSpec, post) -> list[str]:
    """`post(path, body) -> dict` fala com o runner (HTTP ou local)."""
    errs: list[str] = []
    if spec.tipo not in CODE_TIPOS:
        return errs
    generated = None
    if rc.generator_exprs(spec):
        resp = post("/generate", rc.build_generate_request(spec))
        if resp.get("status") != "ok":
            return [f"{path}: os args_gerador falharam na solução de referência: {resp.get('status')} {resp.get('error')}"]
        generated = rc.items_to_generated(spec, resp["items"])
    for locale in ("pt-PT", "en"):
        code = _code_for(spec.solucao_referencia, locale)
        r = post("/run", rc.build_run_request(spec, code, locale, generated))
        if r["status"] != "accepted":
            errs.append(f"{path}: solucao_referencia [{locale}] não passa: {_describe(r)}")
    if spec.tipo == "bug":
        r = post("/run", rc.build_run_request(spec, _code_for(spec.codigo_inicial, "pt-PT"), "pt-PT", generated))
        if r["status"] in ("accepted", "requirements_unmet") or r["passed"] == r["total"]:
            errs.append(f"{path}: o codigo_inicial (bug) devia falhar pelo menos um teste mas {r['status']}")
    if spec.nivel_algo:
        r = post("/run", rc.build_run_request(spec, spec.solucao_ingenua, "pt-PT", generated))
        if not any(c["status"] == "time_limit" for c in r["cases"]):
            errs.append(f"{path}: a solucao_ingenua devia dar tempo limite num teste mas deu {_describe(r)}")
    return errs


def validate_all(root: Path, post) -> list[str]:
    errors = validate(root)
    for path in iter_problem_files(root):
        try:
            spec = parse_yaml(path)
        except Exception:  # noqa: BLE001 - já reportado em validate()
            continue
        try:
            errors += run_semantics(path, spec, post)
        except rc.RunnerError as exc:
            errors.append(f"{path}: runner indisponível: {exc}")
    return errors


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    root = Path(args[0]) if args else settings.problems_dir
    errors = validate(root) if "--schema-only" in sys.argv else validate_all(root, lambda p, b: rc.post_sync(p, b, 120))
    for e in errors:
        print("ERRO", e)
    n = len(list(iter_problem_files(root)))
    print(f"{n} problemas verificados, {len(errors)} erros")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
