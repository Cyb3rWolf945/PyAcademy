// Bracket da eliminatória: colunas por ronda, grupos como caixas com avatares e barras de progresso (testes passados),
// vencedores destacados e linhas a ligar à ronda seguinte. Mostra nomes e progresso, nunca código.
import { el } from "./dom.js";
import { t } from "../services/i18n.js";
import { pick } from "../pages/challenge/lib.js";

const TEAM_BG = ["bg-team-0", "bg-team-1", "bg-team-2", "bg-team-3", "bg-team-4", "bg-team-5", "bg-team-6", "bg-team-7"];

export const roundLabel = (r) => (r.is_final ? t("tournament.final_round") : (pick(r.title) || t("tournament.round_n", { n: r.idx })));

// Avatar simples: inicial do nome sobre a cor do jogador
const tone = (seed) => { let h = 0; for (const c of String(seed ?? "")) h = (h * 31 + c.charCodeAt(0)) >>> 0; return h % 8; };
export function avatar(name, uid, big = false, seed = null) {
  return el("span", { class: `${TEAM_BG[tone(seed ?? uid)]} ${big ? "h-[2.6vw] w-[2.6vw] text-[1.6vw]" : "h-7 w-7 text-xs"} inline-flex shrink-0 items-center justify-center font-pixel text-accent-text`, "aria-hidden": "true" },
    (name || "?").trim().charAt(0).toUpperCase());
}

export function progressBar(passed, total, { big = false, winner = false } = {}) {
  const pct = total ? Math.min(100, Math.round((passed / total) * 100)) : 0;
  const fill = el("span", { class: `block h-full ${winner ? "bg-success" : "bg-accent"}` });
  fill.style.width = `${pct}%`;
  return el("span", { class: `block ${big ? "h-[0.8vw]" : "h-2"} w-full bg-surface-3`, role: "progressbar", "aria-valuenow": String(passed ?? 0), "aria-valuemax": String(total ?? 0) }, fill);
}

// Linha de um membro do grupo. opts: {big, meId, attempts}
export function memberRow(m, { big = false, meId = null, attempts = false } = {}) {
  const winner = m.status === "winner";
  const out = m.status === "out";
  const mine = m.user_id === meId;
  const txt = big ? "text-[1.8vw]" : "text-sm";
  return el("div", { class: `grid gap-1 p-1 ${winner ? "bg-success/25" : ""} ${mine ? "outline outline-2 outline-accent" : ""} ${out ? "opacity-60" : ""}` },
    el("div", { class: "flex items-center gap-2" },
      avatar(m.display_name, m.user_id, big, m.avatar_seed),
      el("span", { class: `min-w-0 flex-1 truncate ${txt} ${winner ? "font-bold" : ""}` }, m.display_name),
      winner ? el("span", { class: txt, "aria-label": t("tournament.group_winner") }, "🏆") : null,
      el("span", { class: `shrink-0 font-pixel ${txt}` }, `${m.passed ?? 0}/${m.total ?? "–"}`)),
    progressBar(m.passed ?? 0, m.total ?? 0, { big, winner }),
    attempts ? el("span", { class: "text-xs text-muted" }, t("tournament.attempts_n", { n: m.attempts ?? 0 })) : null);
}

// mountBracket(host, {big, focus, meId}) -> {update(snap), destroy()}
// focus (projetor): a ronda atual é a protagonista, numa grelha que cabe num ecrã 16:9 sem scroll; as anteriores
// ficam numa tira compacta. Sem focus (telemóvel): colunas com a ronda atual primeiro.
export function mountBracket(host, { big = false, focus = false, meId = null } = {}) {
  const wrap = el("div", { class: focus ? "flex h-full min-h-0 flex-col gap-[1vw]" : `flex max-w-full ${big ? "gap-[1vw]" : "gap-3"} overflow-x-auto` });
  host.classList.add("min-w-0", "max-w-full");
  host.replaceChildren(wrap);
  let last = null;

  function groupBox(g, hasNext, wide = false) {
    const decidedBy = g.decided_by ? t(`tournament.decided_${g.decided_by}`) : "";
    const box = el("div", { class: `${focus ? "w-full self-start" : big ? "w-[20vw]" : "w-56"} grid min-w-0 content-start shrink-0 gap-1 bg-surface ${big ? "p-[0.6vw]" : "p-2"} ${g.decided ? "border-l-4 border-success" : ""}` },
      ...(g.members || []).map((m) => memberRow(m, { big, meId })),
      g.decided && decidedBy ? el("span", { class: `${big ? "text-[1.1vw]" : "text-xs"} text-muted` }, decidedBy) : null);
    const stub = !focus && hasNext && g.decided ? el("span", { class: `block ${big ? "h-[0.3vw] w-[1.6vw]" : "h-1 w-4"} shrink-0 bg-success`, "aria-hidden": "true" }) : null;
    return focus ? box : el("div", { class: "flex items-center" }, box, stub);
  }

  function update(snap) {
    last = snap;
    const rounds = (snap.rounds || []).filter((r) => r.groups && r.groups.length);
    meId = snap.me?.user_id ?? meId;
    if (!rounds.length) { wrap.replaceChildren(el("p", { class: `${big ? "text-[2vw]" : "text-sm"} text-muted` }, t("tournament.bracket_empty"))); return; }
    const cur = rounds.find((r) => r.idx === snap.tournament.current_round) || rounds[rounds.length - 1];
    if (focus) {
      const prev = rounds.filter((r) => r !== cur && r.idx < cur.idx);
      const n = cur.groups.length;
      const cols = Math.min(n, n <= 5 ? n : Math.ceil(n / 2));
      const grid = el("div", { class: `grid min-h-0 flex-1 gap-[0.8vw] ${n === 1 ? "mx-auto w-[44%]" : ""}` }, cur.groups.map((g) => groupBox(g, false)));
      grid.style.gridTemplateColumns = `repeat(${cols}, minmax(0, 1fr))`;
      const strip = prev.length ? el("div", { class: "flex flex-wrap items-center gap-[1vw] text-[1.2vw] text-muted" },
        el("span", { class: "font-pixel" }, t("tournament.previous_rounds")),
        ...prev.map((r) => el("span", { class: "bg-surface px-[0.8vw] py-[0.3vw]" },
          `${roundLabel(r)}: ${r.groups.flatMap((g) => (g.members || []).filter((m) => m.status === "winner").map((m) => m.display_name)).join(", ") || "…"}`))) : null;
      wrap.replaceChildren(...[el("h3", { class: "font-pixel text-[1.8vw] text-accent" }, roundLabel(cur)), grid, strip].filter(Boolean));
      return;
    }
    // Telemóvel: a ronda atual primeiro, depois as outras por ordem
    const ordered = [cur, ...rounds.filter((r) => r !== cur)];
    wrap.replaceChildren(...ordered.map((r, i) => {
      const current = r === cur && snap.tournament.state !== "finished";
      return el("div", { class: "flex shrink-0 flex-col gap-2" },
        el("h3", { class: `font-pixel ${big ? "text-[1.8vw]" : "text-sm"} ${current ? "text-accent" : "text-muted"}` }, roundLabel(r)),
        el("div", { class: "flex flex-1 flex-col justify-around gap-2" }, ...r.groups.map((g) => groupBox(g, i < ordered.length - 1 || r.state === "closed"))));
    }));
  }
  const onLocale = () => last && update(last);
  document.addEventListener("localechange", onLocale);
  return { update, destroy() { document.removeEventListener("localechange", onLocale); host.replaceChildren(); } };
}
