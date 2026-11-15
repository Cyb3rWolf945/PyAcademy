// Visualizador de slides da Academia: miniaturas dos intervalos `slides` da secção + modal com setas, teclado, swipe,
// armadilha de foco e Esc. As imagens vêm de GET /api/academy/slides/{deck}/{n} (precisam de sessão; o cookie segue com o <img>).
// Se o deck ainda não foi importado (404), mostra "slides ainda não importados". Só nós DOM, nunca HTML em bruto.
import { el } from "../dom.js";
import { t } from "../../services/i18n.js";

const url = (s) => `/api/academy/slides/${encodeURIComponent(s.deck)}/${s.n}`;
const MAX_THUMBS = 8;

// refs: [{deck, de, ate}] -> [{deck, n}]
export function expandSlides(refs) {
  const out = [];
  for (const r of refs || []) for (let n = r.de; n <= (r.ate ?? r.de) && out.length < 200; n++) out.push({ deck: r.deck, n });
  return out;
}

// Mostra a tira de miniaturas em `host`; devolve {destroy()}
export function mountSlides(host, refs) {
  const slides = expandSlides(refs);
  host.replaceChildren();
  if (!slides.length) return { destroy() {} };
  const note = el("p", { class: "slides-note", role: "status", hidden: true }, t("ui.slides.missing"));
  const strip = el("div", { class: "slides-strip" });
  const shown = slides.slice(0, MAX_THUMBS);
  shown.forEach((s, i) => {
    const img = el("img", { src: url(s), alt: t("ui.slides.alt", { n: s.n }), loading: "lazy", width: 160, height: 90 });
    img.addEventListener("error", () => { strip.hidden = true; note.hidden = false; }, { once: true });
    strip.append(el("button", { type: "button", class: "slides-thumb", "aria-label": t("ui.slides.open", { n: s.n }), onclick: (e) => openModal(slides, i, e.currentTarget) }, img));
  });
  if (slides.length > shown.length) strip.append(el("button", { type: "button", class: "slides-thumb slides-more", onclick: (e) => openModal(slides, MAX_THUMBS, e.currentTarget) }, `+${slides.length - shown.length}`));
  host.append(el("h5", { class: "slides-h" }, el("span", { "aria-hidden": "true" }, "📑 "), t("ui.slides.title")), strip, note);
  return { destroy() { host.replaceChildren(); } };
}

function openModal(slides, start, opener) {
  let i = start;
  const prev = document.activeElement;
  const img = el("img", { class: "slides-big", alt: "" });
  const missing = el("p", { class: "slides-note", role: "alert", hidden: true }, t("ui.slides.missing"));
  const counter = el("span", { class: "slides-count", "aria-live": "polite" });
  const btn = (label, txt, fn, cls = "") => el("button", { type: "button", class: `btn-pixel btn-pixel--ghost ${cls}`, "aria-label": label, title: label, onclick: fn }, txt);
  const bPrev = btn(t("ui.slides.prev"), "‹", () => go(-1)), bNext = btn(t("ui.slides.next"), "›", () => go(1));
  const bClose = btn(t("ui.slides.close"), "✕", close);
  const dlg = el("div", { class: "slides-modal", role: "dialog", "aria-modal": "true", "aria-label": t("ui.slides.title"), tabindex: "-1" },
    el("div", { class: "slides-modal__bar" }, counter, bClose),
    el("div", { class: "slides-modal__stage" }, bPrev, el("div", { class: "slides-modal__img" }, img, missing), bNext));
  const veil = el("div", { class: "slides-veil" }, dlg);

  function show() {
    i = Math.max(0, Math.min(slides.length - 1, i));
    missing.hidden = true; img.hidden = false;
    img.src = url(slides[i]); img.alt = t("ui.slides.alt", { n: slides[i].n });
    counter.textContent = `${i + 1} / ${slides.length}`;
    bPrev.disabled = i === 0; bNext.disabled = i === slides.length - 1;
  }
  const go = (d) => { i += d; show(); };
  img.addEventListener("error", () => { img.hidden = true; missing.hidden = false; });
  function onKey(e) {
    if (e.key === "Escape") { e.preventDefault(); close(); }
    else if (e.key === "ArrowRight") go(1);
    else if (e.key === "ArrowLeft") go(-1);
    else if (e.key === "Home") { i = 0; show(); } else if (e.key === "End") { i = slides.length - 1; show(); }
    else if (e.key === "Tab") { // armadilha de foco
      const f = [...dlg.querySelectorAll("button:not([disabled])")];
      if (!f.length) return;
      const first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  }
  // swipe horizontal com pointer events
  let x0 = null;
  dlg.addEventListener("pointerdown", (e) => { x0 = e.clientX; });
  dlg.addEventListener("pointerup", (e) => { if (x0 != null && Math.abs(e.clientX - x0) > 50) go(e.clientX < x0 ? 1 : -1); x0 = null; });
  veil.addEventListener("click", (e) => { if (e.target === veil) close(); });
  function close() {
    document.removeEventListener("keydown", onKey, true);
    veil.remove(); document.body.classList.remove("slides-open");
    (opener || prev)?.focus?.();
  }
  document.addEventListener("keydown", onKey, true);
  document.body.append(veil); document.body.classList.add("slides-open");
  show(); bClose.focus();
}
