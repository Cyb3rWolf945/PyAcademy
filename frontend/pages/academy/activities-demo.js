// Demo das atividades da Academia. Um "servidor" falso (só nesta página) corrige as respostas e devolve `detalhe` e
// `explicacao`, para testar os 6 tipos sem o backend. As respostas certas vivem AQUI (na demo), nunca nos componentes.
import { applyTheme } from "../../services/theme.js";
import { initialLocale, setLocale, getLocale } from "../../services/i18n.js";
import { mountLangSwitch } from "../../components/lang-switch.js";
import { el } from "../../components/dom.js";
import { EXAMPLES, exampleById } from "../../components/academy/examples.js";
import { renderActivity } from "../../components/academy/activities/index.js";

applyTheme();
await setLocale(initialLocale(), { save: false });
document.querySelectorAll("[data-lang-switch]").forEach(mountLangSwitch);

const media = exampleById("media-3-notas"), seg = exampleById("segundos-minutos");
const bi = (pt, en) => ({ pt, en });
const shuffle = (a, perm) => perm.map((i) => a[i]);

// ---- atividades "públicas" (o que o servidor mandaria: itens já baralhados, sem respostas) ----
const ACTS = [
  { tipo: "ligar", enunciado: bi("Liga cada bloco do fluxograma à linha de Python que o escreve.", "Link each flowchart block to the Python line that writes it."), exemplo: media, ids: ["l1", "l2", "l3", "c", "e"] },
  { tipo: "ordenar_fluxograma", enunciado: bi("Põe os blocos do fluxograma por ordem.", "Put the flowchart blocks in order."), exemplo: media, itens: shuffle(["d", "l1", "l2", "l3", "c", "e"], [4, 1, 5, 0, 3, 2]) },
  { tipo: "ordenar_python", enunciado: bi("Põe as linhas de Python por ordem.", "Put the Python lines in order."), exemplo: seg, itens: shuffle(["l", "c1", "c2", "e"], [2, 0, 3, 1]) },
  { tipo: "ordenar_lista", enunciado: bi("Ordena a escada das linguagens, da mais natural à mais próxima da máquina.", "Order the ladder of languages, from most natural to closest to the machine."),
    itens: [{ id: "py", texto: bi("Python", "Python") }, { id: "nat", texto: bi("Linguagem natural", "Natural language") }, { id: "bin", texto: bi("Código máquina (binário)", "Machine code (binary)") }, { id: "fluxo", texto: bi("Fluxograma", "Flowchart") }, { id: "ia", texto: bi("IA / prompts", "AI / prompts") }] },
  { tipo: "completar", enunciado: bi("Completa o Python e o fluxograma (// dá a parte inteira, % dá o resto).", "Complete the Python and the flowchart (// gives the whole part, % gives the remainder)."), exemplo: seg,
    lacunas: [{ stmt: "c1", lado: "py", modelo: bi("minutos = total ___ 60", "minutos = total ___ 60") }, { stmt: "c2", lado: "fluxo", modelo: bi("segundos = total ___ 60", "segundos = total ___ 60") }] },
  { tipo: "pergunta", enunciado: bi("Qual é o erro?", "What is the mistake?"), exemplo: media, mostrar_exemplo: false, pergunta: bi("O que está mal em nota1 + nota2 + nota3 / 3?", "What is wrong with nota1 + nota2 + nota3 / 3?"),
    opcoes: [bi("A divisão faz-se antes da soma, só divide a última nota.", "Division happens before the sum, so only the last mark is divided."), bi("Falta o print.", "The print is missing."), bi("Os nomes das variáveis estão trocados.", "The variable names are swapped.")] },
];

// ---- chaves e explicações: só no servidor falso ----
const KEYS = {
  0: { pares: { l1: "l1", l2: "l2", l3: "l3", c: "c", e: "e" } },
  1: { ordem: ["d", "l1", "l2", "l3", "c", "e"] },
  2: { ordem: ["l", "c1", "c2", "e"] },
  3: { ordem: ["nat", "ia", "fluxo", "py", "bin"] },
  4: { valores: ["//", "%"] },
  5: { escolha: [0] },
};
const EXPL = [
  bi("Cada bloco do fluxograma corresponde a uma linha de Python.", "Each flowchart block matches one Python line."),
  bi("Primeiro definimos, depois lemos, calculamos e escrevemos.", "First define, then read, calculate and write."),
  bi("Lê-se o total, calcula-se os minutos e os segundos e só depois se escreve.", "Read the total, compute minutes and seconds, then write."),
  bi("Cada degrau está mais perto da máquina do que o anterior.", "Each step is closer to the machine than the previous one."),
  bi("// dá o quociente inteiro e % dá o resto da divisão.", "// gives the whole quotient and % gives the remainder."),
  bi("A divisão tem prioridade sobre a soma: faltam parênteses.", "Division has priority over addition: parentheses are missing."),
];
const tries = {};
const norm = (s) => String(s).trim().toLowerCase().replace(",", ".");
const realFetch = globalThis.fetch.bind(globalThis);
globalThis.fetch = async (url, opts) => {
  const m = /\/api\/academy\/sections\/demo\/activities\/(\d+)\/answer$/.exec(String(url));
  if (!m) return realFetch(url, opts);
  const i = Number(m[1]), r = JSON.parse(opts.body).resposta, k = KEYS[i];
  let ok = true, detalhe = {};
  if (k.pares) { const bad = Object.keys(k.pares).filter((x) => r.pares?.[x] !== k.pares[x]); ok = !bad.length; detalhe = { erradas: bad }; }
  else if (k.ordem) { const bad = k.ordem.map((id, p) => (r.ordem?.[p] === id ? -1 : p)).filter((p) => p >= 0); ok = !bad.length; detalhe = { erradas: bad }; }
  else if (k.valores) { const bad = k.valores.map((v, p) => (norm(r.valores?.[p] ?? "") === norm(v) ? -1 : p)).filter((p) => p >= 0); ok = !bad.length; detalhe = { erradas: bad }; }
  else { ok = JSON.stringify(r.escolha) === JSON.stringify(k.escolha); }
  tries[i] = (tries[i] || 0) + (ok ? 0 : 1);
  const body = { correta: ok, detalhe: ok ? undefined : detalhe, explicacao: ok || tries[i] >= 2 ? EXPL[i] : undefined };
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
};

const list = document.getElementById("list");
function mountAll() {
  list.replaceChildren(...ACTS.map((a, i) => {
    const host = el("div");
    renderActivity(host, a, { sectionId: "demo", idx: i, exemplo: a.exemplo, locale: getLocale(), onSolved: () => { host.closest(".panel-pixel")?.classList.add("is-done"); } });
    return el("section", { class: "panel-pixel" }, el("p", { class: "mb-2 text-xs text-muted" }, `${i + 1} · ${a.tipo}`), host);
  }));
}
mountAll();
document.addEventListener("localechange", mountAll);
