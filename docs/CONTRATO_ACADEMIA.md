# Contrato: Academia — fase A0 (protótipo para aprovação do professor)

O plano completo está em [PLANO_ACADEMIA.md](PLANO_ACADEMIA.md).
**A0 não liga ao backend nem dá pontos.** O objetivo é o professor aprovar a **notação do fluxograma** e o **layout** antes de A1.
Dois agentes trabalham em paralelo:
- **FX:** fluxograma + vista Python ligadas;
- **UI:** maqueta das páginas da Academia e do módulo.

## 1. Modelo do programa (fonte única de verdade)
É um programa **estruturado** (sequência de instruções e blocos aninhados), e não um grafo livre. A partir dele geram-se o fluxograma e o Python, que por isso nunca se contradizem.

```js
// frontend/components/academy/model.js (exporta tipos via JSDoc; sem build)
Program = {
  id: "media-3-notas",
  titulo: { pt, en },
  corpo: [ Stmt, ... ]          // Início e Fim são automáticos no fluxograma
}
Stmt =
  | { id, tipo: "definir",  texto: {pt,en}, py: "nota1 = 0" }          // inicialização no topo (convenção do professor)
  | { id, tipo: "ler",      texto: {pt,en}, py: 'nota1 = float(input("Nota 1: "))' }
  | { id, tipo: "calcular", texto: {pt,en}, py: "media = (nota1 + nota2 + nota3) / 3" }
  | { id, tipo: "escrever", texto: {pt,en}, py: 'print("Média =", media)' }
  | { id, tipo: "se", cond: {pt,en}, py: "media >= NOTA_MINIMA",
      sim: [Stmt...], nao: [Stmt...] }                                   // nao com um único "se" → elif
  | { id, tipo: "enquanto", cond: {pt,en}, py: "contador < 5", corpo: [Stmt...] }
  | { id, tipo: "para",     texto: {pt,en}, py: "for i in range(1, 6)", corpo: [Stmt...] }
```
- **Geração do Python** (`toPython(program, locale)` → `[{line, indent, stmtId}]`): instruções simples → `py`; `se` → `if <py>:` + o ramo `sim` indentado; `nao` → `else:` (ou `elif` quando `nao` é um único `se`); `enquanto` → `while <py>:`; `para` → `<py>:`. Indentação de 4 espaços. Cada linha guarda o `stmtId` (é isto que permite a ligação bloco↔linha).
- O **texto do fluxograma** é o rótulo em português/inglês (`texto`/`cond`). Pode diferir do Python, como nos slides (ex. "Ler nota1" ↔ `nota1 = float(input(...))`).
- Nos exemplos, as **constantes** vão em MAIÚSCULAS e as variáveis são inicializadas no topo, tal como nas aulas.

## 2. Fluxograma: estilo limpo, igual aos slides (NÃO pixel art)
`frontend/components/academy/flowchart.js` → `renderFlowchart(container, program, {locale, onSelect, highlight})` → `{ select(stmtId), clear(), destroy() }`. SVG vetorial criado com `document.createElementNS` (nunca HTML em bruto).

| Bloco | Forma | Cor (claro) |
|---|---|---|
| Início / Fim | pílula (retângulo com cantos totalmente arredondados) | verde `#8cc63f`, texto branco |
| Ler / Escrever | paralelogramo | lilás claro `#ece9fb`, contorno `#8f86d6` |
| Definir / Calcular | retângulo | lilás claro `#ece9fb`, contorno `#8f86d6` |
| Decisão (`se`, `enquanto`) | losango | azul-escuro `#1f2a44`, texto branco |
| Setas | linhas finas 1.5 px, ponta triangular | cinza-escuro `#4a4f5c` |

