# Contrato: Torneio "Formato Aula" + design partilhado

Este contrato é escrito pelo orquestrador e é a fonte de verdade para os 3 agentes que trabalham em paralelo:
- **T** = backend do torneio + tempo real
- **F** = frontend do torneio (editor, ecrã do aluno, projetor, painel do professor)
- **D** = design pixel art, temas e homepage 3D

**Prioridade:** usar na aula de amanhã com ~20 alunos. Primeiro tem de ser robusto e simples, depois bonito.
Ficam para depois: "Grupos + Eliminatórias", duelos, mundo e loja.

## 1. Regras do Formato Aula (iguais à aula "Operação Decomposição" do professor)
- **Modo:** `individual` ou `agencias` (equipas de 2–4 alunos; o nome é escolhido pelos alunos no lobby).
- **Rondas:** o preset tem 5 rondas + boss.

  | # | Nome | Pontos por missão | Multiplicador | Missões | Duração (omissão) |
  |---|---|---|---|---|---|
  | R1 | Fácil | 10 | ×1 | 3 | 10 min |
  | R2 | Fácil-Médio | 10 | ×1 | 3 | 10 min |
  | R3 | Médio | 15 | ×1 | 3 | 12 min |
  | R4 | Médio-Difícil | 15 | ×1 | 3 | 12 min |
  | R5 | Difícil | 15 | **×2** | 3 | 15 min |
  | Boss | Boss Battle | 30 por cada participante que resolve | — | 1 (problema boss) | 10 min |
- **Pontuação de uma missão** (por participante, ou seja, aluno ou agência), dada na **primeira submissão aceite**:
  `pontos = pontos_missao × multiplicador × (0.5 se o participante abriu alguma pista dessa missão, senão 1)`.
  No modo agências, a pista conta se **qualquer** membro a abriu, e a missão fica resolvida para a agência inteira.
  Submissões erradas não tiram pontos (só se configurado: `penalizacao_erro`, que vale 0 por omissão).
- **Bónus de rapidez:** +5 para o **primeiro** participante a ter **todas** as missões da ronda certas. Não é multiplicado (o ×2 da R5 não se aplica ao bónus). Não há bónus no boss.
- **Boss:** todos contra um problema. Cada participante que o resolve ganha 30 pontos. A primeira resolução dispara o evento `boss_defeated` (a turma inteira celebra).
- **Fim:** pódio com top 3, e cada aluno pode descarregar um diploma pixel ("Mestre da Decomposição" / tema escolhido pelo professor), gerado no cliente (canvas → PNG).
- **Tempo:** o servidor decide. `ends_at` é absoluto. Uma submissão é aceite se o servidor a **receber** até `ends_at + 30 s` (tolerância para rede má). Com a ronda pausada não se aceitam submissões.
- **O professor pode usar problemas em rascunho** nos seus torneios (os alunos só os veem quando a ronda começa).

## 2. Modelos (T, migração `0003`)
- `tournaments`: id, class_id, teacher_id, name, mode, join_code (6), state (`lobby|round_active|round_paused|between_rounds|finished`), current_round (int|null), config JSONB (`hint_factor` 0.5, `first_bonus` 5, `grace_s` 30, `diploma_title` {pt,en}), created_at.
- `tournament_teams`: id, tournament_id, name (1–24 caracteres, único no torneio), color_idx.
- `tournament_players`: tournament_id, user_id, team_id|null, joined_at (PK tournament_id + user_id).
- `tournament_rounds`: id, tournament_id, idx, title {pt,en}, points, multiplier, duration_s, is_boss, problem_slugs[], state (`pending|active|paused|closed`), started_at, ends_at, remaining_s (enquanto pausada).
- `tournament_solves`: tournament_id, round_id, problem_slug, participant_key (`u:<id>` ou `t:<id>`), points, hint_used, submission_id, solved_at (único em tournament_id + round_id + problem_slug + participant_key).
- `tournament_hint_uses`: round_id, problem_slug, user_id, n.
- `tournament_bonus`: round_id, participant_key, points, kind (`first`).
- `tournament_events`: seq BIGSERIAL, tournament_id, type, payload JSONB, created_at. É o registo usado para replay.
- `presence` (UNLOGGED): tournament_id, user_id, last_seen, last_seq.

## 3. API REST (T). Erros sempre `{"error": "tournament.<chave>"}`, com as chaves em `i18n/tournament_api/*.json`
Professor (o dono, verificado no servidor):
- `POST /api/tournaments` `{class_id, name, mode}` → cria o torneio com o **preset Formato Aula**. Escolhe automaticamente problemas da turma pelo `bloco` mais alto aberto e pela `dificuldade` (R1: 1–2★, R2: 2★, R3: 3★, R4: 3–4★, R5: 4–5★, Boss: `origem: boss`). Inclui tipos `programa`, `funcao`, `bug` e (na R1/R2) `quiz`/`decomposicao`. Devolve o estado de admin.
- `PUT /api/tournaments/{id}/rounds/{idx}` `{title?, problem_slugs?, points?, multiplier?, duration_s?}` (só se a ronda estiver `pending`).
- `GET /api/tournaments?class_id=` · `GET /api/tournaments/{id}/admin` (estado completo + presença: quem está online ou offline + submissões por missão).
- Controlo: `POST /api/tournaments/{id}/rounds/{idx}/start` · `/pause` · `/resume` · `/extend {seconds}` · `/close` · `POST /api/tournaments/{id}/finish`.
- `POST /api/tournaments/{id}/teams/{tid}/move {user_id}` (mudar um aluno de agência).

