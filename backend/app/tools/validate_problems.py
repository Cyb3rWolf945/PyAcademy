# Ferramenta: valida o esquema de todos os YAML em backend/problems (sai com código 1 se houver erros).
import sys
from pathlib import Path

from app.config import settings
from app.services.problems import iter_problem_files, parse_yaml


def validate(root: Path) -> list[str]:
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


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else settings.problems_dir
    errors = validate(root)
    for e in errors:
        print("ERRO", e)
    n = len(list(iter_problem_files(root)))
    print(f"{n} problemas verificados, {len(errors)} erros")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
