# Contrato: Torneio "Eliminatória" (individual) + pontos pessoais + leaderboard público

Escrito pelo orquestrador. É a fonte de verdade para os agentes **T** (backend), **F** (frontend do torneio + perfil) e **D** (leaderboard público na homepage).
Este contrato complementa o [CONTRATO_TORNEIO.md](CONTRATO_TORNEIO.md) (o Formato Aula continua a existir). O **novo formato por omissão** ao criar um torneio é `eliminatoria`.

## 1. Regras do formato Eliminatória (definidas pelo professor)
- **Individual:** sem equipas. Todos os alunos que entram com o código jogam por si.
- **Grupos automáticos:** em cada ronda, os jogadores **ainda em jogo** são distribuídos por grupos de `group_size` (omissão 4), equilibrados (tamanhos que diferem no máximo 1, mínimo 2 por grupo). Os grupos são sorteados, evitando repetir adversários da ronda anterior sempre que possível.
  - `n_grupos = ceil(n / group_size)`. Exemplo: 20 → 5 grupos de 4; 18 → 5 grupos (4, 4, 4, 3, 3); 7 → 2 grupos (4, 3).
  - **Final:** quando os jogadores em jogo forem ≤ `group_size + 1` (omissão ≤ 5), a ronda seguinte é a **final**: um só grupo, cujo vencedor ganha o torneio.
  - Passam `advance_per_group` por grupo (omissão 1; o professor pode pôr 2 para ter mais rondas).
  - Antes de começar, o professor vê uma **pré-visualização** do bracket com o número de alunos atual (ex. 20 → 5 grupos → 5 → final com 5 → campeão). Pode mudar `group_size` (3–6) e `advance_per_group` (1–2).
- **Exercícios:** cada ronda tem **um** exercício, o mesmo para todos os grupos dessa ronda. A dificuldade sobe a cada ronda: fácil → médio → difícil. Na final, ★★★★–★★★★★ ou um boss. Os exercícios são escolhidos automaticamente pelo bloco mais alto aberto e pela dificuldade, e o professor pode trocá-los antes de cada ronda. Só tipos com código (`programa`, `funcao`, `bug`). Duração por ronda configurável (omissão: fácil 8 min, médio 10, difícil/final 12).
- **Quem ganha o grupo:**
  1. O **primeiro** a ter uma submissão **aceite**. O grupo fica decidido nesse instante e os outros membros veem "🏆 <nome> venceu o grupo". Podem continuar a tentar para ganhar os pontos do exercício, mas já não passam.
  2. Se o tempo acabar sem ninguém aceite: quem tiver a submissão com **mais testes passados**. Em empate, a que chegou **mais cedo**.
  3. Se ninguém do grupo submeteu nada: **sorteio** (marcado como `decided_by: "draw"`).
  - O professor pode **corrigir manualmente** o vencedor de um grupo (`decided_by: "teacher"`), por exemplo se um aluno ficou sem rede.
  - Com `advance_per_group = 2`, passam os 2 primeiros por esta mesma ordem.
- **A ronda termina** quando todos os grupos estiverem decididos ou o tempo acabar (+ `grace_s` de tolerância para submissões que já iam a caminho). Fecha **automaticamente**, sem o professor ter de carregar (o professor também pode fechar mais cedo). Depois, o professor carrega em "Próxima ronda" e os grupos novos são sorteados.
- **Eliminados:** passam a **espectadores**. Veem o bracket e o grupo em direto e podem resolver o exercício da ronda **em modo treino**: ganham os pontos do exercício (ver §2), mas não voltam ao torneio. Isto mantém toda a gente ocupada e motivada.
- **Progresso ao vivo no grupo:** cada membro vê os adversários do grupo com "testes passados X/Y" e o número de tentativas. **Nunca** vê o código.

