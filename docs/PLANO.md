# PyArena — jogo competitivo de algoritmia em Python (Programação I)

## Contexto
Um professor de Programação I (Python) quer um jogo que motive os alunos de forma competitiva e saudável:
1. **Modo Treino (individual, em casa):** desafios aleatórios com dificuldade progressiva, XP, níveis e conquistas.
1b. **Modo Algoritmia (estilo LeetCode):** níveis Hard / Extra Hard / Hardcore Insane, que correspondem a LeetCode Easy / Medium / Hard.
2. **Modo Duelo (1 vs 1):** desafio direto a um colega por código de convite, com rating ELO.
3. **Modo Torneio (em aula, ~20 alunos):** fase de grupos + eliminatórias, problemas cada vez mais difíceis, ranking ao vivo projetado na sala.

Decisões tomadas: web app **alojada online** (casa + aula), **editor no browser + testes automáticos no servidor**, torneio **grupos + eliminatórias**, **banco inicial de ~30 problemas** + o professor acrescenta. Frontend o **mais leve possível no cliente** e com **estrutura de pastas clara**. A **rede da aula pode falhar várias vezes** → tempo real por WebSocket com reconexão e nada se perde.
Pasta vazia (greenfield). **Tudo corre em Docker Compose na VM do professor.** O Python 3.9 local não importa, porque as imagens usam Python 3.12.

## Stack
- **Backend:** FastAPI (API JSON + WebSocket) + SQLModel + asyncpg. PostgreSQL em dev e em produção.
- **Frontend (web + mobile, mobile first):** HTML + **Tailwind CSS v4** (compilado pelo binário standalone dentro do Docker) + **JavaScript simples com módulos ES nativos**, sem framework nem build de JS (o mais leve no cliente: só se descarrega o que cada página usa). Editor: **CodeMirror 6** (único peso extra, carregado só na página do desafio). Servido como ficheiros estáticos pelo FastAPI.
- **Deploy:** só Docker Compose na VM do professor (ver a secção "Tudo em Docker").

## Estrutura de pastas
```
pyarena/
├── backend/
│   ├── app/
│   │   ├── main.py              # cria a app, monta rotas e frontend estático
│   │   ├── config.py            # definições (env vars)
│   │   ├── db.py                # ligação à base de dados
│   │   ├── models/              # user.py, problem.py, submission.py, tournament.py, badge.py
│   │   ├── api/                 # rotas HTTP: auth.py, practice.py, problems.py, tournament.py, admin.py
│   │   ├── realtime/
│   │   │   ├── hub.py           # gere ligações WebSocket por torneio (salas)
│   │   │   └── events.py        # tipos de eventos enviados (round_started, score_update, …)
│   │   ├── services/            # lógica de jogo: xp.py, matchmaking.py, bracket.py, scoring.py
│   │   └── runner/
│   │       ├── sandbox.py       # corre código do aluno isolado
│   │       └── harness.py       # corre o programa com stdin de cada teste e compara o stdout
│   ├── problems/                # 1 ficheiro YAML por problema (+ solução de referência)
│   └── tests/
├── frontend/
│   ├── index.html               # entrada: login / escolha de modo
│   ├── pages/                   # 1 HTML + 1 JS por ecrã
│   │   ├── practice/            # practice.html, practice.js   (modo treino)
│   │   ├── duel/                # duel.html, duel.js           (modo duelo 1v1)
│   │   ├── challenge/           # challenge.html, challenge.js (editor + submissão)
│   │   ├── tournament/          # tournament.html, tournament.js (vista do aluno)
│   │   ├── projector/           # projector.html, projector.js (bracket/ranking para projetar)
│   │   ├── admin/               # admin.html, admin.js (painel do professor)
│   │   ├── leaderboard/         # leaderboard.html, leaderboard.js (rankings + pódio 3D)
│   │   └── profile/             # profile.html, profile.js (XP, nível, conquistas)
│   ├── scenes/                  # cenas Three.js carregadas a pedido (lobby, pódio, rank-up, bracket, versus)
│   ├── vendor/                  # three.module.min.js (versão fixa)
│   ├── components/              # peças reutilizáveis em JS: editor.js, leaderboard.js,
│   │                            # bracket.js, timer.js, toast.js, connection-status.js
│   ├── services/
│   │   ├── api.js               # fetch com retry automático
│   │   ├── socket.js            # WebSocket com reconexão
│   │   ├── storage.js           # rascunhos e fila offline em localStorage
│   │   └── auth.js              # token/sessão
│   ├── i18n/                    # pt-PT.json, en.json (todas as strings da interface)
│   ├── styles/                  # tokens.css, base.css, layout.css, components.css, themes/<tema>.css
│   └── assets/                  # sprites/ (ranks, conquistas, avatares, moedas), fonts/, sfx/
├── docker-compose.yml
├── Dockerfile
└── README.md                    # explica cada pasta
```
Regra simples: **pages** = ecrãs, **components** = peças visuais reutilizáveis, **services** = comunicação com o servidor/armazenamento. Cada ficheiro curto e com comentário no topo a explicar o que faz.

## Web + mobile (mobile first, com Tailwind)
- **Tailwind CSS v4 através do binário standalone** (sem Node). Um *stage* do `Dockerfile` corre `tailwindcss -i frontend/styles/app.css -o frontend/dist/app.css --minify` e lê as classes usadas nos `.html`/`.js`. Em desenvolvimento, um serviço `css` no `docker-compose.override.yml` corre `--watch`. A VM continua a precisar só de Docker, e o JS continua sem build.
- **Tokens pixel art no Tailwind:** a paleta, as fontes, as bordas em degrau e as sombras são definidas no `@theme` do `app.css` a partir das variáveis CSS dos temas. Assim, `bg-surface`, `text-accent`, `shadow-pixel` e `font-pixel` mudam automaticamente com o tema ativo. Componentes repetidos (`.btn-pixel`, `.panel-pixel`, `.xp-bar`) ficam em `@layer components`, para o HTML não ficar ilegível.
- **Mobile first:** os estilos base são para ~360 px e alargam com `sm:`/`md:`/`lg:`.
  - **Navegação:** barra inferior com 5 ícones pixel no telemóvel (Mundo, Duelo, Torneio, Ranking, Perfil); barra lateral em `lg:`.
  - **Editor no telemóvel:** ecrã com separadores **Enunciado | Código | Resultado**, em vez de colunas lado a lado. Por cima do teclado há uma **barra de símbolos Python** (`:` `(` `)` `[` `]` `"` `=` `#` e tecla Tab/indentar), porque escrever indentação no teclado do telemóvel é difícil. O CodeMirror funciona com toque.
  - **Toque:** alvos com pelo menos 44 px, `100dvh` (sem saltos com a barra do browser), `safe-area-inset` em iPhones e nada que dependa de *hover*.
  - **Duelo/torneio no telemóvel:** o progresso do adversário passa a uma barra fina no topo e o temporizador fica sempre visível.
  - **Ecrã projetor e painel do professor:** pensados para desktop, mas utilizáveis em tablet.
- **PWA instalável:** `manifest.webmanifest` + o service worker já previsto. O aluno pode "Adicionar ao ecrã principal" e abrir como app, com ícone pixel e ecrã inicial.
- **3D no telemóvel:** resolução interna ainda mais baixa, 30 FPS e versão 2D por omissão quando a poupança de bateria está ativa ou em dispositivos fracos.
- **Ficheiros:** `frontend/styles/app.css` (entrada do Tailwind + `@theme` + `@layer components`), `frontend/dist/` (gerado, no `.gitignore`), `frontend/components/symbol-bar.js`, `frontend/components/bottom-nav.js` e `frontend/manifest.webmanifest`.

