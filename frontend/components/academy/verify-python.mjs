// Verificação A0: o Python gerado por toPython() tem de ser IGUAL ao código das soluções dos slides.
// Corre sem browser e sem dependências, num contentor descartável (a partir da raiz do projeto):
//   docker run --rm -v "$PWD/frontend:/f:ro" node:20-alpine node /f/components/academy/verify-python.mjs
// Origem do código esperado: slides de Aula II-III (Ex. 3.1 e 3.2), Aula IV (Exercício A, comentário final omitido)
// e a contagem do foguetão (definida no contrato CONTRATO_ACADEMIA.md §4, exemplo 4).
import { EXAMPLES } from "./examples.js";
import { toPython, pythonText, allIds, walk } from "./model.js";

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
};

let bad = 0;
for (const ex of EXAMPLES) {
  const got = pythonText(ex);
  const want = EXPECTED[ex.id].join("\n");
  const ids = allIds(ex);
  const linesOk = toPython(ex).every((l) => ids.includes(l.stmtId));
  const pathOk = ex.demoPath.every((id) => ids.includes(id));
  const uniq = new Set(ids).size === ids.length;
  const ok = got === want && linesOk && pathOk && uniq && [...walk(ex.corpo)].length === ids.length;
  console.log(`${ok ? "OK  " : "FAIL"} ${ex.id}`);
  if (!ok) { bad++; console.log("--- obtido\n" + got + "\n--- esperado\n" + want); }
}
console.log(bad ? `${bad} exemplo(s) com diferenças` : "Todos os exemplos geram exatamente o Python dos slides.");
process.exit(bad ? 1 : 0);
