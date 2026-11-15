# Converte um .pptx ou .pdf em PNG por slide (1280 px de largura) para /data/slides/<deck>/<n>.png + manifest.json.
# Corre dentro do contentor "converter" (sem rede). Uso: convert.py <deck_id> <ficheiro> [--titulo "..."]
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

OUT = Path("/data/slides")
WIDTH = 1280


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("deck")
    ap.add_argument("file")
    ap.add_argument("--titulo", default="")
    args = ap.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", args.deck):
        print("deck inválido (a-z, 0-9 e hífens)", file=sys.stderr)
        return 2
    src = Path(args.file)
    if not src.is_file() or src.suffix.lower() not in (".pptx", ".pdf"):
        print("ficheiro inexistente ou não é .pptx/.pdf", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        pdf = src
        if src.suffix.lower() == ".pptx":
            copy = tmp / "deck.pptx"  # nome ASCII simples para o LibreOffice
            shutil.copy(src, copy)
            subprocess.run(
                ["soffice", "--headless", "--norestore", "-env:UserInstallation=file:///tmp/lo", "--convert-to", "pdf", "--outdir", str(tmp), str(copy)],
                check=True, timeout=600,
            )
            pdf = tmp / "deck.pdf"
        subprocess.run(["pdftoppm", "-png", "-scale-to-x", str(WIDTH), "-scale-to-y", "-1", str(pdf), str(tmp / "p")], check=True, timeout=600)
        pages = sorted(tmp.glob("p-*.png"), key=lambda p: int(p.stem.split("-")[1]))
        if not pages:
            print("nenhum slide gerado", file=sys.stderr)
            return 1
        stage = OUT / f".{args.deck}.tmp"
        shutil.rmtree(stage, ignore_errors=True)
        stage.mkdir(parents=True)
        for i, p in enumerate(pages, 1):
            shutil.copy(p, stage / f"{i}.png")
        (stage / "manifest.json").write_text(
            json.dumps({"id": args.deck, "titulo": args.titulo or args.deck, "n_slides": len(pages), "width": WIDTH}, ensure_ascii=False), encoding="utf-8"
        )
        final = OUT / args.deck
        shutil.rmtree(final, ignore_errors=True)
        stage.rename(final)
    print(f"{args.deck}: {len(pages)} slides")
    return 0


sys.exit(main())
