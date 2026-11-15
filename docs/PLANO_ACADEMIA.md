# PyArena — Próximo passo: "Academia" (módulos de aprendizagem) + tema 3D do campus IPT

> Só planeamento. Nada é implementado até o professor aprovar.
> O plano original está em `docs/PLANO.md`. Torneios, leaderboard e design já existem.

## Contexto
Os torneios motivam quem já sabe. Os **alunos mais fracos** precisam de um percurso para **aprender ao seu ritmo**.
A ideia central da cadeira: no início importam sobretudo os **fluxogramas e os blocos de Python correspondentes**. O aluno tem de saber **ler as duas linguagens** e ver as peças a **encaixarem devagar, passo a passo**.

O modo "Mundo" (hoje o cartão "Em breve") passa a ser uma **Academia de módulos**:
- **apresentação:** uma página de módulos em sequência vertical, passo a passo, gamificada ao estilo das academias de cibersegurança (módulos com secções, % concluída, pontos, selos);
- **conteúdo:** começa pelo contexto da 1.ª aula (linguagens naturais e formais, IA) e acompanha os PowerPoints do professor;
- **referência secundária:** o livro *Python Basics* (Real Python), usado para a ordem e a pedagogia, sem copiar texto.

No fim desta fase, o **tema principal da app** passa a ser uma **vista 3D do campus do Politécnico de Tomar**.

**Decisões do professor:**
- **Vistas:** só fluxograma + Python, sempre lado a lado e ligados.
- **Fluxogramas: estilo limpo, NÃO pixel art** (igual aos slides).
- **Pontos:** pequenos, mais estrelas, e contam para o score pessoal e o leaderboard.
- **Acesso:** para todos, adaptativo, com painel do professor.

## 1. Conteúdo: módulos baseados nas aulas
| # | Módulo | Origem (PowerPoints) | Livro (referência) |
|---|---|---|---|
| **M0** | **Porquê programar? Linguagens e IA** | Aula I (objetivos, "IA vs. Pensamento Crítico"), Aula II–III (máquina de Turing, base 2/10, texto em binário/ASCII, linguagens naturais vs. formais, abstração, noção de problema) | Cap. 1 |
| **M1** | **Algoritmos e fluxogramas** | Aula II–III (o que é um algoritmo, receita vaga vs. refinada, algoritmo não computacional vs. computacional, símbolos do fluxograma, candeeiro) | — |
| **M2** | **Do fluxograma ao Python: sequencial** | Aula II–III (tipos, variáveis, blocos 1–4 Ler/Atribuir/Operações/Programa completo, `\n` `\t`, `%`, ex. 3.1–4.3) | Cap. 3, 4.4–4.7, 5.1–5.6 |
| **M3** | **Decomposição** | Aula 3.5 (entradas, variáveis, constantes, operação; missões da Loja XPTO) | Desafios dos cap. 4–5 |
| **M4** | **Decisões** | Aula IV (comparação, `and/or/not`, Boole, De Morgan, `if/elif/else`, aninhados, o café, o gato) | Cap. 8.1–8.3 |
| **M5** | **Repetição** | PDF Estruturas de Repetição (`for`/`range`, `while`, traçar, validação, erros clássicos) | Cap. 6.4, 8.5 |
| **M6** | **Funções** | Modularização | Cap. 6.1–6.3, 6.6 |
| **M7** | **Listas** | Dados estruturados | Cap. 9.2–9.3 |
| ✚ | **Caça aos bugs** (transversal) | Erros clássicos das aulas | Cap. 7 |

### M0 começa pelo contexto que o professor deu na 1.ª aula
- **Linguagem natural vs. formal:** "aparece daqui a pouco" vs. `esperar 5 minutos`, exemplos de ambiguidade, a máquina de Turing e o texto em binário (um mini-jogo de converter "Olá" ↔ bits).
- **A escada das linguagens**, como uma visualização interativa com degraus:
  **linguagem natural → IA / prompts → semi-formal (pseudocódigo) → fluxograma → Python → máquina/binário**.

  A perspetiva do professor fica explícita: **a IA é uma nova camada, quase junta da linguagem semi-formal**. Ajuda a passar das ideias para código, mas **quem programa tem de saber ler e validar** os níveis formais por baixo (o slide "IA vs. Pensamento Crítico": a IA gera e acelera; a pessoa compreende, valida e decide a estrutura).
  - Atividade "Valida a IA": é mostrado um fluxograma e um Python "gerados por IA" com um erro subtil, e o aluno encontra o erro.
