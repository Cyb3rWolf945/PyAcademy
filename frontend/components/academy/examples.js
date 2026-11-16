// Exemplos das aulas para o protótipo da Academia. O `py` é exatamente o código das soluções dos slides
// (convenção do professor: variáveis inicializadas no topo, constantes em MAIÚSCULAS). `demoPath` é a ordem do
// "Passo a passo (demo)"; os ciclos são percorridos 3 vezes.
// Nota: em "média" e "segundos" o bloco Definir só existe no fluxograma (py: null), porque o Python dos slides
// não tem essas linhas de declaração.

export const EXAMPLES = [
  {
    id: "media-3-notas",
    titulo: { pt: "Média de 3 notas", en: "Average of 3 marks" },
    corpo: [
      { id: "d", tipo: "definir", texto: { pt: "definir real nota1, nota2, nota3, media", en: "define real nota1, nota2, nota3, media" }, py: null },
      { id: "l1", tipo: "ler", texto: { pt: "ler nota1", en: "read nota1" }, py: 'nota1 = float(input("Nota 1: "))' },
      { id: "l2", tipo: "ler", texto: { pt: "ler nota2", en: "read nota2" }, py: 'nota2 = float(input("Nota 2: "))' },
      { id: "l3", tipo: "ler", texto: { pt: "ler nota3", en: "read nota3" }, py: 'nota3 = float(input("Nota 3: "))' },
      { id: "c", tipo: "calcular", texto: { pt: "media = (nota1 + nota2 + nota3) / 3", en: "media = (nota1 + nota2 + nota3) / 3" }, py: "media = (nota1 + nota2 + nota3) / 3" },
      { id: "e", tipo: "escrever", texto: { pt: 'escrever "Média = " + media', en: 'write "Average = " + media' }, py: 'print("Média =", media)' },
    ],
    demoPath: ["d", "l1", "l2", "l3", "c", "e"],
  },
  {
    id: "segundos-minutos",
    titulo: { pt: "Segundos em minutos", en: "Seconds to minutes" },
    corpo: [
      { id: "d", tipo: "definir", texto: { pt: "definir inteiro total, minutos, segundos", en: "define integer total, minutos, segundos" }, py: null },
      { id: "l", tipo: "ler", texto: { pt: "ler total", en: "read total" }, py: 'total = int(input("Segundos: "))' },
      { id: "c1", tipo: "calcular", texto: { pt: "minutos = total / 60", en: "minutos = total / 60 (whole part)" }, py: "minutos = total // 60" },
      { id: "c2", tipo: "calcular", texto: { pt: "segundos = total % 60", en: "segundos = total % 60" }, py: "segundos = total % 60" },
      { id: "e", tipo: "escrever", texto: { pt: 'escrever minutos + " min e " + segundos + " s"', en: 'write minutos + " min and " + segundos + " s"' }, py: 'print(minutos, "min e", segundos, "s")' },
    ],
    demoPath: ["d", "l", "c1", "c2", "e"],
  },
  {
    id: "cafe",
    titulo: { pt: "Ainda dá para um café?", en: "Time for a coffee?" },
    corpo: [
      { id: "d", tipo: "definir", texto: { pt: "declarar: minutos_para_aula = 0", en: "declare: minutos_para_aula = 0" }, py: "minutos_para_aula = 0" },
      { id: "l", tipo: "ler", texto: { pt: "ler minutos para a aula", en: "read minutes until class" }, py: 'minutos_para_aula = int(input("Quantos minutos faltam para a aula? "))' },
      {
        id: "s1", tipo: "se", cond: { pt: "minutos > 10 ?", en: "minutes > 10 ?" }, py: "minutos_para_aula > 10",
        sim: [{ id: "e1", tipo: "escrever", texto: { pt: "Ainda dá para um café", en: "Time for a coffee" }, py: 'print("Ainda dá para um café")' }],
        nao: [{
          id: "s2", tipo: "se", cond: { pt: "minutos >= 0 ?", en: "minutes >= 0 ?" }, py: "minutos_para_aula >= 0",
          sim: [{ id: "e2", tipo: "escrever", texto: { pt: "Corre, corre, CORRE!", en: "Run, run, RUN!" }, py: 'print("Corre, corre, CORRE!")' }],
          nao: [{ id: "e3", tipo: "escrever", texto: { pt: "Entra na boa e finge que estás atento desde o início", en: "Walk in calmly and pretend you were paying attention all along" }, py: 'print("Entra na boa e finge que estás atento desde o início")' }],
        }],
      },
    ],
    demoPath: ["d", "l", "s1", "s2", "e3"],
  },
  {
    id: "foguetao",
    titulo: { pt: "Contagem decrescente do foguetão", en: "Rocket countdown" },
    corpo: [
      { id: "d", tipo: "definir", texto: { pt: "t = 5", en: "t = 5" }, py: "t = 5" },
      {
        id: "w", tipo: "enquanto", cond: { pt: "t > 0 ?", en: "t > 0 ?" }, py: "t > 0",
        corpo: [
          { id: "e1", tipo: "escrever", texto: { pt: "escrever t", en: "write t" }, py: "print(t)" },
          { id: "c", tipo: "calcular", texto: { pt: "t = t - 1", en: "t = t - 1" }, py: "t = t - 1" },
        ],
      },
      { id: "e2", tipo: "escrever", texto: { pt: 'escrever "Descolagem!"', en: 'write "Liftoff!"' }, py: 'print("Descolagem!")' },
    ],
    // 3 voltas do ciclo e depois a saída (a condição é avaliada 4 vezes)
    demoPath: ["d", "w", "e1", "c", "w", "e1", "c", "w", "e1", "c", "w", "e2"],
  },
];