## Bilingue: português de Portugal 🇵🇹 + inglês 🇬🇧 (obrigatório)
- **Idioma por omissão:** PT-PT. No primeiro acesso usa-se o idioma do browser (`navigator.language`) e depois a escolha do aluno, guardada no perfil (`User.locale`) e no localStorage. Há um seletor 🇵🇹/🇬🇧 no cabeçalho e no perfil, e a mudança de idioma não recarrega a página.
- **Frontend:** nenhum texto fixo no HTML/JS. Todas as strings passam por `t("chave")` (`frontend/services/i18n.js`, ~1 KB, sem biblioteca) a partir de `frontend/i18n/pt-PT.json` e `frontend/i18n/en.json`. O HTML usa `data-i18n="chave"`. Datas e números são formatados com `Intl` (PT: `12,5` e `14/11/2026`; EN: `12.5` e `11/14/2026`).
- **Backend:** as respostas da API e os eventos WebSocket levam **códigos/chaves**, não frases (ex. `{"error": "duel.invite_expired"}`). Quem traduz é o cliente. Os únicos textos traduzidos no servidor são os conteúdos (problemas, conquistas, regiões, nomes de ligas) e os diplomas em PDF.
- **Problemas bilingues:** os campos de texto do YAML passam a ter as duas línguas (`titulo: {pt: ..., en: ...}`, e o mesmo para `enunciado`, `pistas` e `erros_comuns.mensagem`). **Os outputs de texto também dependem da língua** (`stdout: {pt: "Vai a andar", en: "Walk"}`). Os outputs numéricos são comuns às duas línguas. Cada aluno resolve na sua língua, e num duelo cada um vê o enunciado no seu idioma. Há uma solução de referência por língua quando o texto do output muda.
- **Conteúdo do jogo:** regiões, ligas, conquistas, temas, power-ups e honras ficam em `backend/content/*.yaml`, com `pt`/`en`.
- **Qualidade:** o teste `check_i18n` falha se faltar alguma chave numa das línguas (JSON ou YAML). O validador de problemas corre as duas versões. O PT é sempre de Portugal (ecrã, utilizador, ficheiro, guardar), nunca PT-BR.
- **Ficheiros:** `frontend/i18n/` (pasta nova), `frontend/services/i18n.js`, `frontend/components/lang-switch.js`, `backend/app/i18n.py` (escolhe o texto do conteúdo pelo `locale`) e `backend/app/tools/check_i18n.py`.

## Resiliência a falhas de rede (aula)
- **WebSocket** para empurrar eventos do torneio (início de ronda, pontuações, avanço de fase) — instantâneo e menos tráfego do que polling com 20+ alunos.
- `socket.js`: reconexão automática com backoff (1 s, 2 s, 4 s… até 10 s); a cada reconexão o cliente pede **snapshot completo do estado** (`GET /tournament/{id}/state`), por isso eventos perdidos não importam. Se o WebSocket não ligar de todo, cai para polling a cada 5 s.
- Indicador visível "🟢 ligado / 🟡 a reconectar / 🔴 offline" (`connection-status.js`).
- **Código nunca se perde:** rascunho guardado em localStorage a cada tecla (debounce).
- **Submissões com ID único** (gerado no cliente): se a rede falhar, ficam numa fila e são reenviadas; o servidor ignora duplicados (idempotência).
- **Temporizador definido pelo servidor:** enviado como hora de fim absoluta; o cliente conta localmente mesmo offline. Submissões criadas antes do fim mas entregues até 30 s depois (período de tolerância) são aceites, com o tempo do servidor a decidir dentro desse limite.
- Professor pode **pausar/prolongar** uma ronda se a rede cair para toda a turma.

### Estado da ligação no PostgreSQL (sem Redis)
Uma ligação WebSocket é uma ligação TCP viva dentro de um processo e não pode ser guardada. O que se guarda é **o estado à volta dela**, e o PostgreSQL faz isso nativamente sem precisar de outro contentor:
- **Registo de eventos:** tabela `tournament_events (seq BIGSERIAL, tournament_id, type, payload, created_at)`. Ao reconectar, o cliente envia o último `seq` que viu e recebe só os eventos em falta (`WHERE seq > :last`). Se faltarem demasiados, recebe o snapshot completo.
- **Pub/Sub entre processos:** `LISTEN/NOTIFY` (via `asyncpg.add_listener`). O `NOTIFY` leva apenas o `seq` (o payload tem limite de 8 KB) e cada worker lê o evento e envia-o aos seus sockets. Funciona com vários workers e sobrevive a reinícios.
- **Presença por utilizador:** `UNLOGGED TABLE presence (user_id, tournament_id, last_seen, last_seq)`, com heartbeat a cada 15 s. O professor vê quem caiu.
- **Fila do runner:** tabela `jobs` consumida com `SELECT … FOR UPDATE SKIP LOCKED`. Se o runner reiniciar, as submissões ficam na fila.
- **Rate limiting:** contagem de submissões recentes por aluno (índice em `submissions(user_id, created_at)`).
Ficheiros: `backend/app/realtime/pg_bus.py` (LISTEN/NOTIFY + replay), `backend/app/realtime/presence.py`, `backend/app/runner/queue.py`.
O Redis só passaria a fazer sentido com centenas de utilizadores ao mesmo tempo ou com vários servidores. A interface do `pg_bus.py` fica isolada para facilitar essa troca no futuro.
Em desenvolvimento usa-se PostgreSQL via docker-compose (e não SQLite), porque o LISTEN/NOTIFY depende dele.

## Design gamificado + Three.js
- **Skill de design:** usar o plugin **frontend-design** (Anthropic) para definir a identidade visual. O plugin **parallax-threejs** é opcional e serve para depurar cenas 3D. Antes da fase de frontend, o Opus corre a skill e cria `frontend/styles/tokens.css` (cores, tipografia, espaçamentos, raios, sombras e "glow"), que todos os subagentes passam a seguir.
- **Estilo: pixel art retro**, com identidade original (não copiar nenhum jogo existente):
  - **Paleta limitada própria** de ~16 cores, definida em `tokens.css`, com uma cor por rank (Bronze, Prata, Ouro, Platina, Diamante).
  - **Tipografia:** fonte pixel com licença OFL (ex. "Press Start 2P") para títulos, botões e números, e uma fonte pixel mais legível (ex. "VT323" ou "Pixelify Sans") para texto curto. **Os enunciados e o editor de código mantêm uma fonte monoespaçada normal**, porque a legibilidade vem primeiro.
  - **Interface:** caixas com borda de 2 a 4 px em "degrau" (`box-shadow` em escada, sem cantos arredondados), botões que "afundam" 2 px ao clicar, barras de XP segmentadas em blocos, cursor pixelado e `image-rendering: pixelated` em todas as imagens.
  - **Sprites:** ícones de rank, conquistas, avatares (o aluno escolhe e combina cabeça, cor e acessório) e moedas de XP em sprite sheets PNG pequenos (16×16 / 32×32), desenhados de propósito para o projeto.
  - **Micro-animações** feitas com `steps()` do CSS (animação por frames, não suave): moedas a saltar, estrelas ao resolver um problema e texto "+50 XP" a subir. Efeitos sonoros chiptune curtos e opcionais (desligados por omissão).
- **Three.js em estilo pixel art 3D** (*voxels* + pixelização): os modelos são voxels low-poly e a cena é renderizada a baixa resolução (ex. 320×180) e depois ampliada com `NearestFilter`, como em `RenderPixelatedPass` dos *addons* do three.js. As texturas usam `NearestFilter` e a paleta é a mesma dos tokens. O resultado parece pixel art, mas com profundidade e câmara a mexer.
- **Temas pixel art rotativos** (todos originais):
  - **Temas iniciais:** 🌲 Floresta, 🏰 Masmorra, 🌊 Oceano, 🏜️ Deserto, ❄️ Neve, 🌌 Noite Estrelada.
  - **Cada tema tem:** paleta própria (as variáveis CSS mudam via `<html data-theme="floresta">`), fundo em *tile* pixelado, moldura das caixas e uma variante das cenas 3D (bioma da ilha do lobby, materiais do pódio e cenário do mapa do torneio). A estrutura e as cores dos ranks não mudam, para manter tudo reconhecível.
  - **Comportamento:** em cada visita sorteia-se um tema diferente do anterior. No **Perfil** o aluno pode escolher **"Fixar tema"** (guardado no servidor, campo `preferred_theme` no `User`), e esse tema passa a valer em todos os dispositivos. Também se pode voltar a "Aleatório".
  - **Sem flash:** um script pequeno no `<head>` aplica o tema antes de desenhar a página, a partir do localStorage (cópia da preferência ou do último sorteio), e depois confirma com o servidor.
  - **Extra de gamificação (opcional):** alguns temas só se desbloqueiam ao chegar a um rank, por exemplo Noite Estrelada no rank Diamante.
  - **Ficheiros:** `frontend/styles/themes/<tema>.css` (só variáveis), `frontend/services/theme.js` (sorteio, fixar, aplicar), `frontend/scenes/themes.js` (configuração 3D por tema), `frontend/assets/sprites/themes/<tema>/` (tiles e molduras) e o endpoint `PATCH /me/preferences`.
  - **Adicionar um tema novo** = 1 ficheiro CSS + 1 entrada em `themes.js` + tiles. Fica documentado no README.