- **Rótulos "Sim"/"Não"** junto às saídas do losango. "Sim" para baixo; "Não" para a direita (decisão) ou para a saída do ciclo.
- **Layout:**
  - vertical, de cima para baixo, e centrado;
  - `se/senão` com os dois ramos lado a lado, que voltam a juntar-se por baixo;
  - `enquanto`/`para`: o corpo fica por baixo do losango, uma seta de volta sobe pela esquerda até ao losango, e o "Não" sai pela direita para a instrução seguinte;
  - medidas calculadas a partir do texto (`getBBox`) e um `viewBox` que se ajusta ao contentor sem scroll horizontal em 375 px (escala para baixo).
- **Tipografia:** sans-serif do sistema (`system-ui`) a 14–16 px. **Nada de fontes pixel no fluxograma nem no código.**
- **Tema escuro:** fundo do diagrama claro (cartão branco com borda suave) **em todos os temas**, para manter as cores dos slides legíveis. A moldura à volta pode seguir o tema pixel.
- **Interação:**
  - tocar ou clicar num bloco chama `onSelect(stmtId)` e realça o bloco (contorno grosso `#f5a623` + leve sombra);
  - os blocos são focáveis (`tabindex=0`, `role="button"`, `aria-label` com o texto) e Enter/Espaço também seleciona;
  - `prefers-reduced-motion` desliga as transições.

## 3. Vista Python ligada
`frontend/components/academy/code-view.js` → `renderCode(container, program, {locale, onSelect})` → `{ select(stmtId), clear() }`.
- **Aspeto:** código em `font-mono` com números de linha, fundo claro como o diagrama e **uma faixa de cor à esquerda por tipo de bloco**, com as mesmas cores do fluxograma (verde para início/fim não se aplica; lilás para ler/escrever/definir/calcular; azul-escuro para `if`/`while`/`for`).
- **Realce:** clicar numa linha realça-a e chama `onSelect(stmtId)`. Todas as linhas do mesmo `stmtId` ficam realçadas (ex. `if` e a sua condição).
- **Ligação:** `components/academy/linked-view.js` → `renderLinked(container, program, {locale})` monta lado a lado (≥ 768 px) ou empilhado (telemóvel), com o fluxograma em cima, e liga os dois: selecionar num lado seleciona no outro e faz scroll até ele.
- **Sem execução** em A0 (o modo trace é da fase A2). Pode haver um botão "Passo a passo (demo)" que percorre os `stmtId` pela ordem, com um temporizador, só para mostrar a ideia. Os ciclos são percorridos 3 vezes numa sequência fixa definida no exemplo (`demoPath: [ids...]`).

## 4. Os 3 exemplos das aulas (`frontend/components/academy/examples.js`)
1. **Média de 3 notas** (Aula II–III, Ex. 3.1): definir `nota1, nota2, nota3, media` → ler as 3 → calcular `media = (nota1 + nota2 + nota3) / 3` → escrever.
2. **Segundos em minutos** (Ex. 3.2): definir → ler `total` → `minutos = total // 60` → `segundos = total % 60` → escrever `minutos, "min e", segundos, "s"`.
3. **"Ainda dá para um café?"** (Aula IV, Exercício A): definir `minutos_para_aula = 0` → ler → se `> 10` "Ainda dá para um café"; senão se `>= 0` "Corre, corre, CORRE!"; senão "Entra na boa e finge que estás atento desde o início".
4. *(Opcional, para validar o layout dos ciclos)*: **contagem decrescente do foguetão** (PDF de ciclos): `t = 5`, enquanto `t > 0` escrever `t` e `t = t - 1`, depois escrever "Descolagem!".

Os textos ficam em PT-PT e EN. O `py` é exatamente o código das soluções dos slides.

