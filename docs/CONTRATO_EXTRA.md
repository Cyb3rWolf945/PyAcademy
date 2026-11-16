# Contrato: Atividades extracurriculares (Poker + Bit a Bit)

Escrito pelo orquestrador. É a fonte de verdade para os agentes:
- **T** (backend);
- **P** (frontend do poker);
- **B** (frontend do Bit a Bit);
- **D** (campus, navegação, sprites e página hub).

Regras gerais: as do `CLAUDE.md` (bilingue PT-PT/EN, CSP, sem HTML em bruto, mobile first, pixel art, robustez a rede má, tudo em Docker).

## 0. Ideia
Uma aba nova, **"Extra"** (Atividades extracurriculares), com dois jogos:
- **Poker (Texas Hold'em)**, de 2 a 10 jogadores. As fichas vêm dos **pontos de score**, e serve para "roubar" pontos aos colegas: o que um ganha, os outros perdem.
- **Bit a Bit**: um jogo **original** de conversão binário ↔ decimal, inspirado no género dos puzzles de binário (sem copiar nome, arte nem layout de nenhum jogo existente). Serve para **ganhar pontos**.

Ambos em pixel art, com os temas da app e o mesmo sistema de design (skills `pixel-art` e `gsap`).

## 1. Pontos e saldo
- **Livro único** `user_points` (já existe). Razões novas:
  - `poker_net` (pode ser **negativo**; um registo por mão e por jogador, com `ref = hand_id`);
  - `bitabit` (positivo).
- **Fonte das fichas** (definição do professor por turma: `academy`/`extra` settings): `extra_settings.poker_source = "torneios" | "todos"` (**por omissão `"torneios"`**).
  - **Saldo de poker disponível** = soma dos pontos com razões de torneio (`exercise` em contexto de torneio, `group_win`, `champion`, `second`, `third`, `participation`) **+ o líquido acumulado de `poker_net`**, quando a fonte é `"torneios"`. Com `"todos"`, é o total de todos os pontos.
  - **Nunca abaixo de 0.**
- **Leaderboard:** o total geral inclui `poker_net` e `bitabit`, por isso o poker mexe mesmo no score, como o professor pediu.
- **Proteções por omissão** (configuráveis pelo professor):
  - `poker_enabled: true` por turma; o professor pode desligar;
  - **buy-in** entre 10 e `min(200, 50% do saldo)`; quem tem saldo < 10 não se pode sentar;
  - **limite de perda diária**: 100 pontos (Europe/Lisbon); ao atingir, o jogador é levantado da mesa no fim da mão;
  - **mesas só entre alunos da mesma turma** (o professor pode observar);
  - **opt-in**: no primeiro acesso aparece um ecrã a explicar que se ganham e perdem pontos reais de score, e o aluno tem de aceitar.
- **Bit a Bit:**
  - pontos = `floor(pontuação_do_jogo / 100)`, **máximo 50 por dia** e por aluno;
  - as partidas acima do limite contam só para o recorde pessoal.

## 2. Poker (backend T)
- **Regras:** Texas Hold'em **No-Limit**.
  - Blinds pequenas 1/2. Botão do dealer rotativo; heads-up com as regras próprias (o dealer põe a small blind).
  - Rondas: pré-flop, flop, turn e river, mais showdown. Ações: fold, check, call, bet, raise e all-in, com **side pots**.
  - Avaliação de mãos completa: carta alta → royal flush, com kickers. Empates dividem o pote (o resto vai para o primeiro a seguir ao botão).
- **Servidor autoritativo:**
  - baralho embaralhado com `secrets.SystemRandom` por mão;
  - as cartas fechadas **só vão para o próprio jogador** (WS por utilizador; o snapshot de cada jogador esconde as cartas dos outros até ao showdown);
  - os outros jogadores e os espectadores nunca veem cartas fechadas;
  - registo completo de cada mão (`poker_hands` + `poker_actions`) para auditoria do professor.
- **Mesas:**
  - `poker_tables (id, class_id, name, max_seats 2–10, small_blind, big_blind, state)` e `poker_seats (table_id, seat, user_id, stack, status: sitting|sitting_out|away)`.
  - Uma mão começa quando há ≥ 2 jogadores sentados e ativos (pausa de 5 s entre mãos).
  - **Sentar** = buy-in: retira o valor do saldo e coloca-o no `stack`, com um registo `poker_net` negativo provisório? **Não.** O buy-in fica reservado (`poker_seats.stack`) e **só no fim de cada mão** se escreve `poker_net = stack_final - stack_inicial` para cada jogador, numa **transação única por mão** (a soma dos `poker_net` de uma mão é sempre 0).
  - Levantar-se devolve o stack (sem registo extra, porque o líquido já foi escrito mão a mão).
- **Tempo e rede:**
  - 30 s por ação. Ao expirar: **check** se possível, senão **fold**.
  - Quem desliga fica `away`: faz auto-fold nas mãos seguintes e, ao fim de 2 mãos, `sitting_out`.
  - Reconexão com o snapshot (padrão `seq`/replay do torneio).
- **Concorrência:** um *advisory lock* por mesa em cada ação; ações idempotentes por `action_id` do cliente; uma tarefa de fundo trata os temporizadores (como o fecho automático do torneio).
- **API:**
  - `GET /api/extra/settings`; `PATCH /api/extra/settings` (professor: `poker_enabled`, `poker_source`, limites);
  - `GET /api/extra/poker/tables` (da turma); `POST /api/extra/poker/tables` (professor, ou aluno se o professor permitir: omissão sim, até 4 mesas por turma);
  - `POST /api/extra/poker/tables/{id}/sit {seat, buy_in}`, `POST …/leave`, `POST …/action {action_id, type, amount?}`;
  - `GET /api/extra/poker/tables/{id}/state` (snapshot com as **minhas** cartas);
  - `GET /api/extra/poker/me` (saldo disponível, perda de hoje, aceitou o opt-in?), `POST /api/extra/poker/consent`;
  - professor: `GET /api/extra/poker/hands?table=` (histórico com todas as cartas, para auditoria).
- **WS:** `GET /ws/extra/poker/{table_id}`, com os eventos `hand_started`, `hole_cards` (só para o próprio), `action`, `street` (flop/turn/river, com as cartas comunitárias), `showdown` (cartas reveladas + mãos + vencedores), `pot_awarded`, `seat_changed`, `turn` (de quem é a vez + prazo do servidor).
- **Testes:**
  - avaliação de mãos (todas as categorias, kickers, empates, rodas A-2-3-4-5);
  - side pots com 3+ all-ins;
  - a soma de `poker_net` por mão = 0;
  - nunca há cartas de outros no snapshot nem no WS;
  - os limites (buy-in, perda diária, saldo 0);
  - o timeout faz check/fold;
  - ações fora de vez são recusadas;
  - idempotência;
  - privacidade entre turmas.

## 3. Bit a Bit (backend T)
- **Partida:** `POST /api/extra/bitabit/start` → `{game_id, seed, config}`. O servidor gera uma **seed** e regista a partida.
- **Jogo:** a sequência de linhas é **determinística a partir da seed** (o mesmo gerador em Python e em JS, especificado aqui: PRNG `mulberry32(seed)`). Cada linha é um de dois tipos:
  - **"bin→dec"**: bits dados; o aluno escreve o número;
  - **"dec→bin"**: número dado; o aluno liga os bits.

  Os níveis aumentam a velocidade e o número de bits (nível 1: 4 bits; nível 3+: 8 bits).
- **Fim:** `POST /api/extra/bitabit/{game_id}/finish {answers:[{row, value, t_ms}], score}`. O servidor **recalcula** a sequência pela seed, valida cada resposta e o tempo mínimo plausível (≥ 300 ms por linha), recalcula a pontuação e ignora a enviada se divergir. Atribui `bitabit` (com o limite diário) e devolve `{score, points_awarded, best, today_remaining}`.
- **Recordes:** `GET /api/extra/bitabit/leaderboard` (top da turma, por recorde de pontuação; aplica a flag de privacidade só no público, como hoje).
- **Testes:** a seed reproduz a sequência igual em Python e JS (vetor de teste partilhado em `backend/tests/fixtures/bitabit_vectors.json`, usado também pelo frontend), respostas forjadas recusadas, limite diário, tempo impossível recusado.

## 4. Frontend
- **Aba "Extra":**
  - item novo na navegação (ícone de cartas/joystick, `nav.extra`) → `pages/extra/extra.html`, uma página hub com 2 cartões grandes (Poker e Bit a Bit), o saldo de poker, os pontos Bit a Bit de hoje (x/50), os recordes e as regras resumidas;
  - o professor vê as definições da turma (ligar/desligar o poker, fonte dos pontos, limites).
- **Poker (P):** `pages/extra/poker/`:
  - lista de mesas (criar mesa) → **mesa pixel art**: feltro verde em pixel, 2–10 lugares em elipse com avatar e stack em fichas pixel, cartas pixel originais (naipes desenhados em pixel), pote ao centro com side pots, as minhas cartas em destaque;
  - botões grandes Fold / Check-Call / Bet-Raise com slider + botões ½ pote, pote e all-in, com temporizador da vez;
  - animações GSAP (distribuir cartas, fichas a voar para o pote e para o vencedor), histórico curto das ações;
  - mobile first: no telemóvel, a mesa compacta com os lugares à volta e os botões em baixo;
  - o ecrã de opt-in no primeiro acesso;
  - no fim de cada mão, um toast "+12 pts" / "−8 pts".
- **Bit a Bit (B):** `pages/extra/bitabit/`:
  - grelha pixel com as colunas 128 … 1 (ou menos bits nos níveis baixos);
  - as linhas sobem de baixo e o jogo acaba se chegarem ao topo;
  - em cada linha, bits clicáveis (toque) **ou** um campo decimal;
  - painel com pontuação, nível e linhas restantes;
  - botões Pausa, Som e Terminar; sons chiptune opcionais, desligados por omissão;
  - teclado: setas para escolher o bit, Espaço para alternar, números + Enter para o decimal;
  - visual **original** em pixel art e com o tema ativo, que **não** imita a imagem de referência (cores, tipografia e layout próprios).
- **i18n:** áreas novas `extra` (hub + poker + bitabit, prefixos `hub.*`, `poker.*`, `bit.*`) e `extra_api` (erros do backend), registadas em `frontend/i18n/areas.json` (o orquestrador já as cria vazias).

## 5. Campus 3D (D)
- **Hotspot "Atividades extra"** no **pavilhão desportivo** (o edifício ao lado do campo de futebol, a oeste) → `/pages/extra/extra.html`.
  - Um pequeno detalhe voxel à porta: uma mesa com cartas e um painel de bits luminoso.
  - Também no poster 2D.
- **Sprites novos** (`gen_assets.py`, originais):
  - cartas: frente com naipes ♠♥♦♣ e valores em pixel, e verso com o emblema PyArena;
  - fichas em 5 cores;
  - ícone da aba Extra;
  - ícones dos dois jogos.

## 6. Quem é dono de que ficheiros
- **T:** `backend/app/{models,services,api}/extra*.py` (+ `poker_engine.py`, `bitabit.py`), a migração `0006`, os testes, `backend/tests/fixtures/bitabit_vectors.json`, `frontend/i18n/extra_api/*`, as alterações mínimas em `services/leaderboard.py`/`points.py` para as razões novas.
- **P:** `frontend/pages/extra/poker/**`, `frontend/components/extra/poker/**`, `frontend/i18n/extra/*` (só chaves `poker.*`; editar com cuidado).
- **B:** `frontend/pages/extra/bitabit/**`, `frontend/components/extra/bitabit/**` (o PRNG `mulberry32` em JS, igual ao Python), `frontend/i18n/extra/*` (só `bit.*`).
- **D:**
  - `frontend/pages/extra/extra.html|extra.js` (hub);
  - `components/bottom-nav.js` (item Extra);
  - `scenes/campus/**`, `assets/gen_assets.py` + os sprites;
  - `styles/app.css` (só acrescentar, numa secção `/* extra (D) */`; P e B acrescentam secções suas `/* poker (P) */` e `/* bitabit (B) */`);
  - `frontend/i18n/extra/*` (só `hub.*`) e `frontend/i18n/home/*` (`nav.extra`).
