# Verificação de requisitos de estrutura (ast), corre no pai DEPOIS de os testes passarem.
# Só se aplica quando o problema declara `requisitos`; nunca restringe problemas sem eles.
import ast

ALIASES = {
    "while": ("While",), "for": ("For", "AsyncFor"), "if": ("If",), "lista": ("List", "ListComp"),
    "funcao": ("FunctionDef",), "def": ("FunctionDef",), "lambda": ("Lambda",), "return": ("Return",),
    "break": ("Break",), "continue": ("Continue",), "import": ("Import", "ImportFrom"),
    "compreensao": ("ListComp", "SetComp", "DictComp", "GeneratorExp"), "dicionario": ("Dict", "DictComp"),
}


def parse(code: str) -> ast.AST:
    return ast.parse(code, "<aluno>")


def is_recursive(tree: ast.AST) -> bool:
    """Há ciclo no grafo de chamadas entre funções definidas pelo aluno (inclui recursão direta)."""
    funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    calls = {
        name: {c.func.id for c in ast.walk(fn) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id in funcs}
        for name, fn in funcs.items()
    }

    def reaches(start: str) -> bool:
        seen, stack = set(), list(calls[start])
        while stack:
            cur = stack.pop()
            if cur == start:
                return True
            if cur not in seen:
                seen.add(cur)
                stack.extend(calls[cur])
        return False

    return any(reaches(name) for name in funcs)


def uses(tree: ast.AST, token: str) -> bool:
    """O token é uma estrutura (while, for...), um nó ast, uma função/método chamado ou um módulo importado."""
    if token in ("recursao", "recursiva"):
        return is_recursive(tree)
    if token == "elif":
        return any(isinstance(n, ast.If) and len(n.orelse) == 1 and isinstance(n.orelse[0], ast.If) for n in ast.walk(tree))
    kinds = ALIASES.get(token) or ((token,) if hasattr(ast, token) and isinstance(getattr(ast, token), type) else ())
    for node in ast.walk(tree):
        if kinds and type(node).__name__ in kinds:
            return True
        if token == "lista" and isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "list":
            return True
        if isinstance(node, ast.Name) and node.id == token and not kinds:
            return True
        if isinstance(node, ast.Attribute) and node.attr == token and not kinds:
            return True
        if isinstance(node, ast.Import) and any(a.name.split(".")[0] == token for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == token:
            return True
    return False


def check(code: str, requisitos: dict | None) -> list[dict]:
    """Devolve os requisitos NÃO cumpridos: [{kind, value|nome+parametros}]."""
    if not requisitos:
        return []
    tree = parse(code)
    unmet: list[dict] = []
    for token in requisitos.get("usa") or []:
        if not uses(tree, str(token)):
            unmet.append({"kind": "usa", "value": str(token)})
    for token in requisitos.get("proibe") or []:
        if uses(tree, str(token)):
            unmet.append({"kind": "proibe", "value": str(token)})
    spec = requisitos.get("define_funcao")
    if spec:
        want_n = spec.get("parametros")
        ok = any(
            isinstance(n, ast.FunctionDef) and n.name == spec.get("nome")
            and (want_n is None or len(n.args.posonlyargs) + len(n.args.args) == want_n)
            for n in ast.walk(tree)
        )
        if not ok:
            unmet.append({"kind": "define_funcao", "nome": spec.get("nome"), "parametros": want_n})
    if requisitos.get("recursiva") and not is_recursive(tree):
        unmet.append({"kind": "recursiva"})
    return unmet
