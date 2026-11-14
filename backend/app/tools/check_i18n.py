# Ferramenta: garante que pt-PT.json e en.json têm as mesmas chaves e que todo o conteúdo YAML é bilingue.
import json
import sys
from pathlib import Path

import yaml

from app.config import settings


def flatten(d: dict, prefix: str = "") -> dict[str, object]:
    out = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        out.update(flatten(v, key) if isinstance(v, dict) else {key: v})
    return out


def check_json(i18n_dir: Path) -> list[str]:
    errors = []
    pt = flatten(json.loads((i18n_dir / "pt-PT.json").read_text(encoding="utf-8")))
    en = flatten(json.loads((i18n_dir / "en.json").read_text(encoding="utf-8")))
    for k in sorted(pt.keys() - en.keys()):
        errors.append(f"en.json: falta a chave '{k}'")
    for k in sorted(en.keys() - pt.keys()):
        errors.append(f"pt-PT.json: falta a chave '{k}'")
    for name, d in (("pt-PT.json", pt), ("en.json", en)):
        errors += [f"{name}: valor vazio em '{k}'" for k, v in d.items() if not (isinstance(v, str) and v.strip())]
    return errors


def _walk(node, where: str, errors: list[str]) -> None:
    if isinstance(node, dict):
        if node.keys() & {"pt", "en"}:  # é um campo bilingue: as duas línguas, não vazias
            for lang in ("pt", "en"):
                v = node.get(lang)
                if not (isinstance(v, str) and v.strip()):
                    errors.append(f"{where}: falta '{lang}' ou está vazio")
        for k, v in node.items():
            _walk(v, f"{where}.{k}", errors)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _walk(v, f"{where}[{i}]", errors)


def check_yaml(root: Path) -> list[str]:
    errors = []
    if root.is_dir():
        for path in sorted(root.rglob("*.yaml")):
            _walk(yaml.safe_load(path.read_text(encoding="utf-8")), str(path), errors)
    return errors


def run(i18n_dir: Path, yaml_roots: list[Path]) -> list[str]:
    errors = check_json(i18n_dir)
    for r in yaml_roots:
        errors += check_yaml(r)
    return errors


def main() -> int:
    errors = run(settings.frontend_dir / "i18n", [settings.problems_dir, settings.problems_dir.parent / "content"])
    for e in errors:
        print("ERRO", e)
    print(f"check_i18n: {len(errors)} erros")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
