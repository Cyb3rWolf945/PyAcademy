# Ferramenta: confirma que cada SOLUÇÃO DE REFERÊNCIA só usa a matéria do seu bloco e dos anteriores
# (backend/content/curriculum.yaml). Analisa com ast: tipos de nó, funções embutidas, módulo.atributo,
# métodos chamados e recursão. Sai com 1 e um relatório legível (ficheiro, linha, construção, bloco onde se dá).
#
# IMPORTANTE: isto aplica-se SÓ às soluções de referência dos problemas, NUNCA às submissões dos alunos.
# Os alunos podem usar o que quiserem; o que conta é o resultado (ver CLAUDE.md, regra 3).
import ast
import builtins
import sys
from pathlib import Path

from app.config import settings
from app.services.problems import curriculum, iter_problem_files, parse_yaml

ORDER = ["1", "2", "3", "4", "5", "6", "7"]  # ordem de ensino; 6b e 7b são extensões
RECURSION_OK = {"6b", "7b", "mais_alem"}
BUILTIN_NAMES = set(dir(builtins))
IMPLICIT_NODES = {"Del"}  # contexto de `del`, aparece só com Delete (que é reportado)


def blocks_for(bloco: str) -> list[str] | None:
    """Blocos cuja matéria é permitida (None = livre)."""
    if bloco == "mais_alem":
        return None
    if bloco == "6b":
        return ORDER[:6] + ["6b"]
    if bloco == "7b":
        return ORDER + ["6b", "7b"]
    return ORDER[: ORDER.index(bloco) + 1]


class Rules:
    def __init__(self):
        self.by_id = {str(b["id"]): b.get("permite") or {} for b in curriculum()["blocos"]}

    def allowed(self, blocks: list[str]) -> dict:
        nos, builtins_, metodos, modulos = set(), set(), set(), {}
        for b in blocks:
            p = self.by_id.get(b, {})
            nos |= set(p.get("nos") or [])
            builtins_ |= set(p.get("builtins") or [])
            metodos |= set(p.get("metodos") or [])
            for mod, attrs in (p.get("modulos") or {}).items():
                modulos.setdefault(mod, set()).update(attrs or [])
        return {"nos": nos, "builtins": builtins_, "metodos": metodos, "modulos": modulos}

    def first_taught(self, kind: str, name: str) -> str:
        for b in ORDER + ["6b", "7b"]:
            p = self.by_id.get(b, {})
            if kind == "modulos":
                if name.split(".")[0] in (p.get("modulos") or {}):
                    return b
            elif name in (p.get(kind) or []):
                return b
        return "mais_alem (fora do programa)"


def is_recursive(tree: ast.AST) -> bool:
    funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    calls = {k: {c.func.id for c in ast.walk(f) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id in funcs} for k, f in funcs.items()}

    def reaches(start):
        seen, stack = set(), list(calls[start])
        while stack:
            cur = stack.pop()
            if cur == start:
                return True
            if cur not in seen:
                seen.add(cur)
                stack.extend(calls[cur])
        return False

    return any(reaches(n) for n in funcs)


def check_code(code: str, bloco: str, rules: Rules) -> list[tuple[int, str, str]]:
    """Devolve [(linha, construção, bloco onde se dá)] das construções não permitidas."""
    blocks = blocks_for(bloco)
    if blocks is None:
        return []
    allowed = rules.allowed(blocks)
    tree = ast.parse(code)
    issues: list[tuple[int, str, str]] = []
    bound = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    bound |= {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    bound |= {a.arg for a in ast.walk(tree) if isinstance(a, ast.arg)}
    aliases: dict[str, str] = {}
    line = 0
    for node in ast.walk(tree):
        line = getattr(node, "lineno", line)
        kind = type(node).__name__
        if kind not in allowed["nos"] and kind not in IMPLICIT_NODES and not isinstance(node, (ast.expr_context,)):
            issues.append((line, f"nó {kind}", rules.first_taught("nos", kind)))
        if isinstance(node, ast.Import):
            for a in node.names:
                aliases[a.asname or a.name.split(".")[0]] = a.name.split(".")[0]
                if a.name.split(".")[0] not in allowed["modulos"]:
                    issues.append((line, f"import {a.name}", rules.first_taught("modulos", a.name)))
        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or "").split(".")[0]
            if mod not in allowed["modulos"]:
                issues.append((line, f"from {node.module} import", rules.first_taught("modulos", mod)))
            else:
                for a in node.names:
                    if a.name not in allowed["modulos"][mod]:
                        issues.append((line, f"{mod}.{a.name}", rules.first_taught("modulos", mod)))
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in BUILTIN_NAMES and node.id not in bound:
            if node.id not in allowed["builtins"]:
                issues.append((line, f"função {node.id}()", rules.first_taught("builtins", node.id)))
        elif isinstance(node, ast.Attribute):
            base = node.value
            if isinstance(base, ast.Name) and base.id in aliases:
                mod = aliases[base.id]
                if mod in allowed["modulos"] and node.attr not in allowed["modulos"][mod]:
                    issues.append((line, f"{mod}.{node.attr}", rules.first_taught("modulos", mod)))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            base = node.func.value
            if not (isinstance(base, ast.Name) and base.id in aliases) and node.func.attr not in allowed["metodos"]:
                issues.append((line, f"método .{node.func.attr}()", rules.first_taught("metodos", node.func.attr)))
    if bloco not in RECURSION_OK and is_recursive(tree):
        issues.append((0, "recursão", "6b"))
    return sorted(set(issues))


def run(root: Path) -> list[str]:
    rules, report = Rules(), []
    for path in iter_problem_files(root):
        try:
            spec = parse_yaml(path)
        except Exception as exc:  # noqa: BLE001
            report.append(f"{path}: esquema inválido: {exc}")
            continue
        ref = spec.solucao_referencia
        if not ref:
            continue
        for lang, code in (("pt", ref),) if isinstance(ref, str) else (("pt", ref.pt), ("en", ref.en)):
            try:
                issues = check_code(code, spec.bloco, rules)
            except SyntaxError as exc:
                report.append(f"{path} [{lang}]: erro de sintaxe na solução: {exc}")
                continue
            for line, what, taught in issues:
                report.append(f"{path} [{lang}] linha {line}: {what} (bloco {spec.bloco}) só é dado no bloco {taught}")
    return report


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else settings.problems_dir
    report = run(root)
    for line in report:
        print("ERRO", line)
    print(f"{len(list(iter_problem_files(root)))} problemas verificados, {len(report)} construções fora do currículo")
    return 1 if report else 0


if __name__ == "__main__":
    sys.exit(main())
