// Ecrã final (aluno): pódio, a tua posição, ranking completo e o diploma em PNG.
import { el } from "../../components/dom.js";
import { icon } from "../../components/icon.js";
import { t } from "../../services/i18n.js";
import { currentUser } from "../../services/auth.js";
import { mountLeaderboard } from "../../components/leaderboard.js";
import { drawDiploma, downloadCanvas } from "./diploma.js";
import { fmtPoints } from "../challenge/lib.js";
import { mountBracket } from "../../components/bracket.js";
import { podium2d } from "./podium2d.js";
import { myRow, myTeam } from "./ui.js";

export function mountFinal(host, live) {
  const back = el("a", {
    href: "/",
    class: "btn-pixel btn-pixel--ghost min-h-[44px] min-w-[44px] w-fit px-3 text-xl",
    "aria-label": t("tournament.back_home"),
    title: t("tournament.back_home"),
  }, "←");
  const head = el("section", { class: "panel-pixel grid gap-3" });
  const podiumHost = el("div");
  const lbHost = el("div");
  const diplomaBox = el("section", { class: "panel-pixel grid gap-3" });
  const lbBox = el("section", { class: "panel-pixel grid gap-2" }, el("h3", { class: "text-base" }, t("tournament.final_ranking")), lbHost);
  const bracketHost = el("div");
  host.replaceChildren(back, head, el("section", { class: "panel-pixel grid gap-2" }, podiumHost), diplomaBox, lbBox, el("section", { class: "panel-pixel grid gap-2" }, bracketHost));
  const bracket = mountBracket(bracketHost, { meId: live.snap().me?.user_id });
  const lb = mountLeaderboard(lbHost, { meKey: live.snap().me?.participant_key });
  let preview = null;
  let busy = false;

  async function makeDiploma() {
    if (busy) return;
    busy = true;
    const snap = live.snap();
    const mine = myRow(snap);
    try {
      const elim = snap.format === "eliminatoria";
      const champion = snap.me?.status === "champion";
      const canvas = await drawDiploma({
        name: currentUser()?.display_name || "", tournament: snap.tournament.name,
        rank: mine?.rank ?? "-", points: fmtPoints(mine?.points ?? 0), config: snap.tournament.config,
        ...(elim ? { rankText: champion ? t("tournament.diploma_champion") : t("tournament.diploma_reached", { n: snap.me?.eliminated_in_round ?? "-" }), gold: champion } : {}),
      });
      canvas.className = "w-full max-w-xl border-2 border-surface-2";
      canvas.setAttribute("role", "img");
      canvas.setAttribute("aria-label", t("tournament.diploma"));
      preview = canvas;
      downloadCanvas(canvas, "pyarena-diploma.png");
      paint();
    } finally { busy = false; }
  }

  function paint() {
    const snap = live.snap();
    const mine = myRow(snap);
    const elim = snap.format === "eliminatoria";
    const top = (snap.podium && snap.podium.length ? snap.podium : (snap.leaderboard || []).slice(0, 3));
    const team = myTeam(snap);
    head.replaceChildren(...[
      el("h2", { class: "flex items-center gap-2 text-lg" }, icon("crown", "anim-bob"), t("tournament.final_title")),
      elim && snap.champion ? el("p", { class: "font-pixel text-xl text-gold" }, `🏆 ${t("tournament.champion_is", { name: snap.champion.display_name })}`) : null,
      elim ? el("p", { class: "text-sm" }, snap.me?.status === "champion" ? t("tournament.you_are_champion") : t("tournament.diploma_reached", { n: snap.me?.eliminated_in_round ?? "-" })) : null,
      elim ? el("p", { class: "text-sm text-accent" }, t("tournament.my_points_tournament", { points: fmtPoints(snap.my_points_this_tournament || 0) })) : null,
      !elim && mine ? el("p", { class: "font-pixel text-xl text-gold" }, t("tournament.final_rank", { rank: mine.rank, points: fmtPoints(mine.points) })) : null,
      team ? el("p", { class: "text-sm text-muted" }, t("tournament.your_agency", { name: team.name })) : null].filter(Boolean));
    const withColor = top.map((r) => {
      const tm = snap.teams?.find((x) => `t:${x.id}` === r.participant_key);
      return { name: r.name ?? r.display_name, points: r.points, color_idx: r.color_idx ?? tm?.color_idx ?? (r.user_id != null ? r.user_id % 8 : undefined) };
    });
    podiumHost.replaceChildren(podium2d(withColor));
    diplomaBox.replaceChildren(...[
      el("button", { type: "button", class: "btn-pixel btn-pixel--accent btn-pixel--lg", onclick: makeDiploma }, t("tournament.diploma_download")),
      preview].filter(Boolean));
    lb.setMe(snap.me?.participant_key);
    lb.update(snap.leaderboard || [], snap.teams); lbBox.hidden = elim; bracketHost.parentElement.hidden = !elim; if (elim) bracket.update(snap);
  }
  document.addEventListener("localechange", paint);
  return { update: paint, destroy() { document.removeEventListener("localechange", paint); host.replaceChildren(); } };
}