- **Problema → algoritmo:** a conta de 42 € entre 4 amigos e os 6 passos "Como atacar um problema".

### PowerPoints como complemento académico
- Em cada módulo há um separador **"📑 Slides da aula"**, com os slides do professor visíveis só para quem tem sessão iniciada na turma.
- **Conversão:** `.pptx/.pdf` → imagens por slide, com LibreOffice headless num contentor e só no momento de importar.
- **Gestão:** o professor faz upload e associa ao módulo no painel.
- **Os materiais nunca ficam públicos nem no git** (continuam fora do repositório, num volume Docker).
- **Ligações a partir das secções:** cada secção pode apontar para slides concretos ("ver slides 28–33").

## 2. Página de módulos (estilo "academia")
- **Página da Academia:** uma **sequência vertical** de cartões de módulo, ligados por uma linha de progresso, como numa academia de cibersegurança. Cada cartão tem:
  - número e título;
  - ícone da aula;
  - dificuldade;
  - nº de secções;
  - **% concluída** (barra);
  - **pontos ganhos / possíveis**;
  - estado: 🔒 bloqueado / ▶ em curso / ✅ concluído;
  - um selo do módulo (a "peça" desbloqueada: Início/Fim, Ler/Escrever, Calcular, Decisão, Ciclo, Função, Lista).
- **Página do módulo:** uma **lista vertical de secções** numeradas (passo a passo). Cada secção abre e tem:
  1. **Aprender:** texto curto original + vista **fluxograma ↔ Python ligada**;
  2. **Praticar:** 1–3 atividades interativas;
  3. **"Responde para concluir":** uma pergunta de verificação curta, que completa a secção e dá pontos.

  Barra lateral (ou topo no telemóvel) com o progresso do módulo, os slides da aula e a "leitura recomendada".
- **Fim do módulo:** um **desafio** (o "boss" do módulo), em que o aluno escreve código livre corrigido pelo runner atual, e um **selo + pontos**.
- **Estética:** a moldura da app mantém a pixel art (cartões, selos, barras, temas). O **conteúdo didático** (fluxogramas, código, explicações) usa **tipografia limpa e legível**.

## 3. Fluxogramas: estilo limpo, igual aos slides
- **Desenho:** SVG vetorial com formas suaves e texto em fonte sans-serif normal, **sem pixelização**. É a mesma notação dos slides:
  - **Início/Fim:** pílula verde;
  - **Ler/Escrever:** paralelogramo lilás;
  - **Definir/Executar:** retângulo lilás com contorno roxo;
  - **Decisão:** losango azul-escuro com texto branco e saídas **Sim/Não**;
  - setas finas.
- **Contraste:** as cores adaptam-se ao tema claro e ao escuro sem perder legibilidade.
- **O Python ao lado** aparece numa vista de código limpa (fonte mono), com as **linhas coloridas pelo tipo de bloco**.
- **Uma única fonte de verdade:** um *modelo do programa* (nós e ligações) gera **ao mesmo tempo** o fluxograma e o Python. Tocar num bloco realça a linha e vice-versa. As duas vistas nunca se contradizem.
- **Convenções do professor** respeitadas: variáveis inicializadas no topo, CONSTANTES em maiúsculas, nomes em português.