## 2. Pontos pessoais (persistentes, alimentam o leaderboard)
Ficam numa tabela-livro `user_points (id, user_id, points, reason, tournament_id|null, round_idx|null, problem_slug|null, created_at)`.
O total de um aluno é a soma dos seus registos, e o total semanal é a soma desde segunda-feira às 00:00 (hora de Lisboa).
- **Exercício resolvido** (primeira aceitação desse exercício nesse torneio, por aluno): fácil (1–2★) **+10**, médio (3★) **+20**, difícil (4–5★) **+30**. Os eliminados em modo treino também ganham estes pontos.
- **Vencer o grupo** (passar de ronda): **+15**.
- **Vencer o torneio:** **+100** extra. 2.º lugar (finalista com mais testes) **+50**, 3.º **+25**.
- **Participar** (entrar e submeter pelo menos uma vez): **+5**, uma só vez por torneio.
- Os valores ficam no `config` do torneio (`points: {easy, medium, hard, group_win, champion, second, third, participation}`) e o professor pode alterá-los ao criar o torneio.
- **Idempotente:** nunca há pontos duplicados pela mesma razão (índice único em user_id + tournament_id + reason + round_idx + problem_slug).
- O Formato Aula, no modo `individual`, também regista pontos de exercício (mesma tabela, razão `exercise`).

## 3. Leaderboard público + flag de privacidade
- **Novo campo** `User.show_in_leaderboard: bool = False` (**desligado por omissão**, por causa do RGPD). Altera-se no perfil com `PATCH /api/me/preferences {show_in_leaderboard}`.
- `GET /api/leaderboard/public?period=all|week&limit=10..50` (**sem login**):
  - Responde `{"period", "updated_at", "entries": [{"rank", "display_name", "points", "avatar_seed"}]}`.
  - Só inclui alunos com a flag ligada e pontos > 0, e **nunca** o `username` nem a turma.
  - Cache de 30 s no servidor, rate limit leve por IP.
- `GET /api/leaderboard/me?period=all|week` (com login) → `{"rank", "points", "visible": bool, "total_ranked"}`. A posição do próprio aluno é calculada **entre todos os alunos** (mesmo que ele próprio esteja escondido), para ele saber onde está.
- O professor nunca aparece no leaderboard.
- **Perfil** (F): um interruptor "Mostrar o meu nome e pontuação no leaderboard público", com uma explicação curta: "o teu nome a mostrar fica visível para qualquer pessoa na página inicial; podes desligar quando quiseres". Também mostra os pontos totais e da semana.
- **Homepage** (D):
  - Landing pública e hub com o painel "🏆 Leaderboard": separadores Geral / Esta semana, top 10 com pódio para os 3 primeiros (2D pixel; o 3D é opcional e só se não pesar).
  - Para quem tem sessão, uma linha fixa com "Tu: #7 · 230 pts" (com "(escondido)" se a flag estiver desligada) e um atalho para o perfil para ativar.
  - Quando não há ninguém: "Ainda não há ninguém no leaderboard. Ganha pontos nos torneios e ativa a opção no teu perfil!".
  - Atualiza ao voltar ao separador e de 60 em 60 s, sem WebSocket.

## 4. API e eventos do torneio Eliminatória (T)
- `POST /api/tournaments {class_id, name, format: "eliminatoria"|"aula", mode?, group_size?, advance_per_group?, points?}`. Sem `format` → `eliminatoria`.
- `GET /api/tournaments/{id}/bracket-preview?group_size=&advance_per_group=` (professor) → `{"players": n, "rounds": [{"idx", "groups": k, "sizes": [...], "advancing": m, "is_final": bool}]}`.
- Controlo (professor):
  - `POST .../rounds/next/start`: sorteia os grupos com os jogadores em jogo e começa a ronda.
  - `.../rounds/{idx}/pause|resume|extend|close`.
  - `PUT .../rounds/{idx}`: muda o exercício ou a duração enquanto a ronda está `pending`.
  - `POST .../groups/{gid}/winner {user_id}`: correção manual do vencedor.
  - `POST .../finish`.
