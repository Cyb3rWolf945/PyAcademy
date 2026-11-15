// Modelo do programa da Academia: uma árvore de instruções (estruturada) de onde saem o fluxograma e o Python.
// Como as duas vistas nascem do mesmo modelo, nunca se contradizem. Sem execução em A0 (o modo trace vem na fase A2).
//
// Program = { id, titulo: {pt, en}, corpo: Stmt[], demoPath?: string[] }
// Stmt (todos têm `id`; `py` é o código Python, ou null quando só existe no fluxograma):
//   { tipo: "definir"|"ler"|"calcular"|"escrever", texto: {pt, en}, py }
//   { tipo: "se", cond: {pt, en}, py, sim: Stmt[], nao: Stmt[] }   // nao = um único "se" -> elif
//   { tipo: "enquanto", cond: {pt, en}, py, corpo: Stmt[] }
//   { tipo: "para", texto: {pt, en}, py: "for i in range(1, 6)", corpo: Stmt[] }

export const INDENT = "    ";

// Texto no idioma pedido (aceita string simples)
export function pickText(v, locale = "pt-PT") {
  if (v == null) return "";
  if (typeof v === "string") return v;
  return (locale === "en" ? v.en : v.pt) ?? v.pt ?? v.en ?? "";
}

// Família visual de cada tipo: "io" (ler/escrever), "proc" (definir/calcular), "dec" (decisões e ciclos)
export function familyOf(tipo) {
  if (tipo === "ler" || tipo === "escrever") return "io";
  if (tipo === "definir" || tipo === "calcular") return "proc";
  return "dec";
}

// Rótulo do bloco no fluxograma
export const labelOf = (s, locale) => pickText(s.tipo === "se" || s.tipo === "enquanto" ? s.cond : s.texto, locale);

// Percorre o programa por ordem de aparição (pré-ordem): útil para o "passo a passo" e para validar ids
export function* walk(stmts) {
  for (const s of stmts) {
    yield s;
    if (s.tipo === "se") { yield* walk(s.sim || []); yield* walk(s.nao || []); }
    else if (s.tipo === "enquanto" || s.tipo === "para") yield* walk(s.corpo || []);
  }
}

export const allIds = (program) => [...walk(program.corpo)].map((s) => s.id);

// Gera o Python: [{ line, indent, code, text, stmtId, tipo }] (line começa em 1; indent em níveis de 4 espaços).
// "else:" e "elif" ficam ligados ao `se` a que pertencem. Instruções com py === null não geram linha.
export function toPython(program) {
  const out = [];
  const push = (indent, code, s) => out.push({ line: out.length + 1, indent, code, text: INDENT.repeat(indent) + code, stmtId: s.id, tipo: s.tipo });
  const emit = (stmts, indent) => {
    for (const s of stmts) {
      if (s.tipo === "se") emitSe(s, indent, "if");
      else if (s.tipo === "enquanto") { push(indent, `while ${s.py}:`, s); emit(s.corpo || [], indent + 1); }
      else if (s.tipo === "para") { push(indent, `${s.py}:`, s); emit(s.corpo || [], indent + 1); }
      else if (s.py != null) push(indent, s.py, s);
    }
  };
  const emitSe = (s, indent, kw) => {
    push(indent, `${kw} ${s.py}:`, s);
    emit(s.sim || [], indent + 1);
    const nao = s.nao || [];
    if (nao.length === 1 && nao[0].tipo === "se") emitSe(nao[0], indent, "elif");
    else if (nao.length) { push(indent, "else:", s); emit(nao, indent + 1); }
  };
  emit(program.corpo, 0);
  return out;
}

// O mesmo Python como texto simples (linhas separadas por \n)
export const pythonText = (program) => toPython(program).map((l) => l.text).join("\n");