Alunos (da turma do torneio):
- `POST /api/tournaments/join {join_code}` → `{tournament_id}` (idempotente).
- `POST /api/tournaments/{id}/teams {name}` (cria e entra) · `POST /api/tournaments/{id}/teams/{tid}/join` (no máximo 4 por agência; só no lobby).
- `GET /api/tournaments/{id}/state` → **snapshot** (também usado pelo projetor e pelo professor):
  ```json
  {"tournament": {"id","name","mode","state","current_round","join_code (só professor)","config"},
   "server_now": "ISO", "last_seq": 123,
   "rounds": [{"idx","title","points","multiplier","is_boss","state","ends_at","remaining_s","mission_count"}],
   "current": {"idx", "missions": [ <vista pública do problema> + {"slug","solved_by_me": bool,"hints_opened": n} ]},
   "me": {"user_id","team_id","participant_key"},
   "teams": [{"id","name","color_idx","members":[{"user_id","display_name"}]}],
   "leaderboard": [{"participant_key","name","points","per_round":[..],"solved":n,"rank","delta_rank"}],
   "podium": null | [ ...top3 ]}
  ```
  `current.missions` só vem com o conteúdo quando a ronda está `active|paused|closed`. **Nunca** inclui testes, soluções nem respostas.
- `GET /api/tournaments/{id}/events?after=<seq>` → `{"events":[...], "resync": bool}` (`resync=true` se faltarem mais de 500 eventos).
- `GET /api/tournaments/{id}/hints/{slug}/{n}` → abre a pista (marca 0,5× nessa missão) `{text:{pt,en}}`.
- Submeter: o **mesmo** `POST /api/submissions` da fase 2, mais os campos `tournament_id` e `round_idx`. O servidor valida que o aluno é participante, a ronda está ativa, o problema pertence à ronda e o pedido chegou dentro do tempo + tolerância. Quando a submissão é aceite → `tournament_solves` + evento. A resposta e o polling (`GET /api/submissions/{id}`) são os da fase 2. O rate limit no torneio é de 10/min.

## 4. WebSocket (T)
`GET /ws/tournaments/{id}?last_seq=N`. Autenticado pelo cookie de sessão, com verificação do `Origin`, mensagens no máximo de 8 KB, no máximo 3 ligações por utilizador e ping/pong a cada 15 s (atualiza a `presence`).
- **Servidor → cliente:** `{"seq":124,"type":"...","payload":{...}}`. Ao ligar, o servidor reenvia os eventos com `seq > last_seq`, ou envia `{"type":"resync"}`.
- **Tipos de evento:**
  - `player_joined` {user_id, display_name}
  - `team_updated` {teams}
  - `round_started` {idx, ends_at, server_now}
  - `round_paused` {idx, remaining_s}
  - `round_resumed` {idx, ends_at, server_now}
  - `round_extended` {idx, ends_at}
  - `round_closed` {idx}
  - `mission_solved` {participant_key, name, slug, points, hint_used}: sem código, sem detalhes
  - `first_bonus` {participant_key, name, idx}
  - `leaderboard` {leaderboard}: **agrupado, no máximo 1×/s por torneio**
  - `boss_defeated` {participant_key, name}
  - `tournament_finished` {podium}
- **Cliente → servidor:** só `{"type":"ping","last_seq":N}`.
- **Pub/sub entre workers:** `LISTEN/NOTIFY` no canal `tournament_<id>`, com o payload = seq. Cada worker lê o evento de `tournament_events` e envia-o aos seus sockets.

## 5. Frontend do torneio (F)
- **`services/socket.js`:** `connectTournament(id, {onEvent, onStatus})`. Reconecta com backoff (1, 2, 4… até 10 s) e envia `last_seq` ao reconectar. Com `resync` → GET state. Se o WebSocket falhar 3 vezes seguidas, passa a fazer polling a `/events?after=` de 5 em 5 s. O estado da ligação é `online|reconnecting|offline`.
- **`services/storage.js`:** rascunho de código por `tournament:round:slug` no localStorage (com debounce de 500 ms) e fila offline de submissões (com o `client_id` gerado antes de enviar e reenvio automático).
- **`components/editor.js`:** CodeMirror 6 num único bundle ESM em `vendor/codemirror/` (gerado com esbuild num contentor e com versão fixa). Inclui a barra de símbolos para mobile (`components/symbol-bar.js`). Os tipos sem código (quiz/decomposicao/tracar) são formulários de opções ou de texto.
- **`components/timer.js`:** contagem até `ends_at`, corrigida pela diferença `server_now - Date.now()`. Fica vermelho a pulsar nos últimos 60 s. Continua a contar offline.
- **`components/leaderboard.js`:** lista com animação FLIP, setas ▲▼, a linha do próprio aluno destacada e sempre visível, e cores de agência pelo `color_idx`.
- **`components/connection-status.js`:** 🟢/🟡/🔴.
- **`pages/tournament/`** (aluno), mobile first:
  - entrar com código;
  - lobby (criar ou entrar numa agência, ver quem já está);
  - ronda: cartões de missão com estado, toque → editor em ecrã inteiro com separadores Enunciado | Código | Resultado, botões de pista com o aviso "vale metade dos pontos", e resultado com feedback;
  - mini-ranking;
  - ecrã entre rondas;
  - boss;
  - pódio final + diploma PNG.
