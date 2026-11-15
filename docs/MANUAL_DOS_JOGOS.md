# 📖 PyArena — Livro de Instruções

> Programação I · Universidade Politécnica de Tomar
> Treina Python, desafia colegas e sobe no ranking. Competição saudável: o que conta é aprender, e toda a gente ganha pontos.

---

## Índice
1. [Começar](#1-começar)
2. [Como se resolve um exercício](#2-como-se-resolve-um-exercício)
3. [Tipos de exercício](#3-tipos-de-exercício)
4. [Torneio Eliminatória](#4-torneio-eliminatória)
5. [Torneio Formato Aula](#5-torneio-formato-aula)
6. [Pontos pessoais](#6-pontos-pessoais)
7. [Leaderboard público e privacidade](#7-leaderboard-público-e-privacidade)
8. [Guia do professor](#8-guia-do-professor)
9. [Problemas de rede e perguntas frequentes](#9-problemas-de-rede-e-perguntas-frequentes)
10. [Modos em breve](#10-modos-em-breve)

---

## 1. Começar

### Alunos
1. Abre a página do PyArena.
2. Em **"Entrar com código de turma"**, escreve o **código da turma** (6 caracteres) que o professor mostrar, o teu **nome a mostrar**, um **nome de utilizador** e uma **palavra-passe** (mínimo 8 caracteres).
3. A partir daí entras sempre com o nome de utilizador e a palavra-passe.

Se o professor te criou a conta por importação, recebes uma palavra-passe temporária e a app pede-te logo para a mudar.

### No ecrã principal
- **🏆 Torneio**: escreve o código do torneio que o professor projetar e carrega em **Entrar**.
- **👤 Perfil**: muda o nome a mostrar, o idioma (🇵🇹/🇬🇧), o tema, a palavra-passe e a tua visibilidade no leaderboard.
- **🎨 Temas**: em cada visita aparece um tema pixel diferente (Floresta, Masmorra, Oceano, Deserto, Neve ou Noite). No perfil, ou no botão da paleta, podes **fixar** o teu preferido.
- **Menu lateral** (computador): o botão « / » contrai e expande a barra.

---

## 2. Como se resolve um exercício

Cada exercício tem três separadores (no telemóvel aparecem como abas):

| Separador | O que tem |
|---|---|
| **Enunciado** | O problema, os exemplos visíveis e as pistas |
| **Código** | O editor Python. No telemóvel há uma **barra de símbolos** (`:` `(` `)` `[` `]` `"` `=` `#`, Tab…) |
| **Resultado** | O que aconteceu depois de submeteres |

### Submeter
- Carrega em **Submeter**. O teu código corre num ambiente isolado e é testado com **testes escondidos**.
- Vês quantos testes passaram (ex. **5/6**). Nos exemplos visíveis vês também o **esperado vs. obtido**.
- Se houver um erro clássico, a app dá-te uma dica, por exemplo: *"a divisão tem prioridade sobre a soma"*, *"`input()` devolve texto, converte com `int()`"*, *"ciclo infinito?"*.

### Regras de avaliação
- **Conta o resultado, não o caminho.** Podes usar o que quiseres (listas, `sum()`, compreensões, funções…), mesmo matéria que ainda não demos. Se o output estiver certo, está certo.
- **Somos tolerantes nos detalhes:** espaços a mais, maiúsculas/minúsculas e acentos não contam. Nos resultados numéricos, `14`, `14.0` e `14,0` valem o mesmo.
- **O texto do `input("…")` não conta.** Podes escrever `nota = int(input("Nota: "))` à vontade.
- **🧱 Estrutura obrigatória:** alguns exercícios pedem uma estrutura específica (ex. *"resolve com `while`"*, *"sem usar `max()`"*, *"define a função `calcular_media`"*). Isso aparece **em destaque no enunciado**. Se o resultado estiver certo mas faltar a estrutura, a app diz-te isso mesmo e podes voltar a tentar.

### Pistas
Cada exercício pode ter até 2 pistas. **Usar uma pista faz o exercício valer metade dos pontos (0,5×)** no Formato Aula. Antes de abrires uma pista a app avisa-te.

### O teu código nunca se perde
O rascunho fica guardado no teu dispositivo enquanto escreves. Se a rede falhar, a submissão fica em fila e é enviada sozinha quando a ligação voltar (vê a [secção 9](#9-problemas-de-rede-e-perguntas-frequentes)).

---

## 3. Tipos de exercício

| Tipo | O que tens de fazer |
|---|---|
| 🧾 **Programa** | Escrever o programa completo com `input()` e `print()` |
| 🔧 **Função** | Escrever uma função (`def …`) que devolve o resultado com `return` |
| 🐞 **Caça ao bug** | Recebes um programa com **um** erro clássico e tens de o corrigir |
| 🔍 **Traçar** | Prever o output de um pedaço de código, ou o valor das variáveis no fim |
| ❓ **Quiz** | Perguntas de conceitos (tabelas de verdade, De Morgan, tipos, prioridades…) |
| 🧩 **Decomposição** | Identificar entradas, variáveis, constantes e operação de um problema |

Os exercícios seguem a ordem das aulas: algoritmos → sequencial → decomposição → condicionais → ciclos → funções → listas, com dificuldade de ★ a ★★★★★.

---

## 4. Torneio Eliminatória

O formato **por omissão**. É **individual**: todos contra todos, em grupos pequenos, até sobrar um campeão.

### Como funciona
1. **Entrar:** escreve o código do torneio. O projetor mostra *"20 alunos dentro"*.
2. **Sorteio dos grupos:** em cada ronda, os alunos ainda em jogo são sorteados em **grupos de 4** (o professor pode escolher entre 3 e 6). Os grupos ajustam-se ao número de alunos:

   | Alunos | Ronda 1 | Depois |
   |---|---|---|
   | 20 | 5 grupos de 4 | Final com 5 → 🏆 campeão |
   | 18 | 5 grupos (4, 4, 4, 3, 3) | Final com 5 → 🏆 |
   | 12 | 3 grupos de 4 | Final com 3 → 🏆 |
   | 7 | 2 grupos (4, 3) | Final com 2 → 🏆 |

   Quando restam **5 ou menos**, a ronda seguinte é a **Final**: um único grupo. O professor pode pôr a passar **2 por grupo**, para haver mais rondas.
3. **Um exercício por ronda**, o mesmo para todos os grupos. A dificuldade sobe a cada ronda: fácil → médio → difícil/final.
4. **Ao vivo, no teu grupo:** vês os teus adversários com uma barra de *"testes passados X/Y"* e o número de tentativas. **Nunca vês o código deles.**

### Quem ganha o grupo
1. 🥇 O **primeiro** a ter a submissão **aceite** (todos os testes certos). O grupo fica decidido nesse instante.
2. Se o tempo acabar sem ninguém acertar tudo, ganha quem passou **mais testes**. Em caso de empate, ganha quem submeteu **mais cedo**.
3. Se ninguém do grupo submeteu nada, há **sorteio**.

O professor pode **corrigir o vencedor à mão**, por exemplo se alguém ficou sem rede.

### Rondas
- As rondas **fecham sozinhas** quando todos os grupos estão decididos ou o tempo acaba. Submissões que já iam a caminho têm **30 segundos de tolerância**.
- O professor carrega em **"Próxima ronda"** e novos grupos são sorteados.

### Se fores eliminado
Não ficas parado: passas a **espectador** e vês o bracket ao vivo. **Continuas a poder resolver os exercícios em modo treino, e eles ainda dão pontos** (mas já não voltas ao torneio).

### No fim
- **Pódio** com medalhas por cima do avatar: 🥇 **Ouro** (1.º) · 🟫 **Bronze** (2.º) · 🟧 **Cobre** (3.º).
- O 2.º e o 3.º são os finalistas melhor classificados (mais testes, depois quem submeteu mais cedo).
- **Diploma** em PNG para toda a gente: *"Campeão do torneio"* ou *"Chegaste à ronda N"*.
- O projetor mostra o **bracket ao estilo de um Mundial**: duas metades que convergem para a Final ao centro, com o troféu.

---

## 5. Torneio Formato Aula

Baseado na aula **"Operação Decomposição"**. Joga-se **individualmente ou por agências** (equipas de 2 a 4, com nome à escolha).

### Rondas

| Ronda | Nível | Pontos por missão | Multiplicador |
|---|---|---|---|
| R1 | Fácil | 10 | ×1 |
| R2 | Fácil-Médio | 10 | ×1 |
| R3 | Médio | 15 | ×1 |
| R4 | Médio-Difícil | 15 | ×1 |
| R5 | Difícil | 15 | **×2** |
| 👹 | **Boss Battle**: toda a turma contra um problema | 30 por quem resolve | — |

Cada ronda tem **3 missões**.

### Pontuação
- **Missão certa:** pontos da ronda × multiplicador.
- **Usaste uma pista nessa missão:** **metade** (0,5×). Numa agência, conta se **qualquer** membro a abriu.
- **Bónus de rapidez:** **+5** para o primeiro a ter todas as missões da ronda certas. O bónus não é multiplicado e não existe no boss.
- **Erros não tiram pontos.** Podes tentar quantas vezes quiseres.
- **Agências:** a missão conta **uma vez** para a agência, seja quem for que a resolva.

### Fim
Pódio, ranking final e diploma em PNG para descarregar.

---

## 6. Pontos pessoais

Os pontos ficam **guardados na tua conta** e acumulam de torneio para torneio.

| Conquista | Pontos |
|---|---|
| Participar num torneio (entrar e submeter pelo menos uma vez) | **+5** |
| Exercício resolvido, fácil (★–★★) | **+10** |
| Exercício resolvido, médio (★★★) | **+20** |
| Exercício resolvido, difícil (★★★★–★★★★★) | **+30** |
| Vencer um grupo (passar de ronda) | **+15** |
| 🥇 Campeão do torneio | **+100** |
| 🟫 2.º lugar | **+50** |
| 🟧 3.º lugar | **+25** |

- Cada exercício só dá pontos **uma vez** por torneio.
- Os **eliminados** continuam a ganhar os pontos dos exercícios que resolvem.
- Quando ganhas pontos aparece um aviso no ecrã, por exemplo **"+20 pts"**.
- O professor pode ajustar estes valores para cada torneio.

---

## 7. Leaderboard público e privacidade

O ecrã principal tem um **🏆 Leaderboard** que qualquer pessoa pode ver (mesmo sem sessão iniciada), com os separadores **Geral** e **Esta semana** (recomeça à segunda-feira).

- 🔒 **Só apareces se quiseres.** No **Perfil** há o interruptor *"Mostrar o meu nome e pontuação no leaderboard público"*. Por omissão está **desligado**.
- No leaderboard público aparece apenas o teu **nome a mostrar** e os pontos. **Nunca** aparece o teu nome de utilizador nem a turma.
- Mesmo escondido, vês sempre **a tua posição** (*"Tu: #7 · 230 pts (escondido)"*).
- **Dentro de um torneio** aparecem sempre **todos** os participantes no bracket, no ranking e no pódio. A opção de privacidade só se aplica ao leaderboard público da página inicial.
- Os professores não entram no leaderboard.

---

## 8. Guia do professor

### Antes da aula
1. **Criar a turma:** no **Painel do professor**, em *Nova turma*. A turma recebe um **código de entrada** que mostras aos alunos. Também podes **importar alunos por CSV** (`utilizador,nome`). Cada aluno recebe uma palavra-passe temporária, que tem de mudar no primeiro login.
2. **Problemas:** os problemas novos estão em **rascunho**. Nos teus torneios podes usar rascunhos (marcados *[rascunho]*), porque os alunos só os veem quando a ronda começa.

### Criar um torneio
1. Em **Torneios → Novo torneio**, escolhe a turma, o nome e o formato:
   - **Eliminatória (grupos)**, que é a opção por omissão. Define os *alunos por grupo* (3–6) e quantos *passam por grupo* (1–2).
   - **Formato Aula (rondas com pontos)**: individual ou por agências.
2. Os exercícios de cada ronda são **escolhidos automaticamente** pela matéria dada e pela dificuldade. Em **Editar** podes trocar o exercício e a duração de cada ronda enquanto ela não começou.
3. Carrega em **📽 Abrir projetor** e põe esse separador no ecrã da sala. O projetor mostra o código de entrada em grande e quantos alunos já entraram.
4. Na Eliminatória, a **pré-visualização do bracket** mostra o caminho com o número atual de alunos (ex. *"Ronda 1: 5 grupos (4,4,4,4,4), passam 5 (1 por grupo) · Final: 5 jogadores"*). Podes alterar a configuração e carregar em **Guardar configuração** enquanto o torneio está na sala de espera.

### Durante o torneio

| Botão | O que faz |
|---|---|
| ▶ **Próxima ronda** / **Iniciar ronda** | Sorteia os grupos (Eliminatória) e começa a ronda (1 toque) |
| ⏸ **Pausar** / **Retomar** | Congela o tempo, por exemplo se a rede cair para todos |
| ⏱ **+2 minutos** | Dá mais tempo |
| ■ **Fechar ronda** | Fecha já a ronda (pede **um segundo toque** para confirmar) |
| 🏆 **Definir vencedor** | Eliminatória: corrige à mão o vencedor de um grupo |
| 🏁 **Terminar torneio** | Termina e mostra o pódio (pede segundo toque) |

- Na **Eliminatória** as rondas **fecham sozinhas**. Só tens de carregar em *Próxima ronda*.
- **Presença:** vês quem está 🟢 ligado ou 🔴 offline.
- **Alunos atrasados** podem entrar a qualquer momento. No Formato Aula com agências, podem juntar-se a uma agência sozinhos, e tu também os podes mudar de agência.

### No projetor
- **Eliminatória:** bracket ao estilo de um Mundial, grupos com barras de progresso ao vivo, avisos *"🏆 Inês venceu o Grupo 2"*, temporizador grande e celebração do campeão.
- **Formato Aula:** ronda atual, temporizador, ranking animado, *"BOSS DERROTADO!"* e pódio final.

---

## 9. Problemas de rede e perguntas frequentes

**A rede caiu a meio. Perdi o código?**
Não. O rascunho está guardado no teu dispositivo. O indicador mostra 🟢 ligado / 🟡 a reconectar / 🔴 offline, e a app volta a ligar-se sozinha e recupera o estado do torneio.

**Submeti sem rede. O que acontece?**
A submissão fica em fila e é enviada quando a ligação voltar. Nunca é contada duas vezes.

**O tempo acabou enquanto enviava.**
O servidor aceita submissões que cheguem até **30 segundos** depois do fim. Quem manda é o relógio do servidor, não o do teu dispositivo.

**A página parece desformatada depois de uma atualização.**
Recarrega a página (no computador: Ctrl+Shift+R / Cmd+Shift+R).

**Posso usar matéria que ainda não demos?**
Sim! O que conta é o resultado. A única exceção são os exercícios 🧱, que pedem uma estrutura específica.

**Os meus colegas veem o meu código?**
Nunca. Os adversários veem apenas quantos testes passaste e quantas tentativas fizeste.

**Posso apagar a minha conta ou os meus dados?**
Sim. No **Perfil** podes **exportar** os teus dados ou **apagar a conta** (pede a palavra-passe).

---

## 10. Modos em breve

Estes modos aparecem com o selo **"Em breve"** no ecrã principal:

| Modo | Ideia |
|---|---|
| 🗺️ **Mundo** | Modo treino como um mapa de aventura, com uma região por bloco das aulas, santuários (exercícios curtos), masmorras com corações e relíquias que desbloqueiam a região seguinte |
| 🗡️ **Arena de Algoritmia** | Exercícios ao estilo LeetCode em 3 níveis: **Hard** (≈ fácil), **Extra Hard** (≈ médio) e **Hardcore Insane** (≈ difícil), com testes grandes (soluções lentas dão "tempo excedido") e explicação depois de resolver |
| ⚔️ **Duelo** | 1 contra 1 com um colega, por código de convite, à melhor de 3, com rating ELO |
| 📊 **Ranking** | Rankings da turma, semanais e de honras ("Bom adversário", "Solução elegante", "Fair play") |

---

*Bom jogo! E se tiveres dúvidas, o pato de borracha está a ouvir: explica-lhe o teu código antes de perguntares ao professor. 🦆*