## 5. Maqueta das páginas (agente UI), com dados estáticos
- **`frontend/pages/academy/academy.html` + `academy.js`:** a Academia.
  - **Cabeçalho:** título "Academia" + subtítulo e um resumo do progresso (módulos concluídos, pontos, sequência de dias), com dados de exemplo.
  - **Sequência vertical** de cartões M0–M7 + "Caça aos bugs", ligados por uma linha/trilho vertical com nós de estado.
  - **Cada cartão tem:**
    - número;
    - título;
    - ícone sprite;
    - descrição curta;
    - dificuldade (★);
    - nº de secções;
    - barra de %;
    - "pontos ganhos / possíveis";
    - selo da peça;
    - estado 🔒 / ▶ Em curso / ✅ Concluído;
    - o motivo do desbloqueio, quando aplicável ("Aberto pelo professor", "Teste de salto disponível").
  - **Destaque no topo:** "Missão do professor" com um módulo atribuído.
  - **Dados de exemplo:** M0 ✅ 100%, M1 ▶ 60%, M2 aberto pelo professor 0%, M3 🔒 (com "teste de salto"), M4–M7 🔒.
- **`frontend/pages/module/module.html` + `module.js`:** a página do módulo (exemplo: M1 "Algoritmos e fluxogramas").
  - Lista **vertical numerada de secções** com estado (✅ / atual / 🔒) e pontos de cada uma.
  - Ao abrir a secção atual aparecem 3 blocos:
    1. **Aprender:** texto curto + a vista ligada do agente FX com o exemplo "Média de 3 notas", importada de `components/academy/linked-view.js` (se ainda não existir, mostra um *placeholder*, porque os dois agentes trabalham em paralelo);
    2. **Praticar:** uma *maqueta* de uma atividade "Ordenar o fluxograma", com cartões estáticos (sem lógica de arrastar em A0);
    3. **Responde para concluir:** uma pergunta de escolha múltipla com o botão "Concluir secção" (simulado no cliente: marca ✅ e mostra "+3 pts").
  - **Painel lateral** (em baixo no telemóvel): progresso do módulo, "📑 Slides da aula" (placeholder com miniaturas cinzentas) e "📖 Leitura recomendada: Python Basics, cap. …".
- **Visual:**
  - **moldura pixel art** (skill `pixel-art`: cartões, selos, barras, trilho, temas);
  - **conteúdo didático limpo** (texto em `font-ui`/sistema, fluxograma e código como no §2–3);
  - animações GSAP leves via `services/motion.js` (o trilho preenche, os cartões entram);
  - mobile first (375 px) e PT-PT/EN.
- **Navegação:** o cartão "Mundo" da home passa a chamar-se **"Academia"** e a apontar para `/pages/academy/academy.html` (o selo "Em breve" sai; aparece "Protótipo" como badge). O item "Mundo" da navegação muda também para "Academia".

## 6. Quem é dono de que ficheiros
- **FX:** `frontend/components/academy/{model,flowchart,code-view,linked-view,examples}.js`, uma secção `/* academy flowchart (FX) */` no **fim** de `styles/app.css` (só acrescentar), `frontend/pages/academy/prototype.html` + `prototype.js` (página de demonstração com os 4 exemplos e um seletor) e i18n `academy/*` (só as chaves `fx.*`).
- **UI:**
  - `frontend/pages/academy/{academy.html,academy.js}`, `frontend/pages/module/**`;
  - uma secção `/* academy pages (UI) */` no fim de `styles/app.css` (só acrescentar);
  - i18n `academy/*` (chaves `ui.*`);
  - `pages/home/home.html|home.js` e `components/bottom-nav.js`, só para a renomeação para "Academia";
  - sprites novos em `assets/gen_assets.py` (ícones dos módulos e selos das peças).
- A área i18n `academy` tem de ser criada em `frontend/i18n/academy/{pt-PT,en}.json` e acrescentada a `frontend/i18n/areas.json`. **Quem a cria é o FX; o UI espera e acrescenta as suas chaves** (prefixos diferentes, por isso não há conflito; editar com cuidado, sem reformatar).
- Ninguém mexe no backend em A0.

