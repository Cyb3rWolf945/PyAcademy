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


def _check_pair(folder: Path, label: str) -> tuple[list[str], set[str]]:
    errors = []
    pt = flatten(json.loads((folder / "pt-PT.json").read_text(encoding="utf-8")))
    en = flatten(json.loads((folder / "en.json").read_text(encoding="utf-8")))
    for k in sorted(pt.keys() - en.keys()):
        errors.append(f"{label}en.json: falta a chave '{k}'")
    for k in sorted(en.keys() - pt.keys()):
        errors.append(f"{label}pt-PT.json: falta a chave '{k}'")
    for name, d in (("pt-PT.json", pt), ("en.json", en)):
        errors += [f"{label}{name}: valor vazio em '{k}'" for k, v in d.items() if not (isinstance(v, str) and v.strip())]
    return errors, set(pt)


def check_json(i18n_dir: Path) -> list[str]:
    """Ficheiro base (i18n/pt-PT.json + en.json) e cada área listada em i18n/areas.json."""
    errors, seen = _check_pair(i18n_dir, "")
    areas_file = i18n_dir / "areas.json"
    areas = json.loads(areas_file.read_text(encoding="utf-8")) if areas_file.exists() else []
    for area in areas:
        folder = i18n_dir / area
        if not (folder / "pt-PT.json").exists() or not (folder / "en.json").exists():
            errors.append(f"{area}/: falta pt-PT.json ou en.json")
            continue
        errs, keys = _check_pair(folder, f"{area}/")
        errors += errs
        errors += [f"{area}/: chave '{k}' repetida noutro ficheiro" for k in sorted(keys & seen)]
        seen |= keys
    for folder in sorted(p for p in i18n_dir.iterdir() if p.is_dir() and p.name not in areas):
        errors.append(f"{folder.name}/: área não listada em areas.json")
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
