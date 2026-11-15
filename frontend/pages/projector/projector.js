// Projetor (professor): ecrã grande legível ao fundo da sala. Mostra lobby com código gigante, ronda com
// temporizador e ranking animado, feed de missões resolvidas, celebração do boss e pódio final.
import { bootPage } from "../../services/page.js";
import { t } from "../../services/i18n.js";
import { el } from "../../components/dom.js";
import { mountTimer } from "../../components/timer.js";
import { mountLeaderboard } from "../../components/leaderboard.js";
import { mountConnectionStatus } from "../../components/connection-status.js";
import { createLive } from "../tournament/live.js";
import { fmtPoints } from "../challenge/lib.js";
import { celebrateSafe } from "../tournament/fx.js";
import { podium2d } from "../tournament/podium2d.js";
import { currentRound, nextRound, roundTitle, TEAM_BG } from "../tournament/ui.js";

const me = await bootPage({ access: "teacher" });
if (me) main();

function main() {
  const id = new URLSearchParams(location.search).get("id");
  const stage = document.getElementById("stage");
  const toasts = document.getElementById("toasts");
  const conn = mountConnectionStatus(document.getElementById("conn"), { showLabel: false });
  document.getElementById("fs").addEventListener("click", () => {
    if (document.fullscreenElement) document.exitFullscreen?.(); else document.documentElement.requestFullscreen?.();
  });
  if (!id) { stage.replaceChildren(el("p", { class: "text-[2.5vw] text-danger" }, t("projector.missing_id"))); return; }

  let view = null, kind = null;
  const live = createLive(id, { onChange: render, onStatus: (s) => conn.set(s), onEvent: onEvent });
  live.start().catch((err) => stage.replaceChildren(el("p", { class: "text-[2.5vw] text-danger" }, t(err.key || "common.error"))));

  // Ao trocar de idioma, refaz a vista atual (os textos estáticos são criados ao montar)
  document.addEventListener("localechange", () => { view?.destroy(); view = null; kind = null; render(); });

  const kindOf = (snap) => ({ lobby: "lobby", round_active: "round", round_paused: "round", between_rounds: "between" }[snap.tournament.state] || "final");

  function render() {
    const snap = live.snap();
    if (!snap) return;
    document.getElementById("title").textContent = snap.tournament.name;
    const next = kindOf(snap);
    if (next !== kind) {
      view?.destroy();
      kind = next;
      view = { lobby: lobbyView, round: roundView, between: betweenView, final: finalView }[next](live);
    }
    view.update();
  }

  // Toasts de eventos (mission_solved / first_bonus) + celebração do boss
  function pushToast(text, cls = "") {
    const node = el("div", { class: `toast-pixel anim-pop bg-surface p-[1vw] text-[1.8vw] ${cls}` }, text);
    toasts.append(node);
    while (toasts.children.length > 5) toasts.firstChild.remove();
    setTimeout(() => node.remove(), 12000);
  }
  function onEvent(ev) {
    const p = ev.payload || {};
    if (ev.type === "mission_solved") pushToast(`🎯 ${t("tournament.toast_solved", { name: p.name, points: fmtPoints(p.points) })}`);
    else if (ev.type === "first_bonus") pushToast(`⚡ ${t("tournament.toast_first_bonus", { name: p.name })}`, "text-gold");
    else if (ev.type === "boss_defeated") {
      pushToast(`👹 ${t("tournament.toast_boss", { name: p.name })}`, "text-gold");
      bossBanner();
      celebrateSafe("boss");
    }
  }
  function bossBanner() {
    const b = el("div", { class: "fixed inset-0 z-[55] grid place-items-center bg-bg/80 anim-pop" },
      el("p", { class: "font-pixel text-[7vw] text-gold" }, t("projector.boss_defeated")));
    document.body.append(b);
    setTimeout(() => b.remove(), 6000);
  }

  // ---------- Vistas ----------
  const playersCount = (snap) => snap.players_count ?? snap.tournament.players_count ?? 0;

  function lobbyView() {
    const code = el("p", { class: "font-pixel text-[15vw] leading-none tracking-widest text-accent" });
    const url = el("p", { class: "text-[2.6vw] text-muted" });
    const count = el("p", { class: "font-pixel text-[4vw]" });
    const teams = el("div", { class: "flex flex-wrap justify-center gap-[1vw]" });
    const box = el("div", { class: "grid h-full content-center justify-items-center gap-[2vh] text-center" },
      el("p", { class: "text-[2.4vw]" }, t("projector.join_at")), url, code, count, teams);
    stage.replaceChildren(box);
    return {
      update() {
        const snap = live.snap();
        const c = snap.tournament.join_code || "";
        code.textContent = c;
        url.textContent = `${location.host}/pages/tournament/tournament.html`;
        const n = playersCount(snap);
        count.textContent = n === 1 ? t("projector.joined_one") : t("projector.joined", { n });
        teams.replaceChildren(...(snap.teams || []).map((x) => el("span", { class: `${TEAM_BG[x.color_idx % 8]} px-[1.2vw] py-[0.6vw] text-[1.8vw] text-accent-text` }, `${x.name} · ${x.members.length}`)));
      },
      destroy() { stage.replaceChildren(); },
    };
  }

  function roundView() {
    const title = el("h2", { class: "min-w-0 flex-1 font-pixel text-[3.6vw]" });
    const boss = el("span", { class: "badge-pixel text-[2vw]", hidden: true }, t("tournament.boss"));
    const timerHost = el("div");
    const solved = el("p", { class: "text-[1.8vw] text-muted" });
    const lbHost = el("div");
    const top = el("div", { class: "flex items-center gap-[2vw]" }, el("div", { class: "min-w-0 flex-1" }, el("div", { class: "flex items-center gap-[1vw]" }, title, boss), solved), timerHost);
    stage.replaceChildren(el("div", { class: "grid h-full grid-rows-[auto_1fr] gap-[1.5vh]" }, top, el("div", { class: "min-h-0 w-[64vw] overflow-hidden" }, lbHost)));
    const timer = mountTimer(timerHost, { className: "text-[9vw] leading-none" });
    const lb = mountLeaderboard(lbHost, { big: true, limit: 8 });
    return {
      update() {
        const snap = live.snap();
        const r = currentRound(snap);
        if (!r) return;
        title.textContent = roundTitle(r);
        boss.hidden = !r.is_boss;
        const paused = snap.tournament.state === "round_paused" || r.state === "paused";
        timer.set({ ends_at: r.ends_at, remaining_s: r.remaining_s, paused });
        timer.setOffset(live.offset());
        solved.textContent = paused ? `⏸ ${t("tournament.paused_banner")}` : t("projector.missions_in_round", { n: r.mission_count });
        lb.update(snap.leaderboard, snap.teams);
      },
      destroy() { timer.destroy(); stage.replaceChildren(); },
    };
  }

  function betweenView() {
    const head = el("h2", { class: "font-pixel text-[3.4vw]" });
    const nextBox = el("p", { class: "text-[2.2vw] text-muted" });
    const lbHost = el("div");
    stage.replaceChildren(el("div", { class: "grid h-full grid-rows-[auto_auto_1fr] gap-[1.5vh]" }, head, nextBox, el("div", { class: "min-h-0 overflow-hidden" }, lbHost)));
    const lb = mountLeaderboard(lbHost, { big: true, limit: 8 });
    return {
      update() {
        const snap = live.snap();
        const done = currentRound(snap), next = nextRound(snap);
        head.textContent = done ? t("tournament.round_finished", { title: roundTitle(done) }) : t("tournament.between_title");
        nextBox.textContent = next ? `${t("tournament.next_round")}: ${roundTitle(next)}${next.is_boss ? ` · ${t("tournament.boss")}` : ""}` : t("tournament.no_more_rounds");
        lb.update(snap.leaderboard, snap.teams);
      },
      destroy() { stage.replaceChildren(); },
    };
  }

  function finalView() {
    const title = el("h2", { class: "text-center font-pixel text-[4vw] text-gold" }, t("tournament.final_title"));
    const podiumHost = el("div", { class: "min-h-0 flex-1" });
    stage.replaceChildren(el("div", { class: "grid h-full grid-rows-[auto_1fr] gap-[2vh]" }, title, podiumHost));
    let sig = "", disposer = null, celebrated = false;
    return {
      async update() {
        const snap = live.snap();
        const top = (snap.podium && snap.podium.length ? snap.podium : snap.leaderboard.slice(0, 3)).map((r) => {
          const tm = snap.teams?.find((x) => `t:${x.id}` === r.participant_key);
          return { name: r.name, points: r.points, color_idx: r.color_idx ?? tm?.color_idx ?? 0 };
        });
        const s = JSON.stringify(top);
        if (s === sig) return;
        sig = s;
        disposer?.dispose?.(); disposer = null;
        podiumHost.replaceChildren();
        const fallback = () => podiumHost.replaceChildren(el("div", { class: "mx-auto grid h-full max-w-[70vw] content-end" }, podium2d(top, { big: true })));
        try {
          // Cena 3D do design; se o módulo faltar ou der erro, pódio 2D
          disposer = await import("/scenes/podium.js").then((m) => m.mountPodium(podiumHost, top, { theme: document.documentElement.dataset.theme }));
          if (!podiumHost.firstChild) fallback();
        } catch (_) { fallback(); }
        if (!celebrated) { celebrated = true; celebrateSafe("podium"); }
      },
      destroy() { disposer?.dispose?.(); stage.replaceChildren(); },
    };
  }
}