- **`pages/projector/`** (professor, ecrã grande): nome do torneio, código de entrada enorme no lobby, ronda atual, temporizador grande, ranking animado, toasts de "missão resolvida", celebração no boss e no pódio. Usa `scenes/podium.js` do D (ver §6), com versão 2D se falhar.
- **`pages/admin/`:** acrescentar uma secção "Torneios":
  - criar (turma, nome, modo);
  - editar as rondas, com um seletor de problemas filtrável por bloco, tipo e dificuldade (inclui rascunhos);
  - painel de controlo grande e à prova de toques acidentais (iniciar, pausar, +2 min, fechar ronda, próxima, boss, terminar, com confirmação nas ações destrutivas);
  - presença (quem está offline) e link para abrir o projetor.
- **i18n:** chaves em `i18n/tournament/*.json` e `i18n/editor/*.json`, em PT-PT e EN.

## 6. Design partilhado (D define; F usa só estes nomes)
**Cores** (Tailwind via `@theme`, a partir de variáveis CSS do tema):
`surface`, `surface-2`, `surface-3`, `text`, `muted`, `accent`, `accent-2`, `success`, `warning`, `danger`, `gold`, `silver`, `bronze`, `team-0` … `team-7`.
Utilitários: `bg-surface`, `text-accent`, `border-accent`, etc.

**Fontes:** `font-pixel` (títulos/UI), `font-ui` (texto pixel legível), `font-mono` (código e enunciados).

**Componentes CSS** (em `@layer components`):
- `.btn-pixel` (+ `--accent`, `--danger`, `--ghost`, `--lg`)
- `.panel-pixel`, `.panel-pixel--inset`
- `.input-pixel`
- `.badge-pixel`
- `.card-mission` (+ `--solved`, `--locked`)
- `.xp-bar`
- `.timer-pixel` (+ `--danger`)
- `.toast-pixel`
- `.tabs-pixel`
- `.stars` (★)

**Animações** (com `steps()`): `.anim-pop`, `.anim-coin`, `.anim-float-up`, `.anim-shake`. Todas respeitam `prefers-reduced-motion`.

**Cenas 3D** (D implementa, F só chama):
```js
// frontend/scenes/podium.js
export async function mountPodium(el, top3 /* [{name, points, color_idx}] */, { theme }) -> { dispose() }
// frontend/scenes/lobby-island.js (homepage)
export async function mountLobby(el, { theme }) -> { dispose(), setTheme(theme) }
// frontend/scenes/celebrate.js (boss/pódio): partículas pixel por cima de tudo
export async function celebrate(el, { kind: "boss"|"podium"|"solve" }) -> Promise<void>
```
Se o WebGL falhar ou com `prefers-reduced-motion`, todas devolvem uma versão 2D em CSS/canvas.

## 7. Quem é dono de que ficheiros (nunca editar ficheiros de outro agente)
- **T:** `backend/app/models/tournament.py`, `backend/app/api/tournament.py`, `backend/app/api/ws.py`, `backend/app/realtime/**`, `backend/app/services/tournament*.py`, alterações mínimas em `services/submissions.py` + `api/submissions.py` (campos de torneio), `backend/alembic/versions/0003_*`, `backend/tests/test_tournament*.py`, `frontend/i18n/tournament_api/*`. Pode acrescentar o router em `main.py`.
- **F:**
  - `frontend/pages/{tournament,projector,challenge}/**` e a secção de torneios em `frontend/pages/admin/**`;
  - `frontend/components/{editor,symbol-bar,timer,leaderboard,connection-status,mission-card}.js`;
  - `frontend/services/{socket,storage}.js`;
  - `frontend/vendor/codemirror/**`;
  - `frontend/i18n/{tournament,editor}/*`.
- **D:**
  - `frontend/styles/**` e `frontend/assets/**`;
  - `frontend/vendor/{three,fonts}/**`, `frontend/scenes/**`;
  - `frontend/index.html`, `frontend/pages/{landing,home}/**`;
  - `frontend/services/theme*.js`, `frontend/components/{bottom-nav,lang-switch,toast}.js`;
  - `frontend/manifest.webmanifest`, `frontend/i18n/home/*`.
- Ninguém altera `frontend/i18n/pt-PT.json`/`en.json` (base), CLAUDE.md, nem os ficheiros dos outros. Se precisares de algo fora da tua área, **descreve-o no relatório**.