## 7. Verificação de A0
- `prototype.html`: os 4 exemplos desenhados corretamente; clicar num bloco realça a linha e vice-versa; teclado; 375 px sem scroll horizontal; temas claro e escuro; consola limpa e sem violações de CSP.
- **O Python gerado** de cada exemplo é **igual** ao código dos slides. Há um teste em JS corrido no browser, ou um teste Python que lê `examples.js` e confirma que um runner com a mesma lógica de `toPython` dá esse resultado. Basta um script de verificação documentado.
- **Maquetas:** capturas a 375×812 e 1280×800, num tema claro e num escuro.
- `pytest` continua verde e `check_i18n` dá 0 erros.
- **Entrega ao professor:** capturas + link local das 3 páginas, para aprovar a notação e o layout.

---

# Fase A1 — Academia real (backend + atividades + M0/M1 + slides)

O professor aprovou a notação e o layout de A0. A A1 liga tudo: conteúdos em YAML, progresso, pontos, desbloqueio, atividades interativas e slides das aulas. **Ainda fora da A1:** modo trace, Explorar/Prever/Traduzir/Caça ao erro/Escrever, variantes adaptativas, painel do professor e teste de salto (A2–A3).

## 8. Conteúdos (`backend/content/academy/`)
- `modules.yaml`: lista ordenada de módulos.
  ```yaml
  - {id: m0, ordem: 0, titulo: {pt,en}, descricao: {pt,en}, icone: m0, peca: inicio-fim, dificuldade: 1, bloco: "1", sempre_aberto: true}
  - {id: m1, ordem: 1, ..., bloco: "1"}
  - {id: m2, ordem: 2, ..., bloco: "2"}   # bloco = id do curriculum.yaml; se o bloco estiver aberto, o módulo abre (ver §11)
  ```
  Constam M0–M7 e `bugs`. Só M0 e M1 têm secções na A1; os outros aparecem como "Em breve" (sem secções).
- `<modulo>/<nn>-<slug>.yaml`: uma secção.
  ```yaml
  id: m1-04-media            # único
  modulo: m1
  ordem: 4
  titulo: {pt, en}
  aprender: {pt, en}         # Markdown simples (parágrafos, **negrito**, `código`, listas). Texto ORIGINAL.
  exemplo: <Program>         # opcional: o mesmo modelo de §1 (corpo de Stmt), em YAML
  slides: [{deck: aula-2, de: 23, ate: 23}]   # opcional: referências aos slides da aula
  leitura: {pt, en}          # opcional: "Python Basics, cap. 3.3 — Criar uma variável"
  pistas: [{pt, en}]         # 0–2, para a verificação
  atividades: [Atividade]    # 1–3 (praticar). Não dão pontos; o progresso fica registado.
  verificacao: {pergunta: {pt,en}, opcoes: [{pt,en}], resposta: [idx]}   # "Responde para concluir" (escolha múltipla; resposta pode ter vários idx)
  ```
- **Tipos de atividade** (A1):
  | tipo | dados | resposta enviada pelo cliente |
  |---|---|---|
  | `ligar` | usa `exemplo`; `ids` opcional (subconjunto de stmt ids, omissão = todos com `py`) | `{pares: {stmtId: stmtId}}`: bloco do fluxograma → linha de Python (cada linha identificada pelo stmtId; o cliente baralha) |
  | `ordenar_fluxograma` | usa `exemplo` (só sequências de 1.º nível na A1) | `{ordem: [stmtId...]}` |
  | `ordenar_python` | usa `exemplo` | `{ordem: [stmtId...]}` |
  | `ordenar_lista` | `itens: [{id, texto:{pt,en}}]` na ordem certa; `enunciado` | `{ordem: [id...]}` |
  | `completar` | usa `exemplo`; `lacunas: [{stmt, lado: py\|fluxo, modelo: {pt,en} com "___", respostas: ["3", "3.0"]}]` | `{valores: ["3", ...]}` (comparação normalizada: espaços/maiúsculas, números 3 = 3.0) |
  | `pergunta` | `pergunta, opcoes, resposta` (como `verificacao`); pode mostrar o `exemplo` | `{escolha: [idx]}` |
  Todas têm `enunciado: {pt,en}` e `explicacao: {pt,en}` (mostrada depois de acertar ou à 2.ª tentativa errada).
