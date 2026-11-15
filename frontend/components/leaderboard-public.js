// Painel "Leaderboard" (público e no hub): separadores Geral/Semana, pódio 2D dos 3 primeiros e top 10.
// Com sessão mostra ainda a linha fixa "Tu: #7 · 230 pts". Atualiza ao voltar ao separador e de 60 em 60 s (pausa se escondido).
// Todo o texto entra por textContent (nunca HTML em bruto). API: GET /api/leaderboard/public e /api/leaderboard/me.
import { el } from "./dom.js";
import { api } from "../services/api.js";
import { t, getLocale } from "../services/i18n.js";
import { currentUser } from "../services/auth.js";
import { medalImg } from "./medal.js";
import { countTo, flipReorder } from "../services/motion.js";

const REFRESH_MS = 60000;
const key = (e) => `${e.display_name}|${e.avatar_seed}`;
const fmt = (n) => new Intl.NumberFormat(getLocale()).format(n ?? 0);
// avatar determinístico: a semente escolhe a cor da equipa (0..7) do cartão do sprite
const tone = (seed) => { let h = 0; for (const c of String(seed ?? "")) h = (h * 31 + c.charCodeAt(0)) >>> 0; return h % 8; };
const avatar = (seed, cls = "") => el("span", { class: `lb-av lb-av--${tone(seed)} ${cls}` }, el("img", { class: "sprite", src: "/assets/sprites/icons/profile.png", width: 32, height: 32, alt: "" }));

export function mountLeaderboard(host, { nav = false } = {}) {
  let rendered = false, prevRank = new Map(), period = "all", data = null, me = null, failed = false, timer = 0, disposed = false, loadedAt = 0;
  host.classList.add("panel-pixel", "lb");
  if (nav) host.dataset.lbNav = "";

  const tabs = ["all", "week"].map((p) => el("button", { type: "button", role: "tab", "data-p": p, onclick: () => { period = p; data = null; me = null; render(); load(); } }, t(p === "all" ? "lb.all" : "lb.week")));
  const body = el("div", { class: "lb-body", "aria-live": "polite" });
  host.replaceChildren(
    el("h2", { class: "flex items-center gap-3 text-sm" }, el("img", { class: "sprite", src: "/assets/sprites/icons/trophy.png", width: 32, height: 32, alt: "" }), el("span", { id: "lb-title" }, t("lb.title"))),
    el("div", { class: "tabs-pixel my-3", role: "tablist" }, tabs), body);

  const moved = (e) => rendered && prevRank.has(key(e)) && prevRank.get(key(e)) > e.rank; // subiu desde a última leitura

  function podium(top) {
    const order = [1, 0, 2].filter((i) => top[i]);
    return el("ol", { class: "lb-podium" }, order.map((i, k) => {
      const e = top[i];
      const li = el("li", { class: `lb-step lb-step--${i + 1}`, "data-flip-id": key(e) },
        medalImg(e.rank >= 1 && e.rank <= 3 ? e.rank : i + 1, { size: i === 0 ? 64 : 32, cls: i === 0 ? "medal medal--lg" : "medal" }), avatar(e.avatar_seed), el("b", {}, `#${e.rank}`), el("span", { class: "lb-name" }, e.display_name), el("small", {}, el("span", { "data-count": e.points }, fmt(e.points)), ` ${t("lb.pts")}`), el("i", { class: "lb-block" }));
      li.style.animationDelay = `${k * 120}ms`;
      return li;
    }));
  }

  function render() {
    tabs.forEach((b) => { b.textContent = t(b.dataset.p === "all" ? "lb.all" : "lb.week"); b.setAttribute("aria-selected", String(b.dataset.p === period)); });
    host.querySelector("#lb-title").textContent = t("lb.title");
    const kids = [];
    if (failed && !data) kids.push(el("p", { class: "lb-empty" }, t("lb.error")));
    else if (!data) kids.push(el("p", { class: "lb-empty text-muted" }, "…"));
    else if (!data.entries.length) kids.push(el("p", { class: "lb-empty" }, el("img", { class: "sprite sprite--lg anim-bob", src: "/assets/sprites/icons/trophy.png", width: 64, height: 64, alt: "" }), el("span", {}, t("lb.empty"))));
    else {
      kids.push(podium(data.entries.slice(0, 3)));
      const rest = data.entries.slice(3, 10);
      if (rest.length) kids.push(el("ol", { class: "lb-list", start: 4 }, rest.map((e, k) => {
        const li = el("li", { class: `lb-row${moved(e) ? " is-up" : ""}`, "data-flip-id": key(e) }, el("b", {}, `#${e.rank}`), avatar(e.avatar_seed, "lb-av--sm"), el("span", { class: "lb-name" }, e.display_name), el("span", { class: "lb-pts", "data-count": e.points }, fmt(e.points)));
        li.style.animationDelay = `${(k + 3) * 80}ms`;
        return li;
      })));
    }
    if (currentUser() && currentUser().role !== "teacher" && me) {
      const row = el("div", { class: "lb-me" }, me.rank ? el("b", {}, t("lb.me", { rank: me.rank, points: fmt(me.points) })) : el("b", {}, t("lb.unranked")));
      if (me.visible === false) row.append(el("span", { class: "lb-hid" }, t("lb.hidden")), el("a", { href: "/pages/profile/profile.html", class: "lb-link" }, t("lb.enable")));
      kids.push(row);
    }
    const prev = [...body.querySelectorAll("[data-flip-id]")];
    const first = !rendered && data && data.entries.length > 0;
    if (rendered && prev.length && data) flipReorder(prev, () => body.replaceChildren(...kids)); // GSAP Flip: as linhas deslizam
    else body.replaceChildren(...kids);
    if (data) {
      prevRank = new Map(data.entries.map((e) => [key(e), e.rank]));
      if (first) { // contadores a subir só na primeira vez; depois as animações de entrada em CSS ficam paradas
        body.querySelectorAll("[data-count]").forEach((n) => countTo(n, Number(n.dataset.count), { duration: 0.9, format: fmt }));
        setTimeout(() => host.classList.add("is-static"), 1500);
      }
      rendered = rendered || data.entries.length > 0;
    }
  }

  async function load() {
    const p = period;
    try {
      const [pub, mine] = await Promise.all([
        api("GET", `/api/leaderboard/public?period=${p}&limit=10`),
        currentUser() && currentUser().role !== "teacher" ? api("GET", `/api/leaderboard/me?period=${p}`).catch(() => null) : null,
      ]);
      if (disposed || p !== period) return;
      data = { entries: Array.isArray(pub.entries) ? pub.entries : [] }; me = mine; failed = false; loadedAt = Date.now();
    } catch (_) { if (disposed || p !== period) return; failed = true; }
    render();
  }

  const tick = () => { clearTimeout(timer); if (!disposed && !document.hidden) { timer = setTimeout(async () => { await load(); tick(); }, REFRESH_MS); } };
  const onVis = () => { if (document.hidden) clearTimeout(timer); else { if (Date.now() - loadedAt > 15000) load(); tick(); } };
  document.addEventListener("visibilitychange", onVis);
  const onLocale = () => render();
  document.addEventListener("localechange", onLocale);
  render(); load().then(tick);
  return { dispose() { disposed = true; clearTimeout(timer); document.removeEventListener("visibilitychange", onVis); document.removeEventListener("localechange", onLocale); } };
}
