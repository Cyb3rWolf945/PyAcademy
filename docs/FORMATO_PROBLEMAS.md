# Formato dos problemas (YAML)

Cada problema é um ficheiro `.yaml` dentro de `backend/problems/`. A app carrega-os ao arrancar.
Este documento serve tanto para o professor como para os agentes que geram problemas.

## Regras gerais
- **Bilingue:** todos os textos levam `pt` (português de Portugal, nunca PT-BR) e `en`. Os outputs de **texto** esperados também levam as duas línguas (`stdout: {pt: "Corre!", en: "Run!"}`); os outputs só numéricos podem ser uma única string.
- **Originalidade:** enunciados escritos por nós. As variações das aulas mudam a história e os dados, nunca são cópias literais. Os problemas de algoritmia são clássicos com enunciado próprio, nunca o texto do LeetCode.
- **Currículo:** a `solucao_referencia` só pode usar a matéria do bloco do problema e dos anteriores (ver `backend/content/curriculum.yaml`, verificado por `check_curriculum`). **Os alunos podem usar o que quiserem:** conta o resultado.
- **Estilo do professor nas soluções de referência:** variáveis inicializadas no topo antes de ler (`nota = 0` e depois `nota = float(input("Nota: "))`), CONSTANTES em maiúsculas, nomes em português snake_case, comentários `# input / # processamento / # output` nos programas.
- **Tom:** humor do dia a dia de um estudante português (o gato com fome, o café antes da aula, o autocarro, a cantina, a impressora da biblioteca, o foguetão). Nada ofensivo.
- **Estado:** todos os problemas gerados entram como `estado: rascunho`. Só o professor os passa a `aprovado`.
- **Testes:** pelo menos 4 testes escondidos, incluindo casos-limite (zero, negativos, limites de faixas `>=`/`>`, lista vazia, um só elemento).

## Campos
```yaml
id: autocarro-ainda-da          # minúsculas, números e hífens; único
titulo: {pt: "...", en: "..."}
tipo: programa                  # programa | funcao | bug | quiz | decomposicao | tracar
bloco: "4"                      # "1".."7", "6b", "7b", "mais_alem"
regiao: encruzilhada            # vila | floresta | mercado | encruzilhada | rio | torre | cidadela | ilhas
dificuldade: 2                  # 1 a 5 estrelas
origem: variacao_aula           # variacao_aula | novo | boss | mais_alem
estado: rascunho
enunciado: {pt: "...", en: "..."}   # Markdown simples. Diz SEMPRE o formato de entrada e de saída.
codigo_inicial: null            # opcional; OBRIGATÓRIO no tipo bug (o programa com o erro)
assinatura: null                # tipo funcao: "nome_funcao(param1, param2)"
exemplos: [...]                 # visíveis ao aluno (pelo menos 1)
testes: [...]                   # escondidos (pelo menos 4)
comparacao: texto               # texto | numeros | exato
ordem_importa: true             # funcao: false = listas comparadas como conjuntos com repetição
requisitos: null                # opcional (ver abaixo)
pistas:                         # 0 a 2; usar uma pista dá metade do XP
  - {pt: "...", en: "..."}
erros_comuns: []                # opcional, feedback específico
limite_tempo_s: 2
solucao_referencia: |           # str, ou {pt, en} se o output de texto mudar com a língua
  ...
```

### Casos (exemplos/testes)
- `programa` e `bug` de programa: `{stdin: "10\n5\n", stdout: "Vai a andar"}` ou `stdout: {pt: "...", en: "..."}`. O prompt do `input()` é ignorado, por isso **não o incluas no stdout esperado**.
- `funcao` e `bug` de função: `{args: [[1, 2, 3]], devolve: 2}`.

### Comparação
- `texto`: ignora espaços a mais, linhas vazias no fim, maiúsculas e acentos.
- `numeros`: compara só os números do output, com tolerância de 0.01 (`14` = `14.0` = `14,0`). **Usa este modo sempre que o resultado é numérico**, para não chumbar pela frase à volta.
- `exato`: igual carácter a carácter. Só quando o formato for o objetivo do exercício.

### Requisitos (só quando a estrutura é o objetivo pedagógico)
Aparecem em destaque no enunciado (🧱). Menciona-os também no texto do enunciado.
```yaml
requisitos:
  usa: [while]                       # while | for | if | lista | funcao
  proibe: [max, sum, sorted]         # builtins/métodos proibidos
  define_funcao: {nome: calcular_media, parametros: 3}
  recursiva: true                    # só blocos 6b+
```
Mistura no banco: cerca de 70% com output livre (sem `requisitos`) e 30% com estrutura obrigatória. Os bosses têm sempre output livre.

### Tipos sem código (quiz, decomposicao, tracar)
Não levam `exemplos`, `testes` nem `solucao_referencia`. Usam `perguntas`:
```yaml
perguntas:
  - pergunta: {pt: "Qual é a constante neste problema?", en: "Which is the constant in this problem?"}
    codigo: null                   # tracar: o código a seguir (texto)
    opcoes:
      - {pt: "O preço da pizza", en: "The pizza price"}
      - {pt: "O custo de cada talher extra (0,50€)", en: "The cost of each extra cutlery set (€0.50)"}
    resposta: [1]                  # índices (a partir de 0) das opções certas
  - pergunta: {pt: "Qual é o valor de soma no fim?", en: "What is the value of soma at the end?"}
    codigo: |
      soma = 0
      for i in range(1, 4):
          soma = soma + i
    resposta_texto: "6"            # em alternativa a opcoes+resposta
```
- `decomposicao`: 3–4 perguntas sobre um enunciado: entradas, variáveis, constantes e operação (como na aula "Operação Decomposição").
- `tracar`: prever o output ou o valor de variáveis.
- `quiz`: conceitos (tabelas de verdade, De Morgan, tipos, prioridade de operadores, `for` vs `while`).

### Tipo bug
`codigo_inicial` traz um programa com **um** erro clássico: parênteses na média, `/` em vez de `//`, `input()` sem `int()`, off-by-one no `range`, acumulador não inicializado, ciclo infinito (falta incrementar), condição na ordem errada no `elif`. O enunciado explica o que o programa *devia* fazer. O `codigo_inicial` tem de falhar pelo menos um teste e a `solucao_referencia` é a versão corrigida.

### Algoritmia (Arena, estilo LeetCode)
Só tipo `funcao`, `bloco: "mais_alem"`, `regiao: ilhas`, mais:
```yaml
nivel_algo: hard                  # hard (≈LC Easy) | extra_hard (≈LC Medium) | hardcore_insane (≈LC Hard)
restricoes: {pt: "1 ≤ len(nums) ≤ 10^5", en: "1 ≤ len(nums) ≤ 10^5"}
solucao_ingenua: |                # tem de dar TLE num teste grande (ex. O(n²))
  ...
editorial: {pt: "Ideia, complexidade e explicação da solução", en: "..."}
```
Inclui pelo menos um **teste grande**, gerado com `args_gerador` (uma expressão Python que devolve a lista de argumentos). Pode usar `random` com semente fixa e `range`. Omite o `devolve`, que é calculado automaticamente pela solução de referência:
```yaml
testes:
  - args_gerador: "[[(i * 7919) % 100003 for i in range(100000)], 42]"
```
Os geradores são código do professor/autor (confiável), avaliados no runner, e nunca são enviados ao aluno. `limite_tempo_s` deve ser suficiente para a referência e insuficiente para a ingénua.