- **Three.js só onde dá impacto, e carregado apenas nessas páginas** (import map com `three.module.min.js` + addons em `frontend/vendor/`, sem build):
  - **Lobby:** uma pequena ilha/castelo de voxels a rodar devagar, com nuvens pixeladas, no fundo do ecrã inicial.
  - **Subida de rank:** baú de voxels que abre e revela o emblema do novo rank, com partículas quadradas.
  - **Leaderboard / pódio:** pódio de voxels com os avatares pixel dos 3 primeiros e a tabela em HTML por baixo.
  - **Projetor do torneio:** bracket como um "mapa de mundo" em voxels com caminhos entre os duelos, câmara que viaja até ao duelo atual e pódio final com fogo de artifício pixelado.
  - **Duelo:** ecrã "VS" de 3 s com os dois avatares frente a frente antes de cada problema.
- **Leveza e acessibilidade:** cada cena é um módulo em `frontend/scenes/` que se carrega com `import()` dinâmico só quando é preciso. A cena para quando o separador fica escondido e respeita `prefers-reduced-motion`. Em dispositivos fracos, ou se o WebGL falhar, usa-se uma versão 2D em CSS. A página do editor **nunca** carrega Three.js, para não atrapalhar quem está a programar.
- Pastas novas: `frontend/scenes/` (`lobby-arena.js`, `rank-up.js`, `podium.js`, `bracket-3d.js`, `versus.js`, e `scene-base.js` com renderer, resize e pausa comuns) e `frontend/vendor/` (three.js com versão fixa).

## Inspiração de jogos (mecânicas, não cópia)
Tiramos ideias de géneros que os alunos conhecem, com nomes, arte e som 100% originais. Nada de nomes, personagens, logótipos, fontes, música ou visual reconhecível de LoL, GTA ou Zelda.

**Aventura com mundo aberto, mapa e masmorras (estilo Zelda) → Modo Treino como "Mundo"**
- O treino é um **mapa-mundo em pixel art** com as regiões do `curriculum.yaml`, pela ordem das tuas aulas: 🏘️ Vila dos Algoritmos → 🌲 Floresta Sequencial → 🏪 Mercado da Decomposição → 🔀 Encruzilhada das Decisões → 🌊 Rio dos Ciclos → 🗼 Torre das Funções → 🏰 Cidadela dos Vetores → 🌌 Ilhas Distantes ("mais além").
- Cada região tem **santuários** (problemas curtos e aleatórios) e uma **masmorra** no fim: 3 problemas seguidos em que o último é o "boss".
- **Corações = vidas** na masmorra (cada submissão errada tira ½ coração). Se ficares sem corações, voltas à entrada mas não perdes XP.
- Vencer o boss dá uma **relíquia** (item colecionável) que **desbloqueia a região seguinte**. Os santuários continuam disponíveis para farmar XP.

**Missões de cidade e estrelas de dificuldade (estilo GTA) → Desafios diários e "Contratos"**
- Um quadro de **contratos** com 3 desafios aleatórios por dia, com dificuldade de ★ a ★★★★★ e uma recompensa em **moedas**.
- **Ofertas relâmpago:** contratos com bónus ×2 durante 1 hora (por exemplo, ao fim de semana).
- **Ecrã de "missão concluída" original:** faixa pixel com o nome do contrato, tempo, tentativas e moedas ganhas.
- As **moedas** compram cosméticos (peças de avatar, molduras de perfil, efeitos de vitória). Nada que dê vantagem no jogo.

**Ranked competitivo (estilo LoL) → Duelo e Torneio ranked**
- **Ligas e divisões próprias:** Madeira → Pedra → Ferro → Cristal → Rubi → Lendário, cada liga com divisões IV→I. Promoção a uma nova liga só depois de **série de promoção** (ganhar 2 de 3 duelos).
- **Temporadas** por período letivo. No fim da temporada há recompensas (moldura com o emblema da liga) e um *soft reset* do rating.
- **Ecrã de "seleção" antes do duelo:** cada jogador escolhe 1 **power-up** de entre 3, todos justos e simétricos (ex. "ver 1 teste escondido", "+60 s num problema", "dica de complexidade"), com 15 s para escolher.
- **Honras pós-jogo:** depois de um duelo ou de um torneio, cada um pode dar "👏 Bom adversário", "🧠 Solução elegante" ou "🤝 Fair play". As honras aparecem no perfil e reforçam o lado saudável.
- **Lanes do torneio:** no ecrã do projetor, a fase de grupos aparece como um mapa com "lanes" (um grupo por lane) e as eliminatórias como o caminho até à "base" final.

Relação com o resto do plano: os **ranks de treino** (XP) passam a ser os níveis de aventura, e as **ligas** (ELO) ficam para Duelo/Torneio. Os **temas** são as regiões do mapa-mundo. Novos ficheiros: `backend/app/services/world.py` (regiões, santuários, masmorras, relíquias), `services/contracts.py`, `services/economy.py` (moedas, loja), `services/seasons.py`, `services/honors.py`, `frontend/pages/world/`, `frontend/pages/shop/`, `frontend/scenes/world-map.js` (mapa de voxels navegável) e `backend/content/world.yaml` (regiões e ligação aos problemas).

## Leaderboard (motivação para progredir)
- **Separadores:** Turma (XP total), **Semanal** (XP desta semana, recomeça à segunda-feira para quem chegou tarde também poder ganhar), Ranked (liga/divisão da temporada), Torneios (pódios/vitórias) e Honras.
- **Pódio 3D** com o top 3. Linhas animadas quando alguém sobe ou desce (setas ▲▼ e animação FLIP). A linha do próprio aluno fica sempre fixa e visível, mesmo que esteja em 18.º.
- **Ganchos de progresso:** "Faltam 40 XP para passares o João", "Subiste 3 posições esta semana", e uma toast em tempo real (via WebSocket) quando alguém da turma te ultrapassa.
- **Competição saudável:** também há destaques para "Maior evolução da semana" e "Mais persistente" (dias de streak), para não ser só o top a brilhar. O professor pode esconder nomes (pseudónimos) ou ocultar a parte de baixo da tabela.
- Ficheiros: `backend/app/api/leaderboard.py`, `backend/app/services/leaderboard.py` (consultas com índices + cache de 10 s), `frontend/pages/leaderboard/`, `frontend/components/leaderboard.js` (o mesmo componente é usado no torneio e no projetor).

## Tudo em Docker (corre na tua VM com `docker compose up -d`)
**Requisito obrigatório:** a VM só precisa de Docker + Docker Compose. Não é preciso Python, Node nem `uv` instalados no anfitrião, e não há nenhum serviço externo (sem CDN, sem cloud).

`docker-compose.yml`:
| Serviço | Imagem | Função |
|---|---|---|
| `proxy` | `caddy:2` | Porta 80/443 com HTTPS automático (ou só HTTP em rede local); faz *proxy* de HTTP e WebSocket para a app |
| `app` | build `backend/Dockerfile` (Python 3.12-slim) | FastAPI (API + WebSocket) e serve o `frontend/` estático; corre migrações ao arrancar |
| `runner` | build `runner/Dockerfile` | Executa o código dos alunos |
| `db` | `postgres:16` | Dados, eventos, filas e presença; volume `pgdata` persistente |
| `backup` | `postgres:16` | `pg_dump` diário para o volume `./backups` (7 dias de retenção) |