## 4. Atividades (sempre com as duas vistas)
| Atividade | O aluno… |
|---|---|
| **Explorar** | vê o programa a correr: o bloco e a linha acendem juntos e há uma tabela de variáveis (como "Vamos Traçar o Ciclo") |
| **Ligar** | liga cada bloco do fluxograma à linha de Python |
| **Ordenar o fluxograma** | arrasta os blocos para a ordem certa (com o Python como guia, ou ao contrário) |
| **Ordenar o Python** (Parsons) | ordena as linhas, com indentação a partir de M4 |
| **Completar** | preenche lacunas num lado ou no outro |
| **Traduzir** | passa do fluxograma ao Python e vice-versa |
| **Prever** | diz o valor de uma variável / o output a meio da execução |
| **Caça ao erro / Valida a IA** | encontra a diferença ou o erro clássico entre as vistas |
| **Parte de propósito** (do livro) | provoca um erro de sintaxe vs. um erro em execução e lê a mensagem |
| **Escrever** | código livre com o fluxograma como guia (runner atual; conta o resultado) |

**Progressão dentro de cada secção:** ver → reconhecer → ordenar → completar → traduzir → escrever.
O arrastar funciona com rato, com o dedo e também com **"tocar para colocar"** (acessibilidade e telemóvel).

## 5. Bloquear ou desbloquear? Análise e recomendação
| Opção | A favor | Contra |
|---|---|---|
| Tudo desbloqueado | Liberdade; os bons avançam; ninguém fica "preso" | Os mais fracos saltam fundamentos; perde-se o "encaixar devagar" |
| Tudo sequencial e bloqueado | Garante pré-requisitos (aprendizagem por domínio) | Frustra os mais fortes; um passo difícil trava tudo; mau para rever matéria dada |

**Recomendação: um modelo híbrido.**
1. **Dentro de um módulo, as secções são sequenciais:** a secção seguinte abre quando se responde à pergunta de verificação da anterior. É aqui que as peças encaixam, por isso a ordem importa. Uma secção já concluída pode sempre ser revista.
2. **Entre módulos, o desbloqueio é suave.** Um módulo abre quando acontece **qualquer** destas condições:
   - o anterior está concluído;
   - **o professor marcou essa matéria como dada** (o `curriculum.yaml` / painel). Assim ninguém fica impedido de treinar o que já foi dado na aula;
   - o aluno passa um **"teste de salto"** curto (5 perguntas) no início do módulo, para os mais fortes avançarem.
3. **Pontos só na 1.ª conclusão** (repetir é treino e não dá pontos), com o ✅ e a % visíveis no cartão.
4. **Recomendado para mim:** o painel do professor pode **atribuir** um módulo ou secção a um aluno ou à turma, e isso aparece destacado no topo da Academia.

Este modelo garante o "passo a passo" a quem precisa sem castigar quem já sabe, e acompanha o ritmo das aulas.

## 6. Adaptação para os alunos mais fracos
- **Escada de pistas:**
  1. realça o bloco ou a linha;
  2. coloca uma peça;
  3. mostra um exemplo resolvido parecido.
- **2 erros no mesmo passo:** aparece a mini-explicação da aula + o slide relevante + uma **variante mais fácil**. Depois de acertar na variante, volta ao passo original.
- **Revisão espaçada:** os conceitos com mais erros reaparecem em perguntas de revisão nas secções seguintes.
- **Feedback com os erros clássicos** que o runner já deteta. O tom é sempre encorajador.

## 7. Pontos (contam para o score e o leaderboard)
Usam o livro de pontos que já existe, `user_points` (`backend/app/services/points.py`, `award()` idempotente).

| Razão | Pontos |
|---|---|
| `academy_section`: secção concluída na 1.ª vez | +3 (M0–M1) · +5 (M2–M3) · +8 (M4+) |
| `academy_write`: desafio "Escrever" resolvido | +10 |
| Pista usada | metade, **mínimo 1** (nunca zero) |
| `academy_star`: estrelas do módulo (precisão/pistas) | ★ +5 · ★★ +10 · ★★★ +15 (só a diferença ao melhorar) |
| `academy_badge`: módulo completo | +25 + o selo |
| `academy_streak`: dia com atividade | +2 |

Contam no leaderboard **Geral** e **Esta semana** (com a flag de privacidade). A barra de nível/XP da homepage passa a usar estes pontos.

