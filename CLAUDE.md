# PyArena — instruções para o Claude

Jogo web competitivo **e saudável** para alunos de **Programação I (Python)**. O plano completo e aprovado está em [docs/PLANO.md](docs/PLANO.md): ler a secção relevante antes de começar uma tarefa.

## Modos de jogo
- **Treino ("Mundo")**: mapa-mundo pixel art com regiões que seguem as aulas (santuários, masmorras com corações, relíquias), contratos diários, moedas para cosméticos.
- **Arena de Algoritmia** (opcional, estilo LeetCode): níveis Hard / Extra Hard / Hardcore Insane, que equivalem a LeetCode Easy / Medium / Hard. Inclui testes grandes (TLE) e editorial.
- **Duelo 1v1**: só por código de convite, melhor de 3, ELO, ligas e temporadas, power-ups simétricos, honras.
- **Torneio** controlado pelo professor: "Formato Aula" (agências, 5 rondas, pista a 0,5×, +5 para o primeiro, ×2 na ronda 5, boss battle) ou "Grupos + Eliminatórias".
- **Leaderboard**: turma, semanal, ranked, algoritmia, torneios e honras. Também destaca a evolução, não só o top.

## Regras inegociáveis
1. **Originalidade:** tiramos ideias de mecânicas de géneros (aventura, missões, ranked), mas **nunca** nomes, personagens, logótipos, fontes, música ou visual de jogos existentes (LoL, GTA, Zelda…). Os problemas de algoritmia são clássicos com enunciado escrito por nós; nunca se copiam enunciados do LeetCode.
2. **Bilingue PT-PT (omissão) + EN.** Nenhuma string fixa: `t("chave")` / `data-i18n` no frontend e chaves (`"duel.invite_expired"`) nas respostas da API. Problemas e conteúdos com `pt`/`en`, incluindo os outputs de texto esperados. O PT é sempre de Portugal (ecrã, ficheiro, utilizador), nunca PT-BR. `check_i18n` tem de passar.
3. **Avaliação = resultado.** Uma submissão é aceite se o output/valor devolvido estiver certo, use o aluno o que usar. **Nunca** se restringem as submissões pelo currículo: o verificador de currículo serve **só** para as soluções de referência. Restrições de estrutura só existem se o problema declarar `requisitos`, e têm de aparecer em destaque no enunciado (🧱).
4. **Segurança:** o código do aluno corre **só no runner** (contentor sem rede nem BD), nunca com `exec` na app, e a comparação é feita no processo pai. Nada de `innerHTML` com dados de utilizadores. CSP sem scripts inline. Cookies `HttpOnly` + CSRF. Permissões verificadas no servidor. Testes escondidos e soluções nunca saem do servidor. WebSocket autenticado e com limites.
5. **Resiliência de rede:** nunca perder código (rascunho em localStorage), submissões idempotentes com ID gerado no cliente, temporizador definido pelo servidor, reconexão com replay por `seq`, service worker com o esqueleto da app.
6. **Fluidez:** cada página com < 50 KB gzip de JS próprio, submissão p95 < 2 s com 20 submissões em simultâneo, API p95 < 150 ms. Eventos agrupados 1×/s. Nada pode bloquear o editor.
7. **Tudo em Docker Compose.** A VM só tem Docker. Sem CDN nem serviços externos: three.js, CodeMirror e as fontes ficam em `frontend/vendor/` com versão fixa e checksum.

## Stack
- **Backend:** Python 3.12, FastAPI (API JSON + WebSocket), SQLModel + asyncpg, PostgreSQL 16, Alembic. **Sem Redis:** pub/sub com `LISTEN/NOTIFY`, filas com `FOR UPDATE SKIP LOCKED`, presença em `UNLOGGED TABLE`.
- **Frontend:** HTML + JS com **módulos ES nativos**, **sem frameworks e sem build de JS**. **Tailwind v4** via binário standalone dentro do Docker, **mobile first** (360 px primeiro, alvos ≥ 44 px, nada dependente de hover). PWA instalável.
- **Design:** pixel art retro original. Cores **só** via tokens/temas (`styles/themes/<tema>.css` + `@theme` em `styles/app.css`), nunca classes de cor fixas como `bg-red-500`. Fontes pixel só em títulos/UI; enunciados e código em monoespaçada normal. 6 temas rotativos, que o aluno pode fixar no perfil.
- **3D:** three.js em voxels pixelizados, **só** em `frontend/scenes/`, carregado com `import()` dinâmico, com versão 2D de reserva, respeito por `prefers-reduced-motion`, pausa quando o separador está escondido, `dispose()` ao sair e autodegradação. **Nunca** na página do editor.