- O snapshot `GET /api/tournaments/{id}/state` acrescenta, quando `format == "eliminatoria"`:
  ```json
  {"format": "eliminatoria",
   "config": {"group_size", "advance_per_group", "points"},
   "players_count", "alive_count",
   "me": {"user_id", "status": "alive"|"eliminated"|"champion", "group_id", "eliminated_in_round"},
   "rounds": [{"idx", "title", "is_final", "state", "ends_at", "remaining_s", "difficulty": "easy|medium|hard",
               "groups": [{"id", "members": [{"user_id", "display_name", "passed", "total", "attempts", "solved_at", "status": "playing|winner|out"}],
                           "decided": bool, "winners": [user_id], "decided_by": "solve|tests|draw|teacher"|null}]}],
   "current": {"idx", "mission": <vista pública do exercício> + {"solved_by_me", "practice": bool}},
   "champion": null | {"user_id", "display_name"},
   "podium": null | [ ...top3 ],
   "my_points_this_tournament": n}
  ```
  As rondas passadas mantêm os grupos (é o histórico do bracket). Todos os participantes veem o bracket inteiro, com nomes a mostrar (dentro da turma, não é público).
- **Eventos WebSocket novos:**
  - `groups_drawn` {idx, groups}
  - `group_progress` {idx, group_id, user_id, passed, total, attempts}: agrupado, no máximo 2×/s por torneio
  - `group_decided` {idx, group_id, winners, decided_by}
  - `player_eliminated` {user_ids, idx}
  - `round_closed`
  - `champion` {user_id, display_name}
  - `points_awarded` {user_id, points, reason}: **só para o próprio** (enviado na socket desse utilizador)
  - Os eventos existentes (`round_started`, `round_paused`, etc.) mantêm-se.
- **Submissões:** o mesmo `POST /api/submissions` com `tournament_id` + `round_idx`. Para quem está em jogo conta para o grupo. Para os eliminados é treino (pontos de exercício, nunca vitória). O dispatcher regista testes passados e tentativas para o progresso e decide o grupo quando há uma submissão aceite.
- **Fecho automático:** uma tarefa em cada worker (com lock consultivo por torneio, para só um agir) fecha as rondas cujo `ends_at + grace_s` já passou e decide os grupos que faltam.

## 5. Frontend (F)
- **Admin:**
  - criar torneio com o formato Eliminatória por omissão;
  - campos group_size / advance_per_group com pré-visualização do bracket ao vivo;
  - editor de exercício por ronda;
  - painel: "Próxima ronda (sorteia grupos)", pausar, +2 min, fechar, terminar;
  - grelha dos grupos com progresso ao vivo e botão "definir vencedor" com confirmação.
- **Aluno:**
  - lobby "Estás dentro! X alunos";
  - ronda: o exercício (editor) + o painel do grupo com os adversários (barra X/Y testes, tentativas, 🏆 quando vence) + temporizador;
  - ecrã "Venceste o grupo! Passas à ronda N" com celebração;
  - ecrã "Foste eliminado na ronda N — continua a treinar: os exercícios ainda dão pontos", com o modo espectador (bracket ao vivo e editor de treino);
  - final;
  - campeão;
  - resumo dos meus pontos ganhos neste torneio;
  - toasts de `points_awarded` ("+20 pts");
  - diploma também para o campeão.
- **Projetor:** lobby com o código e a contagem; **bracket ao vivo** (colunas por ronda, grupos como caixas com os avatares e barras de progresso, o vencedor destacado e linhas para a ronda seguinte); temporizador grande; celebração do campeão + pódio.
- **Perfil:** interruptor `show_in_leaderboard` + pontos totais e da semana (usa `/api/leaderboard/me`).
- Chaves i18n em `i18n/tournament/*` e `i18n/editor/*` (as do perfil podem ir para `tournament` ou para uma área nova `profile`, que tem de ser listada em `areas.json`).

## 6. Quem é dono de que ficheiros
- **T:** como no contrato anterior + `backend/app/models/points.py`, `backend/app/services/{points,leaderboard,elimination}.py`, `backend/app/api/leaderboard.py`, migração `0004`, campo `show_in_leaderboard` (`models/user.py`, `api/auth.py` preferences e `user_payload`), testes, `frontend/i18n/tournament_api/*`.
- **F:** como no contrato anterior + `frontend/pages/profile/**` + `frontend/i18n/profile/*` (área nova).
- **D:** `frontend/components/leaderboard-public.js`, `frontend/pages/landing/**`, `frontend/pages/home/**`, `frontend/index.html`, `frontend/styles/**`, `frontend/i18n/home/*`.
- O orquestrador trata de `i18n/areas.json`.