- **Validador** (`app.tools.validate_problems` passa a validar também a Academia, ou `app.tools.validate_academy`): esquema, ids únicos, `resposta` válidas, stmt ids existentes, bilingue completo, `slides` referem decks existentes no manifesto (aviso, não erro, se o deck ainda não foi importado).

## 9. Backend
- **Modelos + migração `0005`:**
  - `academy_progress (user_id, section_id, started_at, completed_at, verify_attempts, hints_used, first_try bool)`;
  - `academy_activity_log (user_id, section_id, activity_idx, attempts, solved_at)`;
  - `slide_decks (id, titulo, n_slides, imported_at)`.
- **Serviço** `services/academy.py`: carregamento (cache por mtime), estado dos módulos e das secções, desbloqueio (§11), correção (no servidor, as respostas **nunca** vão para o cliente) e pontos (§10).
- **API** (`api/academy.py`, com sessão iniciada; os erros vêm como `academy.*`):
  - `GET /api/academy` → `{modules: [{id, titulo, descricao, icone, peca, dificuldade, n_secoes, concluidas, pct, pontos_ganhos, pontos_possiveis, estado: locked|open|in_progress|done, motivo: prev_done|teacher|always|null, em_breve: bool}], resumo: {modulos_concluidos, pontos_academia, sequencia_dias}, missao: null}`.
  - `GET /api/academy/modules/{id}` → módulo + `secoes: [{id, ordem, titulo, estado: locked|current|done, pontos}]`.
  - `GET /api/academy/sections/{id}` → vista pública: tudo menos `resposta`/`respostas` e, nas ordenações, a ordem certa (o servidor manda os itens já baralhados). Secção bloqueada → 403 `academy.locked`.
  - `POST /api/academy/sections/{id}/activities/{idx}/answer {resposta}` → `{correta, explicacao?: {pt,en}, detalhe?: {...}}`. `detalhe` diz que posições/pares estão errados sem revelar a solução, e regista no log.
  - `GET /api/academy/sections/{id}/hints/{n}` → `{texto}` (incrementa `hints_used`).
  - `POST /api/academy/sections/{id}/verify {resposta}` → `{correta, concluida, pontos: n, badge?: {modulo, pontos}, proxima: section_id|null}`. Idempotente: se a secção já estava concluída, devolve `pontos: 0`.
  - Rate limit: 30 respostas/min por utilizador.
- **Slides:**
  - Ferramenta `python -m app.tools.import_slides <deck_id> <ficheiro .pptx|.pdf> --titulo "..."`: converte para PNG por slide (1280 px de largura) num contentor **converter** (LibreOffice headless + poppler, imagem fixa, perfil `tools`, sem rede).
  - Os PNG vão para o volume Docker `slides` (`/data/slides/<deck>/<n>.png` + `manifest.json`) e é criada a linha em `slide_decks`.
  - `GET /api/academy/slides` (lista) e `GET /api/academy/slides/{deck}/{n}` (PNG): **só com sessão iniciada** (aluno com turma ou professor), `Cache-Control: private, max-age=3600`, sem listagem de diretório e com o caminho validado (sem path traversal).
  - Nunca há slides no git, nem caminhos públicos estáticos.
  - Decks a importar já na A1 (a partir de `materiais_aulas/`): `aula-1`, `aula-2`, `aula-3`, `aula-3-5`, `aula-4`, `ciclos`.
- **Testes:**
  - desbloqueio (secções sequenciais; módulo aberto pelo anterior concluído ou pelo bloco aberto no currículo; M0 sempre aberto);
  - a vista pública não revela respostas nem a ordem certa;
  - a correção de cada tipo;
  - pontos idempotentes e badge uma só vez;
  - pista → metade (mínimo 1);
  - slides: 401 sem sessão, path traversal recusado;
  - validador.

