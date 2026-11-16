// Verificação A0: o Python gerado por toPython() tem de ser IGUAL ao código das soluções dos slides.
// Corre sem browser e sem dependências, num contentor descartável (a partir da raiz do projeto):
//   docker run --rm -v "$PWD/frontend:/f:ro" node:20-alpine node /f/components/academy/verify-python.mjs
// Origem do código esperado: slides de Aula II-III (Ex. 3.1 e 3.2), Aula IV (Exercício A, comentário final omitido)
// e a contagem do foguetão (definida no contrato CONTRATO_ACADEMIA.md §4, exemplo 4).
import { EXAMPLES } from "./examples.js";
import { toPython, pythonText, allIds, allStmts, walk } from "./model.js";

const EXPECTED = {
  "media-3-notas": [
    'nota1 = float(input("Nota 1: "))',
    'nota2 = float(input("Nota 2: "))',
    'nota3 = float(input("Nota 3: "))',
    "media = (nota1 + nota2 + nota3) / 3",
    'print("Média =", media)',
  ],
  "segundos-minutos": [
    'total = int(input("Segundos: "))',
    "minutos = total // 60",
    "segundos = total % 60",
    'print(minutos, "min e", segundos, "s")',
  ],
  cafe: [
    "minutos_para_aula = 0",
    'minutos_para_aula = int(input("Quantos minutos faltam para a aula? "))',
    "if minutos_para_aula > 10:",
    '    print("Ainda dá para um café")',
    "elif minutos_para_aula >= 0:",
    '    print("Corre, corre, CORRE!")',
    "else:",
    '    print("Entra na boa e finge que estás atento desde o início")',
  ],
  foguetao: ["t = 5", "while t > 0:", "    print(t)", "    t = t - 1", 'print("Descolagem!")'],
  // Funções: deck "modularização" (PDF). slide 17 (soma_lista), 14 (dobro), 15 (media_segura), 19 (pedir_numero_positivo).
  // O comentário final do slide 19 ("# 17 linhas de validação...") não entra: é só nota do slide.
  "soma-lista-turmas": [
    "def soma_lista(numeros):", "    soma = 0", "    for numero in numeros:", "        soma = soma + numero", "    return soma", "",
    "notas_turma_a = [14, 9, 16, 12]", "notas_turma_b = [18, 7, 15, 20, 11]", "",
    'print("Soma da turma A:", soma_lista(notas_turma_a))', 'print("Soma da turma B:", soma_lista(notas_turma_b))',
  ],
  "dobro-return": ["def dobro(numero):", "    return numero * 2", "", "resultado = dobro(5)", "print(resultado)"],
  "media-segura": ["def media_segura(numeros):", "    if len(numeros) == 0:", '        return "não"', "    return soma_lista(numeros) / len(numeros)"],
  "pedir-numero-positivo": [
    "def pedir_numero_positivo(mensagem):", "    valor = -1", "    while valor <= 0:", "        valor = int(input(mensagem))", "        if valor <= 0:",
    '            print("Tem de ser um número positivo.")', "    return valor", "",
    'idade = pedir_numero_positivo("Idade: ")', 'peso = pedir_numero_positivo("Peso: ")', 'altura = pedir_numero_positivo("Altura: ")',
  ],
};

let bad = 0;
for (const ex of EXAMPLES) {
  const got = pythonText(ex);
  void allStmts;
  const want = EXPECTED[ex.id].join("\n");
  const ids = allIds(ex);
  const linesOk = toPython(ex).every((l) => l.stmtId == null || ids.includes(l.stmtId));
  const pathOk = ex.demoPath.every((id) => ids.includes(id));
  const uniq = new Set(ids).size === ids.length;
  // devolver só dentro de funções; nomes de função únicos
  const mainReturns = [...walk(ex.corpo || [])].some((x) => x.tipo === "devolver");
  const names = (ex.funcoes || []).map((f) => f.nome);
  const ok = got === want && linesOk && pathOk && uniq && !mainReturns && new Set(names).size === names.length;
  console.log(`${ok ? "OK  " : "FAIL"} ${ex.id}`);
  if (!ok) { bad++; console.log("--- obtido\n" + got + "\n--- esperado\n" + want); }
}
console.log(bad ? `${bad} exemplo(s) com diferenças` : "Todos os exemplos geram exatamente o Python dos slides.");
process.exit(bad ? 1 : 0);
