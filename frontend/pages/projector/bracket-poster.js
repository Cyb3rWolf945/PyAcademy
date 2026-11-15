// Bracket em "poster de campeonato" para o projetor: duas metades que convergem para o centro, colunas por ronda
// (espelhadas), caixas de grupo com avatar + progresso, linhas de ligação e a FINAL ao centro com o troféu e as medalhas.
// Tudo é desenhado num tamanho "natural" e depois escalado para caber num ecrã 16:9 sem scroll. Nada de HTML em bruto.
import { el } from "../../components/dom.js";
import { t } from "../../services/i18n.js";
import { medalImg } from "../../components/medal.js";
import { roundLabel } from "../../components/bracket.js";
import { fmtPoints } from "../challenge/lib.js";

const SVG_NS = "http://www.w3.org/2000/svg";
const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const tone = (seed) => { let h = 0; for (const c of String(seed ?? "")) h = (h * 31 + c.charCodeAt(0)) >>> 0; return h % 8; };

// Animação curta com passos (estilo pixel) através da Web Animations API; não faz nada com reduced-motion
function anim(node, frames, opts = {}) {
  if (!node || reduced() || !node.animate) return null;
  return node.animate(frames, { duration: 500, easing: "steps(5)", fill: "both", ...opts });
}

const TONES = ["bg-team-0", "bg-team-1", "bg-team-2", "bg-team-3", "bg-team-4", "bg-team-5", "bg-team-6", "bg-team-7"];
function avatar(seed) {
  return el("span", { class: `${TONES[tone(seed)]} inline-grid h-[26px] w-[26px] shrink-0 place-items-center` },
    el("img", { class: "sprite h-[20px] w-[20px]", src: "/assets/sprites/icons/profile.png", width: 20, height: 20, alt: "" }));
}