- **Redes:** `public` (proxy ↔ app), `internal` (app ↔ db) e `sandbox` (`internal: true`, apenas app ↔ runner). **O runner não tem acesso à internet nem à base de dados.** A app tira os trabalhos da fila no Postgres e envia-os ao runner por HTTP na rede `sandbox`.
- **Runner endurecido:** `read_only: true`, `tmpfs /tmp`, `user: nobody`, `cap_drop: [ALL]`, `security_opt: no-new-privileges`, `pids_limit`, `mem_limit`, `cpus`. Cada submissão corre num subprocesso com ambiente vazio, `setrlimit` e timeout.
- **Robustez:** `restart: unless-stopped` em todos os serviços, `healthcheck` na app, na db e no runner, e `depends_on: condition: service_healthy`.
- **Configuração:** `.env.example` → `.env` (palavra-passe da BD, segredo de sessão, domínio para o Caddy, conta inicial do professor).
- **Sem dependências externas no cliente:** three.js, CodeMirror e as fontes ficam em `frontend/vendor/`, com versões fixas. Isto também ajuda quando a internet da escola falha, porque só é preciso chegar à VM.
- **Desenvolvimento também em Docker:** `docker-compose.override.yml` monta o código como volume com `--reload`.
- **Comandos (todos via compose):**
  - `docker compose up -d --build`: arranca tudo
  - `docker compose run --rm app pytest`: testes
  - `docker compose run --rm app python -m app.tools.validate_problems`: valida o banco de problemas
  - `docker compose logs -f app`: logs
  - `docker compose exec db psql -U pyarena`: consola da BD
- Pastas novas na raiz: `runner/` (Dockerfile + `server.py` mínimo, com o sandbox e o harness movidos para aqui), `deploy/Caddyfile`, `backups/` (no `.gitignore`).

## Exercícios baseados nas aulas do professor ("e mais além")
**Materiais analisados** (atualmente na raiz do projeto; na fase 0 passam para `materiais_aulas/`, que fica no `.gitignore` e nunca é servida aos alunos): Aula I (apresentação + programa), Aula II e III (algoritmos, fluxogramas, Portugol→Python, tipos, operadores, programa sequencial, ex. 3.1–4.3), Aula 3.5 "Operação Decomposição", Aula IV (condicionais, 5 nov) e PDF "Estruturas de Repetição" (`for`/`while`).

**O que os materiais mostram, e que o jogo tem de respeitar:**
- **Nas aulas I–V os alunos escrevem programas completos com `input()` e `print()`.** Os problemas dos blocos 2–5 são **corrigidos por stdin/stdout** (ver Formato). Os do bloco 6 (funções, já dado) são corrigidos com chamadas à função.
- **Convenções do professor:** variáveis declaradas e inicializadas no topo antes de ler (`numero = 0`), constantes em MAIÚSCULAS (`NOTA_MINIMA = 10`), nomes em português e snake_case, estrutura input → processamento → output com comentários, e fluxograma + Portugol + Python lado a lado.
- **Erros que o professor destaca:** prioridade de operadores (média sem parênteses), `/` vs `//`, `input()` devolve texto, off-by-one no `range`, acumulador não inicializado e ciclo infinito. Estes erros ganham **mensagens de feedback específicas** (ex. "O teu resultado é 26.0 mas esperava-se 14.0. Lembra-te que a divisão tem prioridade sobre a soma").
- **Tom:** humor do dia a dia (o gato que ataca o tornozelo, "ainda dá para um café", o foguetão, o pato de borracha). Os enunciados novos seguem este estilo.

**`backend/content/curriculum.yaml`** (escrito pelo Opus a partir dos materiais) — blocos pela ordem do curso, cada um com os conceitos permitidos:
| # | Bloco (aula) | Conceitos permitidos | Região do mapa |
|---|---|---|---|
| 1 | Algoritmos e fluxogramas (I–II) | sem código: problema, entrada/saída, passos | 🏘️ Vila dos Algoritmos |
| 2 | Processamento sequencial (II–III) | `input`, `int`, `float`, `print`, `+ - * / // % **`, prioridade, `math.sqrt`/`math.pi`, `round`, `\n \t`, troca com `aux` | 🌲 Floresta Sequencial |
| 3 | Decomposição (3.5) | entradas, variáveis, constantes, operação | 🏪 Mercado da Decomposição (a "Loja XPTO") |
| 4 | Condicionais (IV) | `== != < > <= >=`, `and or not`, De Morgan, `if/elif/else`, aninhados | 🔀 Encruzilhada das Decisões |
| 5 | Repetição (V) | `for` + `range`, `while`, contadores, acumuladores, validação de input, máximo/mínimo | 🌊 Rio dos Ciclos |
| 6 | **Funções (já dado, nov. 2026)** | `def`, parâmetros, `return`, decomposição top-down; recursividade fica num sub-bloco 6b, que só abre quando o professor o marcar como dado | 🗼 Torre das Funções |
| 7 | **Listas (já dado)** + matrizes | listas, indexação, percorrer, `append`, `len`, ordenação, pesquisa; matrizes (listas de listas) num sub-bloco 7b, que abre quando o professor o marcar como dado | 🏰 Cidadela dos Vetores |
| + | **Mais além** (opcional) | strings avançadas, dicionários, complexidade, pesquisa binária, recursão avançada, programação dinâmica | 🌌 Ilhas Distantes |
**Os blocos 1–7 estão abertos** (funções e listas já foram dadas). Só a recursividade (6b) e as matrizes (7b) ficam bloqueadas até o professor as marcar como dadas no painel. Ainda não há slides da aula de funções. Se o professor os puser em `materiais_aulas/`, o Opus ajusta o bloco 6 ao estilo dessa aula. Até lá, segue o programa da Aula I ("funções e procedimentos, parâmetros") e as convenções das aulas anteriores.
**Com as funções já dadas**, o banco inclui desde o início problemas do tipo `funcao` (ex. `def calcular_media(nota1, nota2, nota3)`, `def e_aprovado(media)`, `def converter_kmh_ms(kmh)`) e problemas de **refatorização**: pegar num programa dos blocos 2–5 e dividi-lo em funções, ligando à abordagem top-down das aulas.

**Tipos de desafio** (adequados a cada fase do curso, e não só "escrever código"):
1. **Programa** (blocos 2–7): escrever o programa completo; corrigido com stdin/stdout.
2. **Decomposição** (bloco 3, igual à tua aula): dado um enunciado, identificar entradas, variáveis, constantes e operação, em escolha múltipla ou arrastar etiquetas.
3. **Traçar** (blocos 4–5, como o "Vamos Traçar o Ciclo"): prever o output ou o valor das variáveis no fim de cada iteração.
4. **Caça ao bug** (blocos 2–5): corrigir um programa com um erro clássico (ciclo infinito, off-by-one, parênteses, `input` sem `int`).
5. **Função** (blocos 6+): escrever `def ...`, corrigido com chamadas à função.
6. **Quiz relâmpago** (todos os blocos, como as pausas Fuiz): perguntas rápidas de conceitos (tabelas de verdade, De Morgan, tipos).

**Pistas (mecânica da tua aula de decomposição):** cada problema tem até 2 pistas. A pista 1 é a decomposição (entradas, constantes, operação) e a pista 2 é o fluxograma ou o Portugol. Usar uma pista dá **metade dos pontos/XP** (0,5×).

**Banco inicial (~60 problemas, todos em `rascunho` até o professor aprovar):**
- **Variações das aulas**, com outra história e outros dados mas o mesmo conceito. Exemplos: média de 3 notas → média ponderada de testes; segundos → horas:min:seg; km/h → nós; carro de bombeiros → rampa de acesso (Pitágoras); troca de valores → rodar 3 valores; missões da Loja XPTO → novas missões (estacionamento por hora, ginásio com inscrição, Uber noturno); gato com fome → cão que quer passear; "ainda dá para um café" → "ainda apanho o autocarro"; contagem decrescente → temporizador de micro-ondas; média de N notas → média só das positivas; validação → PIN com 3 tentativas.
- **Exercícios novos** em cada bloco, de ★ a ★★★★★, incluindo o "próximo passo" indicado no PDF (contar notas positivas, maior valor de N inputs).
- **Bosses de região:** problemas que combinam todo o bloco, como a "Missão Final" da festa de aniversário.
- **Mais além:** ~10 problemas opcionais.

