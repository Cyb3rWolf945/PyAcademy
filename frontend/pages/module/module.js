// Página de módulo (?id=m1): secções numeradas vindas de GET /api/academy/modules/{id}; a atual abre sozinha, as concluídas
// podem ser revistas e as bloqueadas mostram 🔒. Cada secção: Aprender (Markdown + vista ligada + slides), Praticar
// (atividades do FX) e "Responde para concluir" (verificação no servidor, pistas, pontos, celebração, selo do módulo).
// Moldura pixel art; o conteúdo didático usa tipografia limpa (.clean). Só nós DOM, nunca HTML em bruto.
import { bootPage } from "../../services/page.js";
import { t, getLocale } from "../../services/i18n.js";
import { api, errorText, ApiError } from "../../services/api.js";
import { el } from "../../components/dom.js";
import { toast } from "../../components/toast.js";
import { mountThemeSwitcher } from "../../components/theme-switcher.js";
import { mountSlides } from "../../components/academy/slides-viewer.js";
import { enter, countTo, pulse, motion } from "../../services/motion.js";
import { pick, renderMarkdown, fmtPoints } from "../challenge/lib.js";
import { playVictory } from "../../services/sound.js";

const ICON = { done: "✅", current: "▶", locked: "🔒" };
const modId = new URLSearchParams(location.search).get("id") || "m1";
const celebrateSafe = (kind) => import("../../scenes/celebrate.js").then((m) => m.celebrate(document.body, { kind })).catch(() => {});

// ---------- blocos de uma secção ----------
function learnBlock(sec) {
  const kids = [el("h4", { class: "acad-block__h" }, el("span", { "aria-hidden": "true" }, "📘 "), t("ui.mod.learn")),
    el("div", { class: "clean" }, renderMarkdown(pick(sec.aprender)))];
  if (sec.exemplo) {
    const status = el("p", { class: "acad-linked-status" }, t("ui.mod.linked_wait"));
    const host = el("div", { class: "acad-linked acad-skeleton" }, status);
    import("../../components/academy/linked-view.js").then((lv) => { host.replaceChildren(); host.classList.remove("acad-skeleton"); lv.renderLinked(host, sec.exemplo, { locale: getLocale() }); })
      .catch(() => { status.textContent = t("ui.mod.linked_missing"); });
    kids.push(host);
  }
  const slidesHost = el("div", { class: "slides" });
  if (sec.slides?.length) { mountSlides(slidesHost, sec.slides); kids.push(slidesHost); }
  if (sec.leitura) kids.push(el("p", { class: "clean acad-reading" }, el("span", { "aria-hidden": "true" }, "📖 "), pick(sec.leitura)));
  return el("section", { class: "acad-block" }, kids);
}

function practiceBlock(sec) {
  const acts = sec.atividades || [];
  if (!acts.length) return null;
  const solved = new Set();
  const badge = el("span", { class: "badge-pixel" }, `0/${acts.length}`);
  const list = el("div", { class: "acad-acts" });
  acts.forEach((act, idx) => {
    const host = el("div", { class: "acad-act" });
    list.append(el("div", { class: "acad-act__wrap" }, el("h5", { class: "acad-act__h" }, `${idx + 1}.`), host));
    import("../../components/academy/activities/index.js").then((m) => {
      m.renderActivity(host, act, { sectionId: sec.id, idx, exemplo: sec.exemplo, locale: getLocale(), onSolved: () => { solved.add(idx); badge.textContent = `${solved.size}/${acts.length}`; } });
    }).catch(() => host.append(el("p", { class: "acad-linked-status" }, t("ui.mod.activity_missing"))));
  });
  return el("section", { class: "acad-block" }, el("h4", { class: "acad-block__h" }, el("span", { "aria-hidden": "true" }, "🧩 "), t("ui.mod.practice"), badge), list);
}

