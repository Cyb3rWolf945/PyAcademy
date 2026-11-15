# Ferramenta: regista na base de dados um deck de slides já convertido (PNG em /data/slides/<deck>/ + manifest.json).
# A conversão .pptx/.pdf -> PNG é feita pelo contentor "converter" (LibreOffice + poppler, sem rede); o script
# scripts/import_slides.sh corre os dois passos. Uso: python -m app.tools.import_slides <deck> [ficheiro] --titulo "..."
import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.db import SessionLocal
from app.models._base import utcnow
from app.models.academy import SlideDeck


def read_manifest(deck: str, slides_dir: Path) -> dict:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", deck):
        raise SystemExit("deck inválido (a-z, 0-9 e hífens)")
    path = slides_dir / deck / "manifest.json"
    if not path.is_file():
        raise SystemExit(f"{path} não existe: converte primeiro o ficheiro com o contentor converter (ver docs/SLIDES.md)")
    m = json.loads(path.read_text(encoding="utf-8"))
    n = int(m["n_slides"])
    missing = [i for i in range(1, n + 1) if not (slides_dir / deck / f"{i}.png").is_file()]
    if missing:
        raise SystemExit(f"faltam PNG: {missing[:5]}")
    return m


async def register(deck: str, titulo: str | None, slides_dir: Path | None = None) -> dict:
    m = read_manifest(deck, slides_dir or settings.slides_dir)
    values = dict(id=deck, titulo=(titulo or m.get("titulo") or deck)[:120], n_slides=int(m["n_slides"]), imported_at=utcnow())
    async with SessionLocal() as db:
        await db.execute(insert(SlideDeck).values(**values).on_conflict_do_update(
            index_elements=["id"], set_={k: v for k, v in values.items() if k != "id"}))
        await db.commit()
    return values


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("deck")
    ap.add_argument("file", nargs="?", help="(informativo) ficheiro de origem, convertido pelo contentor converter")
    ap.add_argument("--titulo", default=None)
    args = ap.parse_args()
    row = asyncio.run(register(args.deck, args.titulo))
    print(f"{row['id']}: {row['n_slides']} slides registados ({row['titulo']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