**Validação do banco (só para quem cria problemas):** solução de referência obrigatória e validador automático. O **verificador de currículo** (`app.tools.check_curriculum`) analisa **apenas a solução de referência**, para garantir que cada problema *pode* ser resolvido só com a matéria dada até àquele bloco. **Nunca se aplica às submissões dos alunos.**

## Avaliação das submissões: liberdade criativa
- **Regra base: conta o resultado, não o caminho.** O aluno pode usar o que quiser: matéria ainda não dada, funções da biblioteca padrão (`sum`, `sorted`, `max`, compreensões, `collections`…), outra estrutura de código ou uma solução mais curta ou mais longa. **Se o output (ou o valor devolvido) estiver certo em todos os testes, está certo.** As únicas restrições são as de segurança do runner (módulos de sistema como `os`, `subprocess`, `socket`, `ctypes`), e essas não têm nada a ver com criatividade.
- **Comparação tolerante, para não chumbar por detalhes:** espaços a mais, linhas em branco no fim, maiúsculas/minúsculas e acentos são normalizados no modo `texto`. No modo `numeros`, `14`, `14.0` e `14,0` valem o mesmo (tolerância 0.01). Nos problemas de funções, uma lista ou um tuplo com os mesmos valores contam como iguais quando a ordem não interessa (`ordem_importa: false`). O prompt do `input()` é sempre ignorado.
- **Exercícios com estrutura obrigatória (uma categoria própria e intencional):** quando o objetivo pedagógico é treinar uma estrutura, o problema declara `requisitos` e mostra-os **em destaque no enunciado** com o selo "🧱 Estrutura obrigatória", para o aluno saber antes de começar. Exemplos:
  - `usa: [while]`: "resolve com um ciclo `while`"
  - `define_funcao: {nome: calcular_media, parametros: 3}`
  - `usa: [lista]` ou `usa: [for, if]`
  - `proibe: [sum, max, sorted]`: "calcula o máximo à mão, sem `max()`" (treinar o algoritmo e não a função pronta)
  - `recursiva: true` (quando o bloco 6b estiver aberto)
  O verificador (`runner/requirements.py`, análise com `ast`) corre **depois** dos testes. Se o output estiver certo mas faltar a estrutura, o feedback é claro e encorajador ("✅ O resultado está certo! 🧱 Mas este desafio pede um ciclo `while`. Experimenta reescrever com `while`."). A submissão só é aceite quando cumprir os requisitos, e não perde as tentativas já feitas.
- **Mistura no banco:** ~70% dos problemas são de **output livre** e ~30% de **estrutura obrigatória**, sobretudo nos blocos onde a estrutura é a matéria (ciclos, funções, listas). Os bosses de região são sempre de output livre, para premiar a criatividade.
- **Depois de resolver:** o aluno pode ver **outras soluções aceites** da turma (anónimas, só depois de resolver), para descobrir abordagens diferentes, e dar "🧠 Solução elegante" a uma delas (liga às honras).
**Revisão do professor:** no painel aprovas, editas ou rejeitas cada problema, e só os aprovados aparecem aos alunos.

## Formato dos problemas (`backend/problems/*.yaml`)
```yaml
id: autocarro-ainda-da
titulo: Ainda apanho o autocarro?
tipo: programa            # programa | decomposicao | tracar | bug | funcao | quiz
bloco: 4                  # do curriculum.yaml (condicionais)
regiao: encruzilhada
dificuldade: 2            # 1 a 5 estrelas
origem: variacao_aula     # variacao_aula | novo | mais_alem | boss
estado: rascunho          # rascunho | aprovado
enunciado: |
  Lê quantos minutos faltam para o autocarro passar e a que distância (em minutos a pé) estás da paragem.
  Se chegares com mais de 2 minutos de folga escreve "Vai a andar".
  Se chegares a tempo mas à justa escreve "Corre!". Caso contrário escreve "Pede boleia".
exemplos:                 # visíveis
  - {stdin: "10\n5\n", stdout: "Vai a andar"}
testes:                   # escondidos
  - {stdin: "7\n5\n", stdout: "Corre!"}
  - {stdin: "4\n5\n", stdout: "Pede boleia"}
comparacao: texto         # texto (normaliza espaços/maiúsculas/acentos) | numeros (tolerância 0.01) | exato
requisitos: null          # opcional, ex. {usa: [while], proibe: [max], define_funcao: {nome: x, parametros: 2}}
pistas:
  - "Entradas: minutos_autocarro, minutos_a_pe. Folga = minutos_autocarro - minutos_a_pe."
  - "Portugol: se folga > 2 ... senao se folga >= 0 ... senao ..."
erros_comuns:             # feedback específico quando o output bate com um erro conhecido
  - {stdout: "Corre!", quando_stdin: "10\n5\n", mensagem: "Confirma a ordem das condições: a mais exigente vem primeiro."}
limite_tempo_s: 2
solucao_referencia: |
  minutos_autocarro = 0
  minutos_a_pe = 0
  minutos_autocarro = int(input("Minutos até o autocarro: "))
  minutos_a_pe = int(input("Minutos a pé: "))
  folga = minutos_autocarro - minutos_a_pe
  if folga > 2:
      print("Vai a andar")
  elif folga >= 0:
      print("Corre!")
  else:
      print("Pede boleia")
```
**Como corre um programa:** o harness substitui `input()` por uma versão que lê do stdin **sem escrever o prompt**. Assim, `input("Nota: ")` funciona tal como o aluno aprendeu, e o texto do prompt não estraga a comparação. Depois compara o stdout com o modo definido em `comparacao`. Os tipos `funcao` usam `chamadas: [{args: [...], devolve: ...}]`; os tipos `decomposicao`, `tracar` e `quiz` usam `opcoes`/`resposta` e não passam pelo runner. O professor pode carregar novos YAML pelo painel.

## Modo Treino
- "Novo desafio" sorteia problema do nível do aluno (±1), evitando já resolvidos.
- XP = base por dificuldade × bónus (1.ª tentativa, rapidez). Ranks: Bronze → Prata → Ouro → Platina → Diamante; ranks desbloqueiam dificuldades maiores.
- Streak diária, conquistas, ranking da turma.
- Feedback: exemplos mostram esperado vs obtido; testes escondidos só "x/y passaram" (+ erro/timeout).

## Modo Algoritmia (estilo LeetCode, opcional)
Uma área à parte, "🗡️ Arena de Algoritmia", para quem quer treinar algoritmia a sério. **Não está presa ao currículo:** o aluno escolhe entrar, sabendo que pode encontrar matéria ainda não dada.
- **Três níveis, com correspondência aos níveis do LeetCode:**
  | Nível no jogo | Equivale a | Exemplos de temas |
  |---|---|---|
  | 🔥 **Hard Level** | LeetCode *Easy* | somas e contagens, strings simples, máximo/mínimo, palíndromos, FizzBuzz-like |
  | 🔥🔥 **Extra Hard Level** | LeetCode *Medium* | hashing/dicionários, dois ponteiros, janela deslizante, ordenação, pesquisa binária, pilhas, recursão |
  | 💀 **Hardcore Insane Level** | LeetCode *Hard* | programação dinâmica, grafos (BFS/DFS, caminhos), *backtracking*, heaps, intervalos |
  Os nomes aparecem iguais em PT e EN, com uma legenda traduzida ("equivale a LeetCode Médio").