## Estrutura
```
backend/app/{models,api,realtime,services,tools}/   backend/problems/   backend/content/   backend/tests/
runner/            # contentor isolado: sandbox, harness (stdin/stdout e chamadas), requirements.py
frontend/{pages,components,services,scenes,i18n,styles,vendor,assets}/
deploy/Caddyfile   docker-compose.yml   docs/PLANO.md   materiais_aulas/ (no .gitignore)
```
**pages** = ecrãs (1 HTML + 1 JS por pasta) · **components** = peças visuais reutilizáveis · **services** = comunicação (api, socket, storage, i18n, theme). Cada ficheiro é curto e começa com um **comentário em português a explicar para que serve**, porque o professor quer perceber o projeto. Código, identificadores e commits em inglês.

## Problemas (YAML em `backend/problems/`)
- Tipos: `programa` (stdin/stdout; o prompt do `input()` é ignorado), `funcao` (chamadas), `decomposicao`, `tracar`, `bug`, `quiz`. Comparação `texto` | `numeros` | `exato`, tolerante a espaços, maiúsculas e acentos, e com `14` = `14.0` = `14,0`.
- Campos obrigatórios: textos `pt`/`en`, `bloco`, `dificuldade`, `estado` (`rascunho` até o professor aprovar), `solucao_referencia`. Opcionais: `requisitos`, `pistas` (cada uma vale 0,5×), `erros_comuns`. Na algoritmia: `nivel_algo`, `restricoes`, `solucao_ingenua` (tem de dar TLE) e `editorial`.
- **Currículo** (`backend/content/curriculum.yaml`, a partir de `materiais_aulas/`): 1 algoritmos/fluxogramas · 2 sequencial · 3 decomposição · 4 condicionais · 5 ciclos · 6 funções · 7 listas (**1–7 já dados**). 6b recursividade e 7b matrizes só abrem quando o professor as marcar como dadas.
- **Estilo do professor:** variáveis inicializadas no topo antes de ler (`numero = 0`), CONSTANTES em maiúsculas, nomes em português snake_case, comentários input → processamento → output, humor do dia a dia (o gato, o café, o foguetão). Feedback específico para erros clássicos: prioridade de operadores, `/` vs `//`, `input()` devolve texto, off-by-one, acumulador não inicializado, ciclo infinito.

## Comandos (sempre via compose)
```bash
docker compose up -d --build
docker compose run --rm app pytest
docker compose run --rm app python -m app.tools.validate_problems
docker compose run --rm app python -m app.tools.check_curriculum
docker compose run --rm app python -m app.tools.check_i18n
docker compose logs -f app
```

## Orquestração
- **Opus** orquestra: define contratos (modelos, rotas, eventos WS), delega, revê diffs, corre testes, faz `/security-review` no fim de cada fase e `/code-review` antes do uso com alunos.
- **Sonnet** implementa a lógica e o que toca em segurança: backend, runner, tempo real, duelo/torneio, serviços JS, páginas com estado, cenas 3D, problemas de algoritmia, bosses e problemas `tracar`/`bug`.
- **Haiku** trata do repetitivo: restantes problemas, CSS/páginas simples, testes simples, README.
- Os subagentes **só alteram os ficheiros que lhes foram atribuídos**. Paralelismo só sem ficheiros partilhados.

## Definição de "feito"
Testes, `validate_problems`, `check_curriculum` e `check_i18n` a passar · comentário de topo em PT em cada ficheiro · funciona a 375 px e em desktop · nenhuma dependência de frontend nova sem aprovação do professor.
