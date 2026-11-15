// Ranking com animação FLIP (as linhas deslizam para a nova posição), setas ▲▼, linha própria destacada
// e sempre visível, e cor de agência pelo color_idx (team-0..7). Só nós DOM, nunca HTML em bruto.
import { el } from "./dom.js";
import { t } from "../services/i18n.js";
import { fmtPoints } from "../pages/challenge/lib.js";
import { medalImg } from "./medal.js";

// Classes literais para o Tailwind as encontrar
const TEAM_BG = ["bg-team-0", "bg-team-1", "bg-team-2", "bg-team-3", "bg-team-4", "bg-team-5", "bg-team-6", "bg-team-7"];
const reduceMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

// mountLeaderboard(host, {meKey, limit, big}) -> {update(rows, teams), setMe(key)}
// rows: [{participant_key, name, points, rank, delta_rank}] · teams: [{id, color_idx}] (cor das agências "t:<id>")
export function mountLeaderboard(host, { meKey = null, limit = 0, big = false } = {}) {
  const list = el("ol", { class: "grid gap-1", "aria-live": "off" });
  host.replaceChildren(list);
  const nodes = new Map(); // participant_key -> <li>
  let me = meKey;
  let lastRows = [];
  let lastTeams = [];

  function colorOf(row, teams) {
    // O servidor envia color_idx em cada linha; se faltar, procura a agência pelo participant_key "t:<id>"
    if (Number.isInteger(row.color_idx)) return TEAM_BG[row.color_idx % 8];
    const team = teams.find((x) => `t:${x.id}` === row.participant_key);
    return team ? TEAM_BG[team.color_idx % 8] : null;
  }

  function build(row, teams) {
    const color = colorOf(row, teams);
    const size = big ? "text-[2.4vw] min-h-[4.4vw] px-[1.4vw]" : "text-sm min-h-[44px] px-2"; // 2.4vw ≈ 46 px em 1080p
    const li = el("li", { class: `flex items-center gap-2 bg-surface ${size}` });
    li._parts = {
      rank: el("span", { class: `${big ? "w-[3em]" : "w-[2.4em]"} shrink-0 font-pixel text-accent` }),
      medal: el("span", { class: `${big ? "w-[3vw]" : "w-6"} inline-flex shrink-0` }),
      dot: el("span", { class: `inline-block ${big ? "h-[2vw] w-[2vw]" : "h-3 w-3"} shrink-0 ${color || "bg-accent"}`, "aria-hidden": "true" }),
      name: el("span", { class: "min-w-0 flex-1 truncate" }),
      arrow: el("span", { class: "w-[1.5em] shrink-0 text-center", "aria-hidden": "true" }),
      pts: el("span", { class: `shrink-0 font-pixel ${big ? "text-[3vw]" : ""}` }),
    };
    li.append(...Object.values(li._parts));
    return li;
  }

  function fill(li, row, teams) {
    const p = li._parts;
    p.rank.textContent = `#${row.rank}`;
    p.medal.replaceChildren(...(row.rank >= 1 && row.rank <= 3 ? [medalImg(row.rank, { cls: big ? "medal h-[2.8vw] w-[2.8vw]" : "medal h-6 w-6" })] : []));
    p.name.textContent = row.name;
    p.pts.textContent = fmtPoints(row.points);
    const d = row.delta_rank || 0;
    p.arrow.textContent = d > 0 ? "▲" : d < 0 ? "▼" : "";
    p.arrow.className = `w-[1.5em] shrink-0 text-center ${d > 0 ? "text-success" : "text-danger"}`;
    const color = colorOf(row, teams);
    p.dot.className = `inline-block ${big ? "h-[2vw] w-[2vw]" : "h-3 w-3"} shrink-0 ${color || "bg-accent"}`;
    const mine = row.participant_key === me;
    li.classList.toggle("outline-2", mine);
    li.classList.toggle("outline", mine);
    li.classList.toggle("outline-accent", mine);
    li.classList.toggle("font-bold", mine);
    if (mine) li.setAttribute("aria-current", "true"); else li.removeAttribute("aria-current");
  }

  function update(rows, teams = lastTeams) {
    lastRows = rows || [];
    lastTeams = teams || [];
    // Lista visível: os primeiros `limit` + a linha própria (sempre visível, mesmo fora do top)
    let shown = lastRows;
    if (limit && lastRows.length > limit) {
      shown = lastRows.slice(0, limit);
      const mineRow = lastRows.find((r) => r.participant_key === me);
      if (mineRow && !shown.includes(mineRow)) shown = [...shown, mineRow];
    }
    // FLIP: First (posições antes) ...
    const before = new Map();
    for (const [k, li] of nodes) before.set(k, li.getBoundingClientRect().top);
    // ... Last (nova ordem no DOM)
    const keep = new Set();
    const ordered = shown.map((row) => {
      keep.add(row.participant_key);
      let li = nodes.get(row.participant_key);
      if (!li) { li = build(row, lastTeams); nodes.set(row.participant_key, li); }
      fill(li, row, lastTeams);
      return li;
    });
    for (const [k, li] of nodes) if (!keep.has(k)) { li.remove(); nodes.delete(k); }
    list.replaceChildren(...ordered);
    if (!lastRows.length) list.replaceChildren(el("li", { class: "text-sm text-muted" }, t("tournament.leaderboard_empty")));
    // ... Invert + Play
    if (reduceMotion()) return;
    for (const [k, li] of nodes) {
      if (!before.has(k)) continue;
      const dy = before.get(k) - li.getBoundingClientRect().top;
      if (!dy) continue;
      li.style.transition = "none";
      li.style.transform = `translateY(${dy}px)`;
      requestAnimationFrame(() => requestAnimationFrame(() => {
        li.style.transition = "transform 450ms steps(8)";
        li.style.transform = "";
      }));
    }
  }

  document.addEventListener("localechange", () => update(lastRows, lastTeams));
  return { update, setMe(key) { me = key; update(lastRows, lastTeams); } };
}