- **Desbloqueio progressivo:** Hard está sempre aberto. Extra Hard abre com 10 Hard resolvidos e Hardcore Insane com 5 Extra Hard (o professor pode abrir tudo no painel).
- **Formato tipo LeetCode:** problema do tipo `funcao` com assinatura dada (`def dois_numeros(nums, alvo):`), exemplos com explicação, restrições (ex. `1 ≤ len(nums) ≤ 10⁵`) e tags de tema. Os testes escondidos incluem **inputs grandes**, por isso uma solução O(n²) num problema que pede O(n) dá **"Tempo limite excedido"**. O limite de tempo é calibrado automaticamente a partir da solução de referência (×5 com margem).
- **Depois de resolver:** tempo de execução e memória comparados com a turma ("mais rápido que 70% da turma"), e uma **explicação/editorial** bilingue com a ideia, a complexidade e a solução de referência comentada. O editorial também abre ao fim de 5 tentativas falhadas, mas aí só dá metade do XP.
- **Biblioteca padrão permitida** neste modo: `collections`, `heapq`, `bisect`, `itertools`, `math`, `functools` (lista branca no runner).
- **Problemas originais:** clássicos de algoritmia (são conceitos, não pertencem a ninguém), mas com **enunciado, história e testes escritos por nós**. Não se copiam enunciados do LeetCode.
- **Gamificação:** XP maior (Hard ×1, Extra Hard ×2, Insane ×4), conquistas próprias ("Primeiro Insane", "10 seguidos sem TLE"), separador **Algoritmia** no leaderboard e emblema de nível no perfil. Os três níveis também podem ser escolhidos como dificuldade em **duelos** e em rondas de **torneio**.
- **Banco inicial:** 15 Hard + 10 Extra Hard + 5 Hardcore Insane, gerados pelo Sonnet (os Insane revistos pelo Opus), cada um com solução de referência, uma solução ingénua que **tem de falhar por tempo** (para confirmar que os testes grandes funcionam) e editorial PT/EN.
- **Ficheiros:** `backend/problems/algoritmia/{hard,extra_hard,insane}/*.yaml`, `backend/app/services/algo_arena.py` (desbloqueios, percentis), `frontend/pages/arena/` e `frontend/components/editorial.js`. No YAML entram os campos `nivel_algo: hard|extra_hard|insane`, `restricoes`, `complexidade_esperada`, `solucao_ingenua` e `editorial: {pt, en}`.

## Modo Duelo (1 vs 1, a qualquer hora)
- **Como entrar (por agora, só desafio direto):** **"Desafiar colega"** gera um código de 6 caracteres e um link. O colega entra com o código e o duelo começa quando os dois carregam em "Pronto". O código expira ao fim de 10 min. Matchmaking automático fica para uma fase futura.
- **Formato:** melhor de 3 problemas, 10 min por problema. Quem desafia escolhe a dificuldade (por omissão, é calculada pela média do rating dos dois). Ganha o problema quem passar mais testes; em caso de empate, quem submeteu primeiro. Os dois veem em tempo real o progresso do adversário ("3/8 testes ✅"), mas nunca o código.
- **Rating ELO** próprio dos duelos (começa em 1000), com ranking de duelistas da turma. Os duelos também dão XP para o modo Treino.
- **Rede:** se um jogador desligar, o duelo pausa e ele tem 60 s para voltar (com o estado recuperado pelo mesmo mecanismo de `seq`); se não voltar, perde por falta. Se ambos desligarem, o duelo é anulado sem alterar o ELO.
- **Anti-abuso:** ELO só conta contra adversários diferentes (no máximo 3 duelos com rating contra a mesma pessoa por dia), para não se poder "farmar" rating com um amigo.
- **Reutilização:** o motor de duelo (`services/duel.py`) é o mesmo usado nas **eliminatórias do torneio**. Lá, o professor define os pares; no modo Duelo, é o código de convite.
- Ficheiros: `backend/app/api/duel.py` (criar desafio, entrar com código, estado), `backend/app/services/duel.py`, `backend/app/services/elo.py`, `backend/app/models/duel.py` (`DuelInvite`, `Duel`, `DuelRound`), `frontend/pages/duel/` (`duel.html`, `duel.js`) e `frontend/components/opponent-progress.js`.

## Modo Torneio (controlado pelo professor)
**Dois formatos:**
- **"Formato Aula"** (copiado da tua "Operação Decomposição"): **individual ou por agências** (equipas de 3–4 com nome escolhido) e 5 rondas Fácil → Fácil-Médio → Médio → Médio-Difícil → Difícil, com 3 missões cada. Pontuação: 10 ou 15 pontos por missão certa à primeira, 0,5× se usou pista, +5 para a primeira agência a acabar a ronda toda certa, ×2 na Ronda 5, e no fim uma **Boss Battle** com toda a turma contra um problema e pontos bónus. Há leaderboard projetado entre rondas, pausas opcionais de **quiz relâmpago** (substituem o Fuiz) e cerimónia final com **diploma pixel** ("Mestre da Decomposição", "Mestre dos Ciclos", …) para descarregar.
- **"Grupos + Eliminatórias"** (20 alunos), como descrito abaixo.

1. Professor cria torneio, escolhe o formato e os blocos do currículo a usar; alunos entram com código. Configurável: nº de grupos, qualificados por grupo, problemas e tempo por ronda.
2. **Grupos** (ex. 20 → 4 grupos de 5): todos resolvem o mesmo problema por ronda; pontos = testes passados + bónus de tempo; top 2 avançam (8 → bracket; melhores terceiros completam se necessário).
3. **Eliminatórias** (quartos → meias → final): duelos 1v1 com o mesmo motor do Modo Duelo, com a dificuldade a subir a cada fase.
4. Botões do professor: iniciar, pausar, prolongar, terminar ronda, avançar fase. Ecrã projetor com bracket e ranking ao vivo.
5. Problema só visível após início da ronda.

## Segurança (cliente + servidor)
### Execução do código dos alunos (runner)
- O código corre num **contentor próprio sem rede e sem acesso à BD** (ver Docker). Cada submissão corre num subprocesso `python -I` com ambiente vazio, `setrlimit` (CPU 2 s, memória 256 MB, nº de processos, ficheiros abertos, tamanho de ficheiros 0), *process group* morto no timeout e diretório temporário apagado no fim.
- **Limites de entrada e saída:** código até 20 KB, stdin até 64 KB, stdout cortado aos 64 KB. Assim, quem faz `print` num ciclo infinito não enche a memória.
- **O aluno não consegue falsificar o resultado:** a comparação com o esperado é feita **no processo pai** (o servidor do runner), nunca dentro do processo do aluno. Nos problemas de funções, o filho devolve os resultados por um *pipe* separado com um *nonce* por execução, e o pai valida o *nonce*.
- Bloqueio de imports perigosos (`os`, `subprocess`, `socket`, `ctypes`…) como camada extra, mas não a única.
- Seccomp por omissão do Docker, `no-new-privileges`, `cap_drop: ALL` e utilizador `nobody`.

### Contas e sessões
- Palavras-passe com **Argon2id**. Sessão em cookie `HttpOnly`, `Secure` e `SameSite=Lax`, com rotação ao fazer login. Proteção CSRF (token + verificação do `Origin`) em todos os pedidos que alteram dados.
- **Contas criadas pelo professor** (importação por CSV ou código de turma) e dados mínimos: nome de utilizador e nome a mostrar, sem email obrigatório (RGPD). O aluno pode exportar ou apagar os seus dados.
- **Permissões verificadas no servidor:** aluno ≠ professor, e um aluno só vê a sua própria turma.
- Login com limite de tentativas e bloqueio temporário. A conta inicial do professor vem do `.env` e é obrigatório mudar a palavra-passe no primeiro login.
- **WebSocket autenticado** pelo cookie de sessão, com verificação do `Origin`, tamanho máximo de mensagem (8 KB), limite de mensagens por segundo e no máximo 3 ligações por utilizador.

### Web (cliente)
- **Nada de `innerHTML` com conteúdo vindo de utilizadores:** usa-se `textContent`. Os enunciados em Markdown são convertidos no servidor e limpos com `nh3` (lista branca de tags).
- **CSP estrita** via Caddy: `default-src 'self'`, sem scripts inline (o script de tema no `<head>` passa a ficheiro externo pequeno), `frame-ancestors 'none'`. Também HSTS, `X-Content-Type-Options`, `Referrer-Policy` e `Permissions-Policy`.
- SQL só com queries parametrizadas (SQLModel). Limite de tamanho do corpo dos pedidos.