## 8. Painel do professor
- **Grelha alunos × módulos/secções:** concluída / em curso / **presa** (≥3 erros ou >10 min).
- **"Onde estão presos":** as secções e conceitos com mais erros na turma.
- **Atribuir** módulos ou secções; **marcar a matéria como dada** (o que desbloqueia módulos).
- **Upload e associação dos slides** a cada módulo e secção.

## 9. Tema principal: o campus do IPT em 3D (fase final)
Fontes: o **mapa geral do campus** (PDF fornecido) e as **fotos** enviadas pelo professor.

- **Planta** (do mapa):
  - edifícios **A–Q**: o pente **G-H-I-J-L** (ao centro, com alas para oeste e o Q/Auditório Q102 a norte); o **B/A** com o Auditório Doutor José Bayolo Pacheco de Amorim; o **O** com a Sala O101; o **C** com o **lago** azul ao lado; o **E–D** a nordeste; o **P** (Bar/Refeitório) a norte; o **F** e o **N/M** a sul;
  - campos de jogos e pavilhão a oeste;
  - zonas verdes e parques de estacionamento;
  - a **Estrada da Serra** com a **rotunda** e a saída "Centro da Cidade".
- **Aspeto** (das fotos):
  - edifícios de **tijolo vermelho** com janelas em faixa e **colunatas brancas** no rés-do-chão;
  - **passadiço metálico** entre edifícios;
  - pátios relvados com bancos de madeira;
  - calçada portuguesa;
  - **candeeiros de globo duplo** e balizadores brancos;
  - o lago com reflexos;
  - choupos e ciprestes;
  - o muro de entrada com as letras "Politécnico de Tomar".
- **Estilo: pixel art 3D**, como o resto da app (skill `pixel-art`):
  - voxels;
  - renderização a baixa resolução ampliada com *nearest-neighbour* (`scene-base.js`);
  - paleta limitada (tijolo vermelho, branco das colunatas, verde dos relvados, azul do lago, cinza da calçada);
  - texturas de tijolo e calçada em pixel;
  - candeeiros e árvores em voxel;
  - pessoas em sprite;
  - ciclo dia/fim de tarde em degraus.

  Corre na **homepage** como cenário principal, substituindo a "ilha" como tema por omissão. Os 6 temas atuais continuam como alternativa.
  (O único conteúdo que **não** é pixel art são os fluxogramas e o código didático, ver §3.)
- **O campus como hub do jogo:** os edifícios são portas para os modos, com uma etiqueta ao passar ou tocar:
  - **Biblioteca / alas G–L** = Academia;
  - **Auditório A** = Torneios;
  - **Campos de jogos** = Duelo;
  - **Refeitório P** = Ranking / leaderboard;
  - **Edifício O (Sala O101)** = a sala de aula do professor (painel).
- **Técnica:** reaproveita `scenes/scene-base.js` (pausa quando escondido, `dispose()`, degradação automática para 2D, `prefers-reduced-motion`). A geometria é gerada em código a partir de uma planta simplificada em JSON (`scenes/campus/layout.json`, com as coordenadas tiradas do mapa). Há uma imagem 2D estática do campus de reserva.
- **Ícone e logótipo da UPT:** já existem em pixel art. Antes do uso público da imagem do campus e do logótipo, confirmar com a comunicação da UPT.

## 10. Arquitetura técnica (reutilizando o que existe)
- **Conteúdo:** `backend/content/academy/<modulo>/<secao>.yaml`, bilingue PT-PT/EN, com estes campos:
  - `modelo` (nós `{id, tipo: inicio|ler|escrever|calcular|decisao|ciclo|funcao|fim, texto, py}` + ligações Sim/Não/volta);
  - `aprender`, `atividades`, `verificacao`;
  - `variantes_faceis`, `conceitos`;
  - `slides` (referências);
  - `leitura` (o livro).
  
  **Validador:** o Python gerado do modelo tem de ser igual à `solucao_referencia` e passar os testes no runner. Há também um verificador de currículo para cada secção.