function checkBlock(sec, state, onResult) {
  const v = sec.verificacao || {};
  const multi = !!(v.multipla || v.multi || v.varias);
  const opts = v.opcoes || [];
  const msg = el("p", { class: "acad-msg", role: "status" });
  const btn = el("button", { type: "button", class: "btn-pixel btn-pixel--accent", disabled: true }, t("ui.mod.finish"));
  const inputs = [];
  const labels = opts.map((o, i) => {
    const input = el("input", { type: multi ? "checkbox" : "radio", name: `q-${sec.id}`, value: String(i), onchange: () => { btn.disabled = !inputs.some((x) => x.checked); msg.textContent = ""; } });
    inputs.push(input);
    return el("label", { class: "acad-opt" }, input, el("span", {}, pick(o)));
  });
  // pistas: cada pista aberta faz a secção valer metade dos pontos
  const nHints = sec.n_pistas ?? sec.pistas?.length ?? 0;
  let hintsOpen = 0;
  const hintList = el("ul", { class: "acad-hints clean" });
  const hintBtn = nHints ? el("button", { type: "button", class: "btn-pixel btn-pixel--ghost", onclick: async () => {
    hintBtn.disabled = true;
    try { const r = await api("GET", `/api/academy/sections/${encodeURIComponent(sec.id)}/hints/${hintsOpen + 1}`); hintsOpen++; hintList.append(el("li", {}, pick(r.texto))); }
    catch (err) { toast(errorText(err), "error"); }
    hintBtn.disabled = hintsOpen >= nHints;
    hintBtn.textContent = t("ui.mod.hint_btn");
  } }, t("ui.mod.hint_btn")) : null;
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    try {
      const r = await api("POST", `/api/academy/sections/${encodeURIComponent(sec.id)}/verify`, { resposta: { escolha: inputs.filter((x) => x.checked).map((x) => Number(x.value)) } });
      if (!r.correta) {
        msg.textContent = t("ui.mod.wrong"); msg.classList.remove("anim-shake"); void msg.offsetWidth; msg.classList.add("anim-shake"); btn.disabled = false; return;
      }
      inputs.forEach((x) => { x.disabled = true; });
      msg.textContent = t("ui.mod.done_msg");
      onResult(r, btn);
    } catch (err) { msg.textContent = errorText(err); btn.disabled = false; }
  });
  return el("section", { class: "acad-block" },
    el("h4", { class: "acad-block__h" }, el("span", { "aria-hidden": "true" }, "✍️ "), t("ui.mod.check")),
    state === "done" ? el("p", { class: "clean acad-revisit" }, t("ui.mod.revisit")) : null,
    el("div", { class: "clean" }, el("p", {}, el("b", {}, pick(v.pergunta)))),
    el("fieldset", { class: "acad-opts" }, el("legend", { class: "sr-only" }, pick(v.pergunta)), labels),
    nHints ? el("div", { class: "acad-hintbox" }, el("p", { class: "acad-warn" }, el("span", { "aria-hidden": "true" }, "💡 "), t("ui.mod.hint_warn")), hintBtn, hintList) : null,
    el("div", { class: "acad-actions" }, btn, msg));
}

// ---------- página ----------
const me = await bootPage({ access: "user", nav: true });
const IS_TEACHER = me?.role === "teacher";
if (me) init();