### Anti-batota (competição justa)
- **Testes escondidos e soluções de referência nunca saem do servidor.** O enunciado de uma ronda só é enviado quando a ronda começa. O tempo é medido pelo servidor.
- **Deteção de semelhança** nas submissões de torneio e duelo (hash do AST normalizado + distância de tokens): os casos suspeitos aparecem ao professor, que decide. Nada é automático.
- A perda de foco do separador durante um torneio fica registada apenas como informação para o professor.

### Operação
- Segredos só no `.env` (fora do git). Dependências fixadas (`uv.lock`), JS em `vendor/` com checksum SHA-256 registado e imagens Docker com versão fixa. App e runner correm como utilizador não-root.
- **Registo de auditoria** das ações do professor (aprovar problemas, alterar pontos, terminar rondas).
- No fim de cada fase o Opus corre `/security-review`, e antes do primeiro uso com alunos corre `/code-review`.

## Robustez e fluidez (cliente + servidor)
### Servidor
- **Metas:** resultado de uma submissão em < 2 s (p95) com 20 submissões em simultâneo; API < 150 ms (p95); 60 ligações WebSocket estáveis numa VM de 2 vCPU / 4 GB.
- **Processos:** `gunicorn` + workers `uvicorn` (nº = vCPUs), pool `asyncpg` limitada por worker, timeouts em todas as chamadas (BD, runner) e *graceful shutdown* (as rondas não se perdem num `docker compose restart`).
- **Runner rápido:** um *pool* de interpretadores pré-aquecidos (*zygote* com `fork` por submissão) evita os ~30 ms de arranque do Python, e a concorrência é igual ao nº de CPUs. Com *backpressure*, quando há pico (todos submetem no fim da ronda) os pedidos ficam na fila Postgres e o aluno vê "Na fila: posição 3", em vez de dar erro.
- **Leaderboard sem cálculos pesados:** tabela `user_stats` atualizada na mesma transação de cada submissão aceite, índices adequados e cache de 10 s.
- **Eventos agregados:** as atualizações de pontuação são agrupadas e enviadas no máximo 1×/s por sala, em vez de uma mensagem por cada submissão.
- **Migrações com Alembic** ao arrancar. Limpeza periódica de `tournament_events` e `presence` antigos. *Readiness* separado de *liveness* nos healthchecks.
- **Observabilidade simples:** logs JSON e uma página "Estado" no painel do professor (alunos ligados, tamanho da fila, latência do runner, erros recentes), sem serviços externos.

### Cliente
- **Orçamento de peso:** cada página < 50 KB gzip de JS próprio (sem contar o CodeMirror e o three.js, que só carregam onde são precisos). Caddy com compressão `zstd`/`gzip`, `ETag` e `Cache-Control` longo nos ficheiros de `vendor/` versionados.
- **Service worker** guarda o "esqueleto" da app (HTML, CSS, JS, fontes, sprites). A app abre e o editor funciona mesmo que a rede falhe por momentos, e as submissões ficam na fila offline já prevista.
- **Three.js controlado:** `devicePixelRatio` limitado (a cena é de baixa resolução de qualquer forma), 30 FPS nas cenas de fundo, pausa quando o separador está escondido e `dispose()` de geometrias e texturas ao sair da página. **Autodegradação:** se o tempo por frame passar 33 ms durante 2 s, troca para a versão 2D.
- **UI fluida:** atualizações do leaderboard agrupadas num `requestAnimationFrame`, animações só com `transform`/`opacity`, autosave do editor com *debounce* de 500 ms e nunca a bloquear a escrita.
- **Erros nunca deitam abaixo o ecrã:** um *handler* global (`window.onerror` / `unhandledrejection`) mostra uma toast, mantém o código e regista o erro no servidor.

## Passo 0: `CLAUDE.md` na raiz do projeto (primeira coisa a criar, antes de qualquer código)
Resumo curto (menos de ~120 linhas) que qualquer sessão ou subagente lê primeiro. Conteúdo:
1b. **Originalidade:** inspiração em mecânicas de géneros (aventura/mundo aberto, missões, ranked), mas nunca nomes, personagens, logótipos, fontes, música ou visual de jogos existentes.
1. **O que é o PyArena:** os 3 modos (Treino, Duelo por código, Torneio grupos+eliminatórias), o público (alunos de Programação I) e o tom ("competitivo e saudável").
2. **Idioma:** a app é **bilingue, PT-PT (por omissão) + EN**. Nenhuma string fixa: usar sempre `t("chave")`/`data-i18n` no frontend e chaves nas respostas da API. Os problemas e os conteúdos do jogo têm `pt` e `en`, incluindo os outputs de texto esperados. `check_i18n` tem de passar. O código e os commits ficam em inglês. Os comentários de topo de cada ficheiro ficam em português, para o professor perceber o projeto.
3a. **Design:** pixel art retro original. Seguir `frontend/styles/tokens.css` (paleta limitada, bordas em degrau, sem cantos arredondados), usar fontes pixel só em títulos/UI e fonte monoespaçada normal no código e nos enunciados. Cenas 3D em voxels pixelizados. Temas: só variáveis CSS em `styles/themes/` e configuração 3D em `scenes/themes.js`, sem cores fixas no código dos componentes. Three.js só em `frontend/scenes/`, carregado com `import()` dinâmico, com versão 2D de reserva e respeito por `prefers-reduced-motion`. Nunca carregar Three.js na página do editor.
3. **Stack e restrições:** FastAPI + SQLModel + asyncpg + PostgreSQL, sem Redis (LISTEN/NOTIFY, SKIP LOCKED, UNLOGGED). Frontend em JS simples com módulos ES, **sem frameworks e sem build de JS**. Estilos com **Tailwind v4 (binário standalone no Docker)**, **mobile first**: escrever primeiro para 360 px, alvos ≥ 44 px, nada dependente de hover. As cores vêm sempre dos tokens/temas, nunca de classes de cor fixas do Tailwind (ex. `bg-red-500`). CodeMirror 6 só na página do editor. Python 3.12 via `uv`.
4. **Estrutura de pastas** (a árvore acima) e a regra pages / components / services.
5. **Regras de resiliência de rede:** nunca perder código (rascunho em localStorage), submissões idempotentes com ID do cliente, temporizador definido pelo servidor, reconexão com replay por `seq`.
6. **Segurança:** o código do aluno corre só no runner (nunca `exec` na app) e a comparação é feita no processo pai. Nunca usar `innerHTML` com dados de utilizadores. CSP sem inline. CSRF + cookies `HttpOnly`. Permissões verificadas no servidor. Testes escondidos e soluções nunca saem do servidor. WebSocket autenticado e com limites.
6b. **Fluidez:** respeitar os orçamentos (página < 50 KB JS próprio, submissão p95 < 2 s, API p95 < 150 ms). Eventos agrupados 1×/s. Three.js com pausa, `dispose` e autodegradação. Nada pode bloquear o editor.
7a. **Avaliação:** conta o output/valor devolvido. **Nunca** restringir as submissões dos alunos pelo currículo; o verificador de currículo serve só para as soluções de referência. As restrições de estrutura existem apenas quando o problema declara `requisitos`, e têm de aparecer em destaque no enunciado.
7. **Problemas:** formato YAML bilingue, com stdin/stdout nos blocos 2–5 e chamadas a funções no bloco 6 (já dado), respeito pelo `curriculum.yaml` (nenhuma construção ainda não dada), convenções do professor (variáveis inicializadas no topo, CONSTANTES em maiúsculas, nomes em português), tom com humor do dia a dia, solução de referência obrigatória que passe no validador e no verificador de currículo.
8. **Tudo em Docker:** a VM só precisa de Docker Compose. Comandos: `docker compose up -d --build`, `docker compose run --rm app pytest`, `docker compose run --rm app python -m app.tools.validate_problems`. Nenhuma dependência de CDN ou de serviço externo.
9. **Orquestração:** Opus orquestra e revê. Implementação por Sonnet (lógica/segurança) e Haiku (problemas, CSS, páginas simples, docs). Os subagentes só alteram os ficheiros que lhes foram atribuídos.
10. **Definição de "feito":** testes a passar, validador a passar, ficheiro com comentário de topo e sem dependências de frontend novas sem aprovação.

