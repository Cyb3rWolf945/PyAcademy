# Slides das aulas (Academia)

Os slides do professor nunca entram no git nem na imagem da app. São convertidos num contentor próprio (`converter`: LibreOffice headless + poppler-utils, imagem fixa, **sem rede**, perfil `tools` do compose) para PNG de 1280 px de largura, guardados no volume Docker `slides` e servidos só a quem tem sessão (`/api/academy/slides/<deck>/<n>`, cache privada de 1 h). A app monta o volume só de leitura em `/data/slides`.

## Importar um deck
```bash
scripts/import_slides.sh <deck_id> "<ficheiro .pptx|.pdf>" "<título>"
# exemplo
scripts/import_slides.sh aula-2 "materiais_aulas/Introdução à Programação - Aula II.pptx" "Aula II - Introdução à Programação"
```
O script faz dois passos:
1. `docker compose --profile tools run --rm -v <ficheiro>:/input/<nome>:ro converter <deck> /input/<nome> --titulo "..."` converte e escreve `/data/slides/<deck>/<n>.png` + `manifest.json` (o ficheiro de origem é montado só de leitura, só durante esta execução);
2. `docker compose run --rm app python -m app.tools.import_slides <deck> --titulo "..."` regista (ou atualiza) a linha em `slide_decks`.

`deck_id`: letras minúsculas, dígitos e hífens (até 40). Repetir o comando substitui o deck.

## Decks importados na fase A1
| deck | origem | slides |
|---|---|---|
| `aula-1` | Introdução à Programação - Aula I.pptx | 10 |
| `aula-2` | Introdução à Programação - Aula II.pptx | 40 |
| `aula-3` | Introdução_à_Programação_-_Aula_III.pptx | 31 |
| `aula-3-5` | Introdução à Programação - Aula de decomposição 3.5.pptx | 27 |
| `aula-4` | Estruturas_Condicionais - Aula IV.pptx | 24 |
| `ciclos` | Estruturas_de_Repeticao.pdf | 21 |

## Notas
- O volume `slides` vive na máquina onde se importa: numa VM nova é preciso repetir a importação (os ficheiros de `materiais_aulas/` ficam fora do repositório).
- `python -m app.tools.validate_academy` avisa quando uma secção refere um deck que ainda não foi importado e dá erro se o intervalo `de–ate` ultrapassar o deck.
- Build do conversor (só uma vez, ~740 MB): `docker compose --profile tools build converter`.