async function init() {
  mountThemeSwitcher(document.querySelector("[data-theme-switch]"));
  const title = document.getElementById("mod-title");
  const root = document.getElementById("module");
  let mod = null;
  let openId = "";
  const loaded = new Map(); // id -> corpo montado (não se refaz ao reabrir)

  const bar = el("div", { class: "xp-bar", role: "progressbar", "aria-valuemin": "0", "aria-valuemax": "100" });
  const pctText = el("b", { class: "acad-pct" });
  const ptsText = el("b", {});
  const secText = el("span", {});
  const list = el("ol", { class: "acad-secs" });
  const h2 = el("h2", { class: "acad-h2" }, t("ui.mod.sections"));
  const crumb = el("a", { class: "btn-pixel btn-pixel--ghost acad-back", href: "/pages/academy/academy.html" }, t("ui.back"));
  const buildSide = () => el("aside", { class: "acad-side" },
    el("section", { class: "panel-pixel" }, el("h2", {}, t("ui.side.progress")), el("div", { class: "acad-progress" }, bar, pctText), el("p", { class: "acad-side__line" }, secText), el("p", { class: "acad-side__line" }, ptsText)),
    el("section", { class: "panel-pixel" }, el("h2", {}, t("ui.side.slides")), el("p", { class: "acad-side__line" }, t("ui.side.slides_hint"))),
    el("section", { class: "panel-pixel" }, el("h2", {}, t("ui.side.reading")), el("p", { class: "clean", id: "side-reading" }, t("ui.side.reading_none"))));
  let side = buildSide();
  const badgeBox = el("div", { class: "acad-badge-box" });
  root.replaceChildren(el("div", { class: "acad-layout" }, el("div", { class: "acad-col" }, crumb, h2, badgeBox, list), side));

  function paintProgress(prevPts) {
    const pct = Math.round(mod.pct ?? 0);
    bar.style.setProperty("--v", String(pct)); bar.setAttribute("aria-valuenow", String(pct)); bar.setAttribute("aria-label", `${pct}%`);
    pctText.textContent = `${pct}%`;
    secText.textContent = t("ui.side.sections", { done: mod.concluidas ?? 0, total: mod.n_secoes ?? mod.secoes.length });
    const fmt = (n) => t("ui.card.points", { got: fmtPoints(n), max: fmtPoints(mod.pontos_possiveis ?? 0) });
    if (prevPts != null && prevPts !== mod.pontos_ganhos) countTo(ptsText, mod.pontos_ganhos ?? 0, { from: prevPts, duration: 0.6, format: fmt }); else ptsText.textContent = fmt(mod.pontos_ganhos ?? 0);
    title.textContent = pick(mod.titulo);
  }

  async function ensureBody(sec, body) {
    if (loaded.has(sec.id)) { body.replaceChildren(...loaded.get(sec.id)); return; }
    body.replaceChildren(el("p", { class: "text-muted", role: "status" }, t("ui.loading")));
    try {
      const full = await api("GET", `/api/academy/sections/${encodeURIComponent(sec.id)}`);
      const kids = [learnBlock(full), practiceBlock(full), checkBlock(full, sec.estado, (r, btn) => onVerified(sec, r, btn))].filter(Boolean);
      loaded.set(sec.id, kids);
      body.replaceChildren(...kids);
      if (full.leitura) { const r = document.getElementById("side-reading"); if (r) r.textContent = pick(full.leitura); }
    } catch (err) {
      if (err instanceof ApiError && err.key === "academy.locked") { toast(errorText(err), "error"); await refresh(); return; }
      body.replaceChildren(el("p", { role: "alert" }, errorText(err)), el("button", { type: "button", class: "btn-pixel", onclick: () => ensureBody(sec, body) }, t("ui.err.retry")));
    }
  }

  // Abre uma secção e leva o aluno ao início dela, já com o conteúdo carregado (antes disso a página ainda não tem a altura final)
  async function goToSection(id) {
    openId = id;
    await renderList();
    const li = document.getElementById(`sec-${id}`);
    if (!li) return;
    // Salto direto: um deslize suave seria interrompido pelo conteúdo que ainda está a chegar (fluxogramas, slides)
    li.scrollIntoView({ block: "start", behavior: "instant" });
    li.querySelector(".acad-sec__head")?.focus({ preventScroll: true });
    setTimeout(() => { if (openId === id && Math.abs(li.getBoundingClientRect().top) > 40) li.scrollIntoView({ block: "start", behavior: "instant" }); }, 350);
  }

  function renderList() {
    const opening = [];
    list.replaceChildren(...mod.secoes.map((s, i) => {
      // O professor pode pré-visualizar secções bloqueadas (a API já o permite); para os alunos continuam fechadas.
      const locked = s.estado === "locked" && !IS_TEACHER;
      const preview = s.estado === "locked" && IS_TEACHER;
      const head = el("button", { type: "button", class: "acad-sec__head", disabled: locked, title: preview ? t("ui.mod.preview") : null, "aria-expanded": String(openId === s.id), onclick: () => { if (openId === s.id) { openId = ""; renderList(); } else goToSection(s.id); } },
        el("span", { class: "acad-sec__n" }, String(i + 1)), el("span", { class: "acad-sec__t" }, pick(s.titulo)), el("span", { class: "chip" }, `+${s.pontos ?? 0}`), el("span", { class: "acad-sec__i", "aria-hidden": "true" }, preview ? "👁" : (ICON[s.estado] || "🔒")));
      const body = el("div", { class: "acad-sec__body", hidden: openId !== s.id || locked });
      const li = el("li", { class: "acad-sec", "data-state": s.estado, id: `sec-${s.id}` }, head, body);
      if (!body.hidden) opening.push(ensureBody(s, body));
      return li;
    }));
    return Promise.all(opening);
  }

  async function refresh() {
    const prev = mod?.pontos_ganhos;
    mod = await api("GET", `/api/academy/modules/${encodeURIComponent(modId)}`);
    paintProgress(prev);
    renderList();
  }

  async function onVerified(sec, r, btn) {
    if ((r.pontos ?? 0) > 0) {
      toast(t("ui.mod.pts", { n: fmtPoints(r.pontos) }), "success");
      const gain = el("span", { class: "acad-gain anim-float-up", role: "status" }, t("ui.mod.pts", { n: fmtPoints(r.pontos) }));
      btn.after(gain); setTimeout(() => gain.remove(), 1600);
      playVictory();
      celebrateSafe(r.badge ? "boss" : "solve");
    } else toast(t("ui.mod.no_points"), "info");
    if (r.badge) {
      document.dispatchEvent(new CustomEvent("scorechange"));
      badgeBox.replaceChildren(el("section", { class: "panel-pixel acad-badge anim-pop", role: "status" },
        el("img", { class: "sprite sprite--lg anim-bob", src: `/assets/sprites/academy/peca-${mod.peca || "inicio-fim"}.png`, width: 64, height: 64, alt: "" }),
        el("div", {}, el("b", {}, t("ui.mod.badge_title")), el("p", {}, t("ui.mod.badge_text", { pts: fmtPoints(r.badge.pontos ?? 25) })))));
      badgeBox.scrollIntoView({ block: "nearest" });
    }
    loaded.delete(sec.id); // o corpo é refeito em modo "revisão" quando se reabrir
    if (r.proxima) openId = r.proxima; // evita reabrir por instantes a secção que acabou de ser concluída
    await refresh().catch(() => {});
    if (r.proxima) await goToSection(r.proxima);
    else if (r.badge) badgeBox.scrollIntoView({ block: "start", behavior: "instant" }); // última secção: mostra o selo ganho
    pulse(bar);
  }

  async function start() {
    list.replaceChildren(el("p", { class: "text-muted", role: "status" }, t("ui.loading")));
    try {
      await refresh();
      const cur = mod.secoes.find((s) => s.estado === "current") || [...mod.secoes].reverse().find((s) => s.estado === "done") || mod.secoes[0];
      openId = cur?.id || "";
      renderList();
      const m = await motion(); if (m) enter([...list.children], { y: 16, stagger: 0.06 });
    } catch (err) {
      list.replaceChildren(el("div", { class: "panel-pixel empty-state", role: "alert" }, el("img", { class: "sprite sprite--lg anim-bob", src: "/assets/sprites/icons/chest.png", width: 64, height: 64, alt: "" }),
        el("p", {}, err?.status === 404 ? t("ui.err.not_ready") : errorText(err)), el("button", { type: "button", class: "btn-pixel", onclick: start }, t("ui.err.retry"))));
    }
  }
  await start();
  document.addEventListener("localechange", () => { crumb.textContent = t("ui.back"); h2.textContent = t("ui.mod.sections"); loaded.clear(); side.replaceWith(side = buildSide()); if (mod) { paintProgress(); renderList(); } });
}