## 10. Pontos (razões no livro `user_points`)
| Razão | Quando | Pontos |
|---|---|---|
| `academy_section` | 1.ª conclusão de uma secção (verificação certa) | M0–M1: **+3** · M2–M3: +5 · M4+: +8 |
| (pistas) | se a verificação foi feita com pistas abertas nessa secção | metade, **mínimo 1** |
| `academy_badge` | todas as secções de um módulo concluídas | **+25** (uma vez) |
| `academy_streak` | 1.ª secção concluída num novo dia (Europe/Lisbon) | **+2** (uma vez por dia) |
Usa `services/points.award()` (idempotente). Conta no leaderboard (Geral e Esta semana) com a flag de privacidade de sempre.

## 11. Desbloqueio (híbrido, aprovado)
- **Secções:** a 1.ª secção de um módulo aberto está sempre disponível; a seguinte abre quando a anterior está concluída. As secções concluídas podem ser revistas (sem voltar a dar pontos).
- **Módulos:**
  - M0 está sempre aberto (`sempre_aberto`);
  - um módulo abre se o **anterior estiver concluído** (`motivo: prev_done`) **ou** se o **bloco correspondente estiver aberto** no `curriculum.yaml` / painel (`motivo: teacher`);
  - o teste de salto chega na A3.

## 12. Frontend
- **Atividades** (agente FX): `components/academy/activities/{index,ligar,ordenar,completar,pergunta}.js`.
  - API comum: `renderActivity(container, activityPublic, { sectionId, idx, exemplo, locale, onSolved })`, que chama o endpoint de resposta e mostra o feedback/explicação.
  - **Arrastar** com pointer events (rato/dedo) **e** "tocar para colocar" (tocar no item → tocar no destino), com teclado (setas para mover, Enter para colocar) e ARIA (`aria-grabbed` não; usar `aria-describedby` com instruções e `aria-live` para os anúncios).
  - `ligar` desenha linhas entre o bloco do fluxograma (reutiliza `renderFlowchart`) e a linha de Python (reutiliza `renderCode`), ou usa pares de cartões em colunas no telemóvel.
  - `ordenar_fluxograma` mostra os blocos com as formas limpas do fluxograma, numa coluna vertical para ordenar.
  - `ordenar_python` mostra as linhas de código.
  - O estilo do conteúdo é limpo (§2–3), nunca pixel art.
- **Páginas** (agente UI):
  - `pages/academy` e `pages/module` passam a usar a API (§9) em vez de dados estáticos. `module.html?id=m1`, com a secção atual aberta e as anteriores revisitáveis. As secções bloqueadas mostram 🔒.
  - **Verificação:** pergunta + pistas (aviso "vale metade dos pontos") + resultado. Com `pontos > 0` aparecem um toast "+3 pts" e `celebrate`; com badge há uma celebração maior + o selo.
  - **Visualizador de slides** (`components/academy/slides-viewer.js`): miniaturas do intervalo `slides` da secção → modal com setas e teclado, imagens carregadas da API (com sessão).
  - O cartão da home perde o "Protótipo" (passa a "Academia" normal) e o selo "Em breve" fica só nos módulos sem secções.
