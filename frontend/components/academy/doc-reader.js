// Leitor de PDF da Academia: mostra as páginas (imagens geradas no servidor) dentro de uma moldura pixel art,
// com página anterior/seguinte, ir para uma página, zoom, teclado (setas, Esc) e deslizar o dedo no telemóvel.
// openReader({ id, titulo, pages, page? }) -> { close() }. Sem página, continua onde se ficou neste dispositivo.
// O PDF nunca é descarregado: só a página que se está a ver.
import { el } from "../dom.js";
import { t } from "../../services/i18n.js";

const SWIPE_PX = 60;
const src = (id, n) => `/api/academy/documents/${encodeURIComponent(id)}/pages/${n}`;

const lastKey = (id) => `pyarena.reader.${id}`;
const lastPage = (id) => { try { return Number(localStorage.getItem(lastKey(id))) || 1; } catch (_) { return 1; } };

export function openReader({ id, titulo, pages, page }) {
  const opener = document.activeElement;
  let n = Math.min(Math.max(1, page ?? lastPage(id)), pages), zoom = false, token = 0;

  const img = el("img", { class: "doc-page", alt: "", draggable: "false" });
  const status = el("p", { class: "doc-status", role: "status" });
  const pageInput = el("input", { class: "input-pixel doc-num", type: "number", min: "1", max: String(pages), inputmode: "numeric", "aria-label": t("ui.reader.page_label") });
  const total = el("span", { class: "doc-total" }, `/ ${pages}`);
  const prev = el("button", { type: "button", class: "btn-pixel doc-nav", "aria-label": t("ui.reader.prev") }, "◀");
  const next = el("button", { type: "button", class: "btn-pixel doc-nav", "aria-label": t("ui.reader.next") }, "▶");
  const zoomBtn = el("button", { type: "button", class: "btn-pixel btn-pixel--ghost doc-zoom", "aria-pressed": "false" }, "🔍");
  const close = el("button", { type: "button", class: "btn-pixel btn-pixel--ghost doc-close", "aria-label": t("ui.reader.close") }, "✕");
  const stage = el("div", { class: "doc-stage" }, el("div", { class: "doc-paper" }, img), status);
  const form = el("form", { class: "doc-go" }, pageInput, total);
  const root = el("div", { class: "doc-reader", role: "dialog", "aria-modal": "true", "aria-label": titulo },
    el("div", { class: "doc-frame panel-pixel" },
      el("header", { class: "doc-head" }, el("span", { class: "doc-icon", "aria-hidden": "true" }, "📖"), el("h2", { class: "doc-title" }, titulo), zoomBtn, close),
      stage,
      el("footer", { class: "doc-foot" }, prev, form, next)));

  function show(target) {
    n = Math.min(Math.max(1, target), pages);
    const my = ++token;
    pageInput.value = String(n);
    try { localStorage.setItem(lastKey(id), String(n)); } catch (_) { /* sem storage: abre sempre na 1.ª */ }
    prev.disabled = n <= 1; next.disabled = n >= pages;
    status.textContent = t("ui.reader.loading");
    stage.classList.add("is-loading");
    const probe = new Image();
    probe.onload = () => {
      if (my !== token) return;
      img.src = probe.src; img.alt = t("ui.reader.page_alt", { n, total: pages });
      stage.classList.remove("is-loading"); status.textContent = "";
      stage.scrollTop = 0;
      for (const k of [n + 1, n - 1]) if (k >= 1 && k <= pages) new Image().src = src(id, k); // a seguinte já fica pronta
    };
    probe.onerror = () => { if (my === token) { stage.classList.remove("is-loading"); status.textContent = t("ui.reader.error"); } };
    probe.src = src(id, n);
  }

  function shut() {
    document.removeEventListener("keydown", onKey, true);
    for (const node of document.body.children) if (node !== root) node.inert = false;
    document.body.classList.remove("overflow-hidden");
    root.remove();
    opener?.focus?.();
  }
  function onKey(ev) {
    if (ev.target === pageInput && ev.key !== "Escape") return;
    if (ev.key === "Escape") { ev.preventDefault(); shut(); }
    else if (ev.key === "ArrowRight" || ev.key === "PageDown") { ev.preventDefault(); show(n + 1); }
    else if (ev.key === "ArrowLeft" || ev.key === "PageUp") { ev.preventDefault(); show(n - 1); }
    else if (ev.key === "Home") { ev.preventDefault(); show(1); }
    else if (ev.key === "End") { ev.preventDefault(); show(pages); }
  }

  prev.addEventListener("click", () => show(n - 1));
  next.addEventListener("click", () => show(n + 1));
  close.addEventListener("click", shut);
  form.addEventListener("submit", (ev) => { ev.preventDefault(); const v = Number(pageInput.value); if (v) show(v); pageInput.blur(); });
  pageInput.addEventListener("change", () => { const v = Number(pageInput.value); if (v) show(v); });
  zoomBtn.addEventListener("click", () => { zoom = !zoom; root.classList.toggle("is-zoomed", zoom); zoomBtn.setAttribute("aria-pressed", String(zoom)); zoomBtn.setAttribute("aria-label", t(zoom ? "ui.reader.zoom_out" : "ui.reader.zoom_in")); });
  zoomBtn.setAttribute("aria-label", t("ui.reader.zoom_in"));
  root.addEventListener("click", (ev) => { if (ev.target === root) shut(); }); // tocar fora da moldura fecha

  // Deslizar o dedo para o lado muda de página (só sem zoom, para não lutar com o scroll horizontal)
  let sx = null, sy = 0;
  stage.addEventListener("pointerdown", (ev) => { if (ev.pointerType !== "mouse" && !zoom) { sx = ev.clientX; sy = ev.clientY; } });
  stage.addEventListener("pointerup", (ev) => {
    if (sx == null) return;
    const dx = ev.clientX - sx, dy = ev.clientY - sy;
    sx = null;
    if (Math.abs(dx) > SWIPE_PX && Math.abs(dx) > Math.abs(dy) * 1.5) show(n + (dx < 0 ? 1 : -1));
  });
  stage.addEventListener("pointercancel", () => { sx = null; });

  document.body.append(root);
  for (const node of document.body.children) if (node !== root) node.inert = true;
  document.body.classList.add("overflow-hidden");
  document.addEventListener("keydown", onKey, true);
  close.focus();
  show(n);
  return { close: shut };
}
