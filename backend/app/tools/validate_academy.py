# Ferramenta: valida os conteúdos da Academia (backend/content/academy): esquema, ids únicos, respostas válidas,
# stmt ids existentes, bilingue completo e referências a slides (aviso se o deck ainda não foi importado).
# Uso: python -m app.tools.validate_academy [pasta]. Sai com 1 se houver erros.
import sys
from pathlib import Path

from app.config import settings
from app.services import academy_content


def validate(root: Path | None = None, slides_dir: Path | None = None) -> tuple[list[str], list[str]]:
    c = academy_content.load(root or settings.academy_dir, slides_dir)
    return c.errors, c.warnings


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else settings.academy_dir
    errors, warnings = validate(root)
    for w in warnings:
        print("AVISO", w)
    for e in errors:
        print("ERRO", e)
    c = academy_content.load(root)
    print(f"validate_academy: {len(c.modules)} módulos, {len(c.sections)} secções, {len(errors)} erros, {len(warnings)} avisos")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