export function mountPoster(host) {
  host.classList.add("relative", "overflow-hidden");
  const fit = el("div", { class: "absolute left-0 top-0" });
  const inner = el("div", { class: "relative inline-flex items-stretch gap-[44px]" });
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "pointer-events-none absolute left-0 top-0");
  svg.setAttribute("aria-hidden", "true");
  fit.append(inner);
  host.replaceChildren(fit);
  inner.append(svg);

  let last = null, scale = 1, animating = false;
  const boxes = new Map();      // group.id -> {box, rows, tag}
  const seenBoxes = new Set();
  const seenMembers = new Set(); // "gid:uid" (para o "pop" do avatar na ronda seguinte)
  const decidedSeen = new Set();
  let championSeen = false;
  let trophy = null;

  // ----- caixa de um grupo (persistente: só as linhas são refeitas) -----
  function ensureBox(g) {
    let b = boxes.get(g.id);
    if (!b) {
      const tag = el("p", { class: "font-pixel text-[10px] text-muted" });
      const rows = el("div", { class: "grid grid-cols-2 gap-x-[6px] gap-y-[3px]" });
      const box = el("div", { class: "grid content-start gap-[3px] bg-surface p-[6px]", "data-group": String(g.id) }, tag, rows);
      b = { box, rows, tag };
      boxes.set(g.id, b);
    }
    return b;
  }

  function memberRow(m, g, boxId) {
    const winner = m.status === "winner" || g.winners?.includes(m.user_id);
    const dim = (g.decided && !winner) || m.status === "out";
    const pct = m.total ? Math.min(100, Math.round(((m.passed ?? 0) / m.total) * 100)) : 0;
    const fill = el("span", { class: `block h-full ${winner ? "bg-gold" : "bg-accent"}` });
    fill.style.width = `${pct}%`;
    const row = el("div", { class: `grid gap-[2px] p-[3px] ${winner ? "bg-gold/25 outline outline-[3px] outline-gold" : ""} ${dim ? "opacity-50" : ""}` },
      el("div", { class: "flex items-center gap-[8px]" },
        avatar(m.avatar_seed ?? m.user_id),
        el("span", { class: `min-w-0 flex-1 truncate text-[14px] ${winner ? "font-bold" : ""}` }, m.display_name),
        winner ? el("span", { class: "text-[16px]", "aria-label": t("tournament.group_winner") }, "🏆") : null,
        el("span", { class: "shrink-0 font-pixel text-[11px]" }, `${m.passed ?? 0}/${m.total ?? "–"}`)),
      el("span", { class: "block h-[4px] w-full bg-surface-3" }, fill));
    const key = `${boxId}:${m.user_id}`;
    if (!seenMembers.has(key)) {
      seenMembers.add(key);
      if (animating) anim(row.firstChild, [{ transform: "scale(1.8)", opacity: 0 }, { transform: "scale(1)", opacity: 1 }], { duration: 400, easing: "steps(4)" });
    }
    return row;
  }

  function paintBox(g, n, finalBox) {
    const b = ensureBox(g);
    b.tag.textContent = finalBox ? "" : t("tournament.group_n", { n });
    b.box.className = `grid content-start gap-[3px] bg-surface p-[6px] ${finalBox ? "w-[400px] outline outline-[4px] outline-gold" : "w-[340px]"} ${g.decided ? "border-l-[6px] border-success" : ""}`;
    b.rows.replaceChildren(...(g.members || []).map((m) => memberRow(m, g, g.id)));
    return b;
  }

  // ----- disposição: metades esquerda/direita + centro -----
  function layout(snap) {
    const rounds = (snap.rounds || []).filter((r) => r.groups && r.groups.length);
    if (!rounds.length) return null;
    const r1 = rounds[0];
    const leftN = Math.ceil(r1.groups.length / 2);
    const sideOfUser = new Map();
    r1.groups.forEach((g, i) => (g.members || []).forEach((m) => sideOfUser.set(m.user_id, i < leftN ? "L" : "R")));
    const cols = []; // {round, L:[g], R:[g], C:[g]}
    rounds.forEach((r, ri) => {
      const col = { round: r, L: [], R: [], C: [] };
      r.groups.forEach((g, gi) => {
        if (r.is_final) { col.C.push(g); return; }
        if (ri === 0) { (gi < leftN ? col.L : col.R).push(g); return; }
        const sides = new Set((g.members || []).map((m) => sideOfUser.get(m.user_id)).filter(Boolean));
        if (sides.size === 1) (sides.has("L") ? col.L : col.R).push(g); else col.C.push(g);
      });
      cols.push(col);
    });
    return { rounds, cols };
  }

  function update(snap) {
    animating = !!last; // a primeira pintura não anima (o ecrã abre já com o estado atual)
    last = snap;
    const lay = layout(snap);
    if (!lay) {
      inner.replaceChildren(el("p", { class: "p-6 text-[20px] text-muted" }, t("tournament.bracket_empty")));
      return;
    }
    const cur = snap.tournament.current_round;
    // numeração dos grupos dentro de cada ronda (1..n, da esquerda para a direita/cima para baixo)
    const num = new Map();
    lay.rounds.forEach((r) => r.groups.forEach((g, i) => num.set(g.id, i + 1)));
    const colEl = (c, side, finalBox = false) => {
      const gs = side === "L" ? c.L : side === "R" ? c.R : c.C;
      const current = c.round.idx === cur && snap.tournament.state !== "finished";
      const body = el("div", { class: "flex flex-1 flex-col justify-around gap-[10px]" }, ...gs.map((g) => paintBox(g, num.get(g.id), finalBox || !!c.round.is_final).box));
      return el("div", { class: "flex min-w-[340px] flex-col gap-[10px]" },
        el("h3", { class: `text-center font-pixel text-[15px] ${current ? "text-accent" : "text-muted"}` }, roundLabel(c.round)), body);
    };
    const nonFinal = lay.cols.filter((c) => !c.round.is_final);
    const finalCol = lay.cols.find((c) => c.round.is_final);
    const left = nonFinal.map((c) => colEl(c, "L"));
    const right = [...nonFinal].reverse().map((c) => colEl(c, "R"));

    // coluna central: troféu, grupos "mistos" e a final, medalhas por baixo
    const mixed = nonFinal.flatMap((c) => c.C);
    const centerBoxes = [...mixed.map((g) => paintBox(g, num.get(g.id), false).box), ...(finalCol ? finalCol.C.map((g) => paintBox(g, num.get(g.id), true).box) : [])];
    trophy = trophy || el("div", { class: "text-center text-[56px] leading-none", "aria-hidden": "true" }, "🏆");
    trophy.classList.toggle("opacity-40", !snap.champion);
    const podium = snap.podium?.length ? el("div", { class: "flex justify-center gap-[16px]" }, snap.podium.slice(0, 3).map((p, i) =>
      el("div", { class: "grid justify-items-center gap-[2px]" }, medalImg(i + 1, { size: 64, cls: "medal" }),
        el("span", { class: "max-w-[140px] truncate font-pixel text-[12px]" }, p.name ?? p.display_name), el("span", { class: "text-[14px] text-accent" }, fmtPoints(p.points ?? 0))))) : null;
    const center = el("div", { class: `flex ${finalCol || mixed.length ? "min-w-[400px]" : "min-w-[120px]"} flex-col items-center justify-center gap-[10px]` },
      el("h3", { class: `font-pixel text-[18px] ${finalCol && finalCol.round.idx === cur ? "text-accent" : "text-gold"}` }, finalCol ? roundLabel(finalCol.round) : t("tournament.final_round")),
      trophy, ...centerBoxes, podium);

    inner.replaceChildren(svg, ...left, center, ...right);

    // animações de entrada / decisão / campeão (só depois da primeira pintura)
    const newBoxes = [];
    for (const g of lay.rounds.flatMap((r) => r.groups)) {
      const b = boxes.get(g.id);
      if (!seenBoxes.has(g.id)) { seenBoxes.add(g.id); newBoxes.push(b.box); }
    }
    if (animating || newBoxes.length) newBoxes.forEach((bx, i) => anim(bx, [{ opacity: 0, transform: "translateY(14px)" }, { opacity: 1, transform: "none" }], { delay: i * 60, duration: 400 }));
    const newlyDecided = [];
    for (const g of lay.rounds.flatMap((r) => r.groups)) if (g.decided && !decidedSeen.has(g.id)) { decidedSeen.add(g.id); if (animating) newlyDecided.push(g.id); }
    for (const id of newlyDecided) {
      const rows = boxes.get(id)?.rows.children || [];
      for (const r of rows) if (r.className.includes("outline-gold")) anim(r, [{ opacity: 1 }, { opacity: 0.2 }, { opacity: 1 }, { opacity: 0.2 }, { opacity: 1 }], { duration: 700, easing: "steps(2)" });
    }
    if (snap.champion && !championSeen) {
      championSeen = true;
      if (animating) anim(trophy, [{ transform: "translateY(0)" }, { transform: "translateY(-28px)" }, { transform: "translateY(0)" }, { transform: "translateY(-12px)" }, { transform: "translateY(0)" }], { duration: 900, easing: "steps(8)" });
    }
    requestAnimationFrame(() => { fitToHost(); drawLinks(lay, snap, newlyDecided); });
  }

  // ----- escala para caber no ecrã -----
  function fitToHost() {
    const w = inner.offsetWidth, h = inner.offsetHeight;
    const aw = host.clientWidth, ah = host.clientHeight;
    if (!w || !h || !aw || !ah) return;
    scale = Math.min(aw / w, ah / h, 2.4);
    fit.style.transformOrigin = "top left";
    fit.style.transform = `scale(${scale})`;
    fit.style.left = `${Math.max(0, (aw - w * scale) / 2)}px`;
    fit.style.top = `${Math.max(0, (ah - h * scale) / 2)}px`;
    svg.setAttribute("width", String(w));
    svg.setAttribute("height", String(h));
  }

  // posição de um elemento relativa a `inner` (em px "naturais", sem escala)
  function pos(node) {
    let x = 0, y = 0, e = node;
    while (e && e !== inner) { x += e.offsetLeft; y += e.offsetTop; e = e.offsetParent; }
    return { x, y, w: node.offsetWidth, h: node.offsetHeight };
  }

  function path(d, stroke, win) {
    const p = document.createElementNS(SVG_NS, "path");
    p.setAttribute("d", d);
    p.setAttribute("fill", "none");
    p.setAttribute("stroke-width", win ? "4" : "3");
    p.setAttribute("shape-rendering", "crispEdges");
    p.style.stroke = stroke;
    return p;
  }

  // Ligações: de cada vencedor (grupo decidido) para a caixa da ronda seguinte que o contém
  function drawLinks(lay, snap, newlyDecided) {
    svg.replaceChildren();
    const rounds = lay.rounds;
    for (let i = 0; i < rounds.length - 1; i++) {
      for (const g of rounds[i].groups) {
        if (!g.decided) continue;
        const A = boxes.get(g.id)?.box;
        if (!A || !A.isConnected) continue;
        const targets = new Set();
        for (const w of g.winners || []) {
          const nb = rounds[i + 1].groups.find((x) => (x.members || []).some((m) => m.user_id === w));
          if (nb) targets.add(nb.id);
        }
        for (const id of targets) {
          const B = boxes.get(id)?.box;
          if (!B || !B.isConnected) continue;
          const a = pos(A), b = pos(B);
          const toRight = b.x > a.x;
          const x1 = toRight ? a.x + a.w : a.x, x2 = toRight ? b.x : b.x + b.w;
          const y1 = a.y + a.h / 2, y2 = b.y + b.h / 2, xm = (x1 + x2) / 2;
          const p = path(`M${x1} ${y1} H${xm} V${y2} H${x2}`, "var(--c-gold, var(--c-accent))", true);
          svg.append(p);
          if (newlyDecided.includes(g.id) && !reduced() && p.getTotalLength) {
            const len = p.getTotalLength();
            p.style.strokeDasharray = String(len);
            anim(p, [{ strokeDashoffset: len }, { strokeDashoffset: 0 }], { duration: 700, easing: "steps(10)" });
          }
        }
      }
    }
  }

  const ro = new ResizeObserver(() => { if (last) { fitToHost(); } });
  ro.observe(host);
  const onLocale = () => last && update(last);
  document.addEventListener("localechange", onLocale);
  return {
    update,
    destroy() { ro.disconnect(); document.removeEventListener("localechange", onLocale); host.replaceChildren(); },
  };
}