- **Backend:**
  - `services/academy.py` (carregar, desbloqueio híbrido, adaptação, pontos);
  - `api/academy.py` (módulos, secção, responder, pistas, teste de salto, endpoints do professor, slides);
  - modelos `academy_progress`, `academy_assignments`, `slide_decks` (migração `0005`).
  
  As atividades sem código são corrigidas como em `services/grading.py`; o "Escrever" usa `services/submissions.py` com `mode="academy"`.
- **Runner:** um novo **modo trace** (`sys.settrace` na harness, com os mesmos limites) para Explorar/Prever. É pré-calculado na validação para a solução de referência.
- **Frontend** (JS simples, CSP, mobile first; skills `pixel-art` só para a moldura e `gsap`):
  - `components/flowchart.js` (SVG limpo), `components/code-view.js`, `components/dnd.js`, `components/tracer.js`, `components/ladder.js` (escada das linguagens);
  - `pages/academy/` (lista vertical de módulos), `pages/module/` (secções passo a passo);
  - `scenes/campus/` (fase final).
- **i18n:** área `academy`.

## 11. Fases
| Fase | Entrega |
|---|---|
| **A0** | Contrato `docs/CONTRATO_ACADEMIA.md` + esquema + **protótipo do `flowchart.js` limpo** com 3 exemplos das aulas (média, segundos, café) + **maqueta da página de módulos** → **o professor aprova a notação e o layout** |
| **A1** | Página de módulos + página de secções + atividades Ligar/Ordenar/Completar/Pergunta + pontos + **M0 e M1** (linguagens, IA, algoritmos, fluxogramas) + slides das aulas I–III |
| **A2** | Modo trace + Explorar/Prever/Traduzir/Caça ao erro/Escrever + adaptação + **M2 e M3** |
| **A3** | Painel do professor (grelha, presos, atribuir, marcar dado, upload de slides) + teste de salto |
| **A4** | **M4–M7** + Caça aos bugs |
| **A5** | **Tema 3D do campus IPT em pixel art (voxels)** como cenário principal e hub dos modos |

**Orquestração:**
- **Opus:** contratos, conteúdo M0 (texto sensível à visão do professor sobre IA, revisto com ele) e revisões.
- **Sonnet:** backend + runner trace; frontend (fluxograma, arrastar, páginas); cena do campus.
- **Haiku:** variantes fáceis e EN.

## 12. Verificação
- **Testes:**
  - o modelo gera o mesmo Python que a solução e passa os testes, em todas as secções;
  - a correção de cada tipo de atividade;
  - o desbloqueio híbrido (anterior concluído / matéria marcada como dada / teste de salto);
  - pontos idempotentes (repetir dá 0; as estrelas só dão a diferença; a pista nunca dá 0);
  - a adaptação (2 erros → variante → volta);
  - a privacidade dos slides (sem sessão → 401; outra turma → 404);
  - a privacidade do leaderboard mantida.
- **No browser:**
  - a 375 px e em desktop, nos temas claro e escuro: o módulo M0 completo com o dedo ("tocar para colocar") e com o rato;
  - a ligação bloco↔linha;
  - o fluxograma legível e **não pixelizado**;
  - os slides visíveis só com sessão.
- **Aluno fraco simulado:** erra 2× → mini-explicação + slide + variante → conclui → aparece "presa → concluída" no painel.
- **Campus 3D** (A5): a 30 fps num portátil fraco, degradação para 2D a funcionar, hotspots acessíveis por teclado e a planta fiel ao mapa.
- **Aprovação do professor** no fim de A0 (notação e layout) e de A1 (texto do M0 sobre linguagens e IA).

## 13. Pendentes antes de começar
- **Fazer o commit** do trabalho atual, ainda sem commit desde o `4b13aa2`: Eliminatória, leaderboard, redesign, logótipo, sidebar e skills.
- **Pôr a app na VM** (runbook no Obsidian: `Programming_101/pyArena/04 - Deployment Runbook`).
- **Atualizar as notas do Obsidian** com este plano (nova nota `06 - Plano Academia & Campus 3D`).
- **Slides das aulas de funções e listas**, se existirem.
