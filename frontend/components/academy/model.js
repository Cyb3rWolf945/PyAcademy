// Modelo do programa da Academia: uma árvore de instruções (estruturada) de onde saem o fluxograma e o Python.
// Como as duas vistas nascem do mesmo modelo, nunca se contradizem. Sem execução em A0 (o modo trace vem na fase A2).
//
// Program = { id, titulo: {pt, en}, corpo: Stmt[], demoPath?: string[] }
// Stmt (todos têm `id`; `py` é o código Python, ou null quando só existe no fluxograma):
//   { tipo: "definir"|"ler"|"calcular"|"escrever", texto: {pt, en}, py }
//   { tipo: "se", cond: {pt, en}, py, sim: Stmt[], nao: Stmt[] }   // nao = um único "se" -> elif
//   { tipo: "enquanto", cond: {pt, en}, py, corpo: Stmt[] }
//   { tipo: "para", texto: {pt, en}, py: "for i in range(1, 6)", corpo: Stmt[] }
//   { tipo: "chamar", texto: {pt, en}, py }   // chamada de função como instrução (processo pré-definido)
//   { tipo: "devolver", texto: {pt, en}, py: "return x" }   // só dentro de funções (terminal)
// Qualquer Stmt pode ter `branco_antes: true` (uma linha em branco no Python antes dela, como nos slides).
// Program.funcoes?: [{ id, nome, params, devolve_tipo?, texto?, corpo: Stmt[] }]  (o `def` fica ligado ao início da função)

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
  if (tipo === "definir" || tipo === "calcular" || tipo === "chamar") return "proc";
  if (tipo === "funcao") return "fn";   // pílula verde de início de função (linha def)
  if (tipo === "devolver") return "term"; // terminal "Devolver ..."
  return "dec";
}

// Assinatura "nome(params)" e cabeçalho Python da função
export const fnSignature = (f) => `${f.nome}(${f.params ?? ""})`;
export const fnHeader = (f) => `def ${f.nome}(${f.params ?? ""})${f.devolve_tipo ? ` -> ${f.devolve_tipo}` : ""}:`;
// A função vista como uma pseudo-instrução (para ligar/ordenar: a pílula de início ↔ linha def)
export const funcaoStmt = (f) => ({ id: f.id, tipo: "funcao", texto: fnSignature(f), py: fnHeader(f) });

// Programa reduzido ao corpo de uma função (atividades com `alvo`)
export function scopeProgram(program, alvo) {
  const f = (program.funcoes || []).find((x) => x.id === alvo);
  return f ? { ...program, funcoes: [f], corpo: [], alvo: f.id } : program;
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

// Todas as instruções do programa: principal e corpos das funções
export function* allStmts(program) {
  yield* walk(program.corpo || []);
  for (const f of program.funcoes || []) yield* walk(f.corpo || []);
}

// Ids únicos de tudo o que é ligável: funções (pílula de início / def) e instruções
export const allIds = (program) => [...(program.funcoes || []).map((f) => f.id), ...[...allStmts(program)].map((s) => s.id)];

// Gera o Python: [{ line, indent, code, text, stmtId, tipo }] (line começa em 1; indent em níveis de 4 espaços).
// As funções vêm primeiro (`def` com stmtId = funcao.id), com uma linha em branco entre funções e antes do principal;
// as linhas em branco têm stmtId null e tipo "blank". "else:" e "elif" ficam ligados ao `se` a que pertencem.
// Instruções com py === null não geram linha.
export function toPython(program) {
  const out = [];
  const push = (indent, code, s) => out.push({ line: out.length + 1, indent, code, text: code ? INDENT.repeat(indent) + code : "", stmtId: s ? s.id : null, tipo: s ? s.tipo : "blank" });
  const blank = () => push(0, "", null);
  const emit = (stmts, indent) => {
    for (const s of stmts) {
      if (s.branco_antes) blank();
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
  const funcs = program.funcoes || [];
  funcs.forEach((f, i) => {
    if (i) blank();
    push(0, fnHeader(f), funcaoStmt(f));
    emit(f.corpo || [], 1);
  });
  if (funcs.length && (program.corpo || []).length) blank();
  emit(program.corpo || [], 0);
  return out;
}

// O mesmo Python como texto simples (linhas separadas por \n)
export const pythonText = (program) => toPython(program).map((l) => l.text).join("\n");
