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

export const exampleById = (id) => EXAMPLES.find((e) => e.id === id) || EXAMPLES[0];