## Orquestração (modelos Claude)
- **Opus (esta sessão) orquestra e não escreve o código das funcionalidades.** Define os contratos entre módulos (modelos de dados, rotas da API, formato dos eventos WebSocket), entrega cada tarefa a um subagente, revê o diff, corre os testes e decide se a fase está concluída.
- **Implementação por subagentes** (`Agent` com `model: "sonnet"` ou `"haiku"`), cada um com instruções fechadas: ficheiros que pode alterar, contrato a cumprir e testes que têm de passar.
  - **Sonnet:** o que é lógico ou sensível à segurança, ou seja, esqueleto do backend e modelos, runner/sandbox, tempo real (hub, pg_bus, presença, replay), motor de duelo e ELO, torneio e bracket, e os serviços JS (`api.js`, `socket.js`, `storage.js`) e páginas com estado (challenge, duel, tournament, projector).
  - **Sonnet também:** as cenas Three.js (`frontend/scenes/`) e o leaderboard animado, sempre seguindo os `tokens.css` definidos pelo Opus com a skill frontend-design.
  - **Haiku:** o que é repetitivo ou de baixo risco, ou seja, o banco de ~30 problemas em YAML (validados automaticamente contra a solução de referência), CSS e páginas simples (index, profile, admin estático), testes de casos simples e README.
- **Paralelismo só sem ficheiros partilhados:** por exemplo, o runner (Sonnet) e o banco de problemas (Haiku) correm ao mesmo tempo depois da fase 1. O frontend de uma funcionalidade só arranca quando o contrato da API dela está fixado.
- **Porta de qualidade por fase:** o Opus corre `pytest` e o validador de problemas e faz uma revisão de segurança ao runner. Se algo falhar, a tarefa volta ao mesmo subagente com o erro (via SendMessage).

## Fases de implementação
0. Mover os materiais para `materiais_aulas/` (no `.gitignore`), escrever o `CLAUDE.md` (Opus) e fazer `git init`. Pausa para o professor rever antes de avançar.
1. Esqueleto backend/frontend com a estrutura acima, modelos, auth com turmas, carregamento de YAML e **i18n desde o primeiro dia** (`i18n.js`, JSON PT/EN, `check_i18n`).
2. Runner + harness com sandbox e testes.
3. Modo Treino (editor, submissão com fila offline, XP, ranking).
4. Tempo real (WebSocket hub + pg_bus) e Modo Duelo (motor de duelo, convites por código, ELO).
5. Torneio: grupos, bracket que reutiliza o motor de duelo, painel do professor, ecrã projetor.
5b. Camadas de jogo: mapa-mundo com santuários, masmorras e relíquias, contratos diários, moedas e loja de cosméticos, ligas com temporadas e promoções, power-ups e honras.
6. Design: identidade visual (frontend-design → `tokens.css`), cenas Three.js e leaderboard com pódio 3D (pode correr em paralelo com a fase 7).
6b. `curriculum.yaml` (Opus, a partir da análise já feita das aulas I–V). Depois, ~60 problemas pelos 6 tipos de desafio: variações das aulas, novos, bosses e "mais além". O Sonnet gera os bosses e os tipos `tracar`/`bug`, o Haiku gera os restantes. O validador e o verificador de currículo filtram, e o professor aprova no painel.
6c. Arena de Algoritmia: página, desbloqueios, percentis, editorial e os 30 problemas iniciais (Sonnet; o Opus revê os Insane).
7. Docker + deploy + README a explicar a estrutura.

## Verificação
- `pytest`: harness (certo/errado), sandbox (loop infinito → timeout, memória enorme → erro, `import os` → bloqueado), torneio (20 jogadores simulados → grupos → bracket → campeão), duelo (melhor de 3, empates, desistência após 60 s, cálculo do ELO, limite diário contra o mesmo adversário), mundo (corações, desbloqueio de regiões com relíquia, sem perda de XP ao morrer), economia (as moedas não podem ficar negativas, a compra é idempotente), ligas (série de promoção, soft reset de temporada), power-ups simétricos, convites (código válido junta os dois jogadores; código expirado ou já usado é recusado; ninguém se pode desafiar a si próprio), idempotência de submissões.
- Script que valida cada problema contra a sua solução de referência, mais o verificador de currículo (ex. um problema do bloco 4 com `for` é rejeitado). **Liberdade criativa:** uma submissão de um problema do bloco 2 que usa listas, compreensões ou `sum()` é aceite se o output estiver certo; `14`/`14.0`/`14,0` são equivalentes; um problema com `requisitos: {usa: [while]}` resolvido com `for` → "resultado certo, falta a estrutura"; um com `proibe: [max]` resolvido com `max()` → recusado com a explicação. Harness: `input("prompt")` não suja o stdout, cada modo de comparação (texto/números/exato) funciona, e o feedback de erros comuns aparece.
- **i18n:** `check_i18n` sem chaves em falta. No browser pane, mudar 🇵🇹↔🇬🇧 traduz toda a interface sem recarregar. Um duelo PT vs EN mostra a cada um o seu enunciado, e ambos são corrigidos com o output certo para a sua língua.
- **Algoritmia:** para cada problema, a solução de referência passa e a `solucao_ingenua` dá TLE nos testes grandes. Desbloqueios (10 Hard → Extra Hard, 5 Extra → Insane). O editorial só abre depois de resolver ou de 5 tentativas.
- Formato Aula: simular 5 agências por 5 rondas + boss, confirmando a pista a 0,5×, o +5 para a primeira e o ×2 na Ronda 5.
- **Docker de raiz:** `docker compose down -v && docker compose up -d --build`, e depois confirmar que todos os serviços ficam `healthy`, que o runner não consegue fazer `curl` para fora nem ligar à BD, e que os dados sobrevivem a um `docker compose restart`.
- Abrir a app servida pelo compose e testar no browser pane: professor + vários alunos, treino, torneio completo.
- **Design/3D:** abrir cada cena no browser pane, ver a consola sem erros, simular `prefers-reduced-motion` e WebGL desligado para confirmar a versão 2D, e confirmar no separador Network que a página do editor não descarrega three.js. Temas: recarregar várias vezes muda de tema sem flash, e um tema fixado no perfil mantém-se depois de recarregar e noutro browser. Leaderboard: dois alunos a trocar de posição → animação + toast em tempo real.
- **Segurança (testes automáticos em `tests/security/`):** XSS no nome de utilizador e nos enunciados não executa; POST sem token CSRF → 403; WebSocket sem sessão ou com `Origin` estranho → recusado; aluno a chamar endpoints de professor → 403; aluno de outra turma → 404; nenhuma resposta da API contém testes escondidos ou soluções de referência; runner com `fork bomb`, `print` infinito, `open('/etc/passwd','w')`, `socket` e tentativa de falsificar o resultado → tudo bloqueado ou dado como errado; login com força bruta → bloqueado. Cabeçalhos CSP/HSTS presentes (verificados com `curl -I`).
- **Carga (k6 num contentor de teste):** 40 alunos ligados por WebSocket e 20 submissões no mesmo segundo → p95 < 2 s, zero erros e fila visível. API p95 < 150 ms.
- **Mobile:** no browser pane com `resize_window` mobile (375×812) e tablet, percorrer todos os ecrãs: sem scroll horizontal, barra inferior funcional, editor com separadores e barra de símbolos (resolver um problema completo só com toque), duelo jogável e PWA instalável (manifest válido).
- **Fluidez no cliente:** com o DevTools em CPU 4× mais lento e rede "Slow 4G", o editor continua a responder, as cenas 3D passam a 2D quando necessário e cada página fica dentro do orçamento de peso. Com o service worker, a app abre em modo offline.
- **Teste de rede:** cortar o servidor/rede a meio de uma ronda (DevTools offline) → confirmar que o código fica guardado, a submissão é reenviada, o estado é ressincronizado e o indicador muda de cor.