- **i18n:** área `academy` (prefixos `fx.*`, `ui.*`, `act.*` para as atividades, `api.*` para erros do backend em `tournament_api`? **Não:** os erros do backend `academy.*` vão para um ficheiro novo `frontend/i18n/academy_api/{pt-PT,en}.json`, área `academy_api` em `areas.json`, criado pelo backend.

## 13. Conteúdos M0 e M1 (agente C, revisão do Opus)
Texto **original**, curto e encorajador, em PT-PT (+EN). Usa os exemplos e a voz das aulas (o café, o candeeiro, a conta de 42 €, a receita do bolo, os bombeiros) e cada secção tem referência aos slides certos.
- **M0 — Porquê programar? Linguagens e IA** (≈7 secções):
  1. *O computador segue instruções*: o que é programar; os 4 objetivos da cadeira (Aula I).
  2. *A máquina de Turing*: fita, cabeça e regras; "todo o computador é uma versão elétrica disto" (Aula II, slides 3–12).
  3. *Base 10 e base 2*: contar em binário (Aula II, slide 13).
  4. *Texto em binário*: ASCII, 'A' = 65 = 01000001; "Olá" como bytes (Aula II, slides 14–15). Atividade `completar` (converter um carácter).
  5. *Linguagens naturais vs formais*: ambiguidade ("aparece daqui a pouco" vs `esperar 5 minutos`) (Aula III, slide 11). Atividade `pergunta`: classificar frases.
  6. *A escada das linguagens e a IA*: `ordenar_lista` com a escada **linguagem natural → IA / prompts → semi-formal (pseudocódigo) → fluxograma → Python → código máquina / binário**. O texto explica a perspetiva do professor: **a IA é uma nova camada, quase junta da linguagem semi-formal**. Traduz ideias em português para código, mas **quem programa tem de ler, validar e decidir** (slide "IA vs. Pensamento Crítico": a IA gera código rapidamente, resolve problemas padrão e acelera a produção; a pessoa compreende a lógica, valida e adapta soluções e decide a melhor estrutura).
  7. *Valida a IA*: um fluxograma + Python "gerados por IA" para a média de 3 notas **sem parênteses** (`nota1 + nota2 + nota3 / 3`). Atividade `pergunta` "Qual é o erro?" + explicação da prioridade de operadores. Fecha com "a IA ajuda; tu decides".
  8. *Do problema ao algoritmo*: a conta de 42 € entre 4 amigos e os 6 passos "Como atacar um problema" (`ordenar_lista`) (Aula II, slides 18–19).
- **M1 — Algoritmos e fluxogramas** (≈6 secções):
  1. *O que é um algoritmo*: sequência finita e não ambígua; receita vaga vs refinada (`ordenar_lista` dos passos refinados) (Aula II, slides 20–21).
  2. *Computacional vs não computacional*: trocar uma lâmpada vs a distância do carro de bombeiros (`pergunta`) (slide 22).
  3. *Os símbolos do fluxograma*: Início/Fim, Ler, Definir/Executar, Escrever, Decisão, setas, com o exemplo do candeeiro (`pergunta` sobre a forma de cada bloco) (slide 23).
  4. *Do fluxograma ao Python: média de 3 notas*: `ligar` + `ordenar_python` (exemplo das aulas, Ex. 3.1).
  5. *Segundos em minutos*: `completar` (`//` e `%`) + `ordenar_fluxograma` (Ex. 3.2).
  6. *Desafio: km/h → m/s*: `ordenar_fluxograma` + `completar` (Ex. 4.1).
- Cada secção tem `verificacao` (1 pergunta), 1–2 `pistas` e 1–2 `atividades`, de 3 a 6 min. Os `exemplo` seguem as convenções do professor e o Python **igual ao dos slides**.

---

# Extensão M6 — Funções no modelo (fluxograma + Python)

Fonte: `materiais_aulas/modularização.pdf`, importado como deck **`funcoes`** (24 slides). Abrange: recap, código repetido, funções embutidas e bibliotecas (`random`), DRY, `def` e chamada, parâmetros/argumentos, type hints, valores por omissão, `return` vs `print`, vários `return` com `if`, somatório/produtório, validação sem *boilerplate*, âmbito local/global e funções que chamam funções.

## 14. Modelo do programa: novos campos e tipos
```js
Program = {
  id, titulo,
  funcoes?: [ { id, nome: "soma_lista", params: "numeros", texto?: {pt,en}, corpo: [Stmt...] } ],
  corpo: [Stmt...]            // programa principal
}
Stmt += 
  | { id, tipo: "chamar",   texto: {pt,en}, py: "soma_a = soma_lista(notas_turma_a)" }   // chamada usada como instrução
  | { id, tipo: "devolver", texto: {pt,en}, py: "return soma" }                           // só dentro de uma função
```
- Em `params` vai o texto exato dentro dos parênteses, incluindo type hints e valores por omissão (ex. `"nome, saudacao=\"Olá\""` ou `"largura: float, altura: float"`); o retorno anotado pode ir em `devolve_tipo: "float"` (→ `def f(...) -> float:`).
- **`toPython`:** primeiro cada função (`def nome(params):` + corpo indentado; a linha `def` tem `stmtId = funcao.id`), uma linha em branco entre funções e antes do principal, depois o `corpo` principal. As linhas em branco não têm `stmtId`.
- **Fluxograma:**
  - **o principal** fica como hoje (Início … Fim). Uma instrução `chamar` desenha-se como **processo pré-definido**: um retângulo lilás com **duas barras verticais** junto às margens esquerda e direita (símbolo padrão de sub-rotina);
  - **cada função** é desenhada como um **fluxograma à parte**, ao lado do principal (por baixo no telemóvel), com o título `nome(params)`. Começa numa pílula verde com o texto `nome(params)` em vez de "Início" e termina numa pílula com "Devolver …" (o bloco `devolver`) ou "Fim" se não houver `return`;
  - um `devolver` dentro de um ramo (`se`) é um terminal nesse ramo, sem ligar ao fim comum;
  - as chamadas `chamar` ficam ligadas visualmente à função: ao tocar numa chamada, o título da função correspondente fica realçado (por `nome`).
- **Ligação:** bloco ↔ linha como hoje; a linha `def` fica ligada à pílula de início da função.
- **Atividades:** `ordenar_python`, `ordenar_fluxograma`, `ligar` e `completar` aceitam um campo opcional `alvo: <funcao.id>` para trabalharem só dentro do corpo dessa função (sem `alvo` = programa principal). `ligar` pode também incluir os ids das funções (pílula de início ↔ linha `def`).
- O validador garante: nomes de função únicos; `devolver` só dentro de funções; `alvo` existente; ids únicos em todo o programa (principal + funções).

## 15. Conteúdo M6 — Funções (deck `funcoes`), +8 pts por secção
1. **O problema do código repetido** (slides 3–5): o exemplo das duas somas de turmas copiadas; pergunta "o que se repete?".
2. **Já usamos funções** (7–8): `int`, `float(input())`, `len`, `print`, métodos `lower/upper`, biblioteca `random.randint`.
3. **DRY: Don't Repeat Yourself** (9).
4. **Definir e chamar** (10): `def saudar()` chamada duas vezes; definir ≠ executar; `ordenar_python`.
5. **Parâmetros e argumentos** (11–13): `saudar_aluno(nome)`, argumentos "Edgar"/"Rhyanne"; type hints como documentação; valor por omissão e a regra da ordem; `completar` + `pergunta`.
6. **`return` vs `print`** (14–15): `dobro` com `print` vs com `return`; o `return` termina a função; vários `return` guardados por `if` (losango → saídas diferentes); `pergunta` + `completar`.
7. **Somatório numa função** (17–18): `soma_lista` + chamadas para as duas turmas (exemplo com `funcoes`); `ligar` + `ordenar_python` com `alvo`; somatório (acumulador em 0) vs produtório (acumulador em 1).
8. **Validação sem repetir** (19): `pedir_numero_positivo(mensagem)` com `while` + 3 chamadas.
9. **Âmbito local vs global** (20) e **funções que chamam funções** (21): `NameError` do `contador` local; `media_lista` usa `soma_lista`.
O Python dos exemplos é **igual ao dos slides**. Leitura: Python Basics cap. 6.1–6.3 e 6.6.