// ---- Funções (deck "modularização": slides 14, 15, 17, 19). Python igual ao dos slides, sem os números de linha. ----
const tx = (pt, en) => ({ pt, en });

EXAMPLES.push(
  {
    id: "soma-lista-turmas",
    titulo: tx("Soma de duas turmas com uma função", "Sum of two classes with one function"),
    funcoes: [{
      id: "f", nome: "soma_lista", params: "numeros",
      corpo: [
        { id: "f1", tipo: "definir", texto: tx("soma = 0", "soma = 0"), py: "soma = 0" },
        {
          id: "fp", tipo: "para", texto: tx("para cada numero em numeros", "for each numero in numeros"), py: "for numero in numeros",
          corpo: [{ id: "f2", tipo: "calcular", texto: tx("soma = soma + numero", "soma = soma + numero"), py: "soma = soma + numero" }],
        },
        { id: "f3", tipo: "devolver", texto: tx("Devolver soma", "Return soma"), py: "return soma" },
      ],
    }],
    corpo: [
      { id: "ta", tipo: "definir", texto: tx("notas_turma_a = [14, 9, 16, 12]", "notas_turma_a = [14, 9, 16, 12]"), py: "notas_turma_a = [14, 9, 16, 12]" },
      { id: "tb", tipo: "definir", texto: tx("notas_turma_b = [18, 7, 15, 20, 11]", "notas_turma_b = [18, 7, 15, 20, 11]"), py: "notas_turma_b = [18, 7, 15, 20, 11]" },
      { id: "ca", tipo: "chamar", branco_antes: true, texto: tx('escrever "Soma da turma A:" e soma_lista(notas_turma_a)', 'write "Sum of class A:" and soma_lista(notas_turma_a)'), py: 'print("Soma da turma A:", soma_lista(notas_turma_a))' },
      { id: "cb", tipo: "chamar", texto: tx('escrever "Soma da turma B:" e soma_lista(notas_turma_b)', 'write "Sum of class B:" and soma_lista(notas_turma_b)'), py: 'print("Soma da turma B:", soma_lista(notas_turma_b))' },
    ],
    demoPath: ["ta", "tb", "ca", "f", "f1", "fp", "f2", "fp", "f2", "fp", "f3", "cb", "f"],
  },
  {
    id: "dobro-return",
    titulo: tx("dobro com return", "dobro with return"),
    funcoes: [{
      id: "f", nome: "dobro", params: "numero",
      corpo: [{ id: "f1", tipo: "devolver", texto: tx("Devolver numero * 2", "Return numero * 2"), py: "return numero * 2" }],
    }],
    corpo: [
      { id: "c", tipo: "chamar", texto: tx("resultado = dobro(5)", "resultado = dobro(5)"), py: "resultado = dobro(5)" },
      { id: "e", tipo: "escrever", texto: tx("escrever resultado", "write resultado"), py: "print(resultado)" },
    ],
    demoPath: ["c", "f", "f1", "e"],
  },
  {
    id: "media-segura",
    titulo: tx("Vários return: media_segura", "Several returns: media_segura"),
    funcoes: [{
      id: "f", nome: "media_segura", params: "numeros",
      corpo: [
        {
          id: "s", tipo: "se", cond: tx("len(numeros) == 0 ?", "len(numeros) == 0 ?"), py: "len(numeros) == 0",
          sim: [{ id: "r1", tipo: "devolver", texto: tx('Devolver "não"', 'Return "não"'), py: 'return "não"' }], nao: [],
        },
        { id: "r2", tipo: "devolver", texto: tx("Devolver soma_lista(numeros) / len(numeros)", "Return soma_lista(numeros) / len(numeros)"), py: "return soma_lista(numeros) / len(numeros)" },
      ],
    }],
    corpo: [],
    demoPath: ["f", "s", "r1"],
  },
  {
    id: "pedir-numero-positivo",
    titulo: tx("Validação sem repetir", "Validation without repeating"),
    funcoes: [{
      id: "f", nome: "pedir_numero_positivo", params: "mensagem",
      corpo: [
        { id: "f1", tipo: "definir", texto: tx("valor = -1", "valor = -1"), py: "valor = -1" },
        {
          id: "w", tipo: "enquanto", cond: tx("valor <= 0 ?", "valor <= 0 ?"), py: "valor <= 0",
          corpo: [
            { id: "l", tipo: "ler", texto: tx("ler valor", "read valor"), py: "valor = int(input(mensagem))" },
            {
              id: "s", tipo: "se", cond: tx("valor <= 0 ?", "valor <= 0 ?"), py: "valor <= 0",
              sim: [{ id: "e", tipo: "escrever", texto: tx("Tem de ser um número positivo.", "It must be a positive number."), py: 'print("Tem de ser um número positivo.")' }], nao: [],
            },
          ],
        },
        { id: "r", tipo: "devolver", texto: tx("Devolver valor", "Return valor"), py: "return valor" },
      ],
    }],
    corpo: [
      { id: "c1", tipo: "chamar", texto: tx('idade = pedir_numero_positivo("Idade: ")', 'idade = pedir_numero_positivo("Idade: ")'), py: 'idade = pedir_numero_positivo("Idade: ")' },
      { id: "c2", tipo: "chamar", texto: tx('peso = pedir_numero_positivo("Peso: ")', 'peso = pedir_numero_positivo("Peso: ")'), py: 'peso = pedir_numero_positivo("Peso: ")' },
      { id: "c3", tipo: "chamar", texto: tx('altura = pedir_numero_positivo("Altura: ")', 'altura = pedir_numero_positivo("Altura: ")'), py: 'altura = pedir_numero_positivo("Altura: ")' },
    ],
    demoPath: ["c1", "f", "f1", "w", "l", "s", "e", "w", "l", "s", "w", "r", "c2"],
  },
);

export const exampleById = (id) => EXAMPLES.find((e) => e.id === id) || EXAMPLES[0];
