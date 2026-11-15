#!/bin/sh
# Importa um deck de slides: converte o .pptx/.pdf em PNG no contentor "converter" (sem rede; o ficheiro é montado
# só de leitura) e regista-o na BD. Uso: scripts/import_slides.sh <deck_id> <ficheiro> "<título>"
set -e
DECK="$1"; FILE="$2"; TITULO="${3:-$1}"
[ -f "$FILE" ] || { echo "ficheiro não encontrado: $FILE"; exit 2; }
DIR="$(cd "$(dirname "$FILE")" && pwd)"; NAME="$(basename "$FILE")"
docker compose --profile tools run --rm -v "$DIR/$NAME:/input/$(printf '%s' "$NAME" | tr -c 'A-Za-z0-9._-' '_'):ro" converter "$DECK" "/input/$(printf '%s' "$NAME" | tr -c 'A-Za-z0-9._-' '_')" --titulo "$TITULO"
docker compose run --rm app python -m app.tools.import_slides "$DECK" --titulo "$TITULO"
