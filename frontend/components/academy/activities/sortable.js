// Lista ordenável acessível, partilhada pelas atividades "ordenar": arrastar com pointer events (rato no cartão, dedo pela pega),
// "tocar para colocar" (tocar num item e depois no destino) e teclado (setas + Enter). Anuncia tudo num aria-live.
import { el } from "../../dom.js";
import { t } from "../../../services/i18n.js";

const DRAG_THRESHOLD = 5, SCROLL_EDGE = 72, SCROLL_SPEED = 14, SETTLE_MS = 170;

// makeSortable(host, {ids, renderItem(id) -> Node, labelOf(id) -> string, say(text), onChange()})
//   -> {getOrder(), setWrong(positions), clearMarks(), lock(), destroy()}
export function makeSortable(host, { ids, renderItem, labelOf, say = () => {}, onChange = () => {} }) {
  const order = [...ids];
  const items = new Map();
  let locked = false, selected = null, grabbed = null, grabStart = null, drag = null, settling = false, suppressClick = false;
  const descId = `act-help-${Math.random().toString(36).slice(2, 8)}`;
  const help = el("p", { id: descId, class: "sr-only" }, t("act.sort_help"));
  const list = el("ol", { class: "act-sort", role: "list" });
  host.replaceChildren(help, list);

  const pos = (id) => order.indexOf(id);
  const labelFor = (id) => t("act.item_pos", { n: pos(id) + 1, total: order.length, text: labelOf(id) });

  function paint() {
    order.forEach((id, i) => {
      const li = items.get(id);
      list.append(li);
      li.setAttribute("aria-label", labelFor(id));
      li.querySelector(".act-num").textContent = String(i + 1);
      li.tabIndex = i === 0 || li.matches(":focus") ? 0 : -1;
    });
  }

  function moveTo(id, index, announce = true) {
    const from = pos(id);
    index = Math.max(0, Math.min(order.length - 1, index));
    if (from === index) return;
    order.splice(from, 1);
    order.splice(index, 0, id);
    clearMarks();
    paint();
    if (announce) say(t("act.moved", { text: labelOf(id), n: index + 1, total: order.length }));
    onChange();
  }

  const select = (id) => {
    for (const li of items.values()) { li.classList.remove("is-selected"); li.setAttribute("aria-pressed", "false"); }
    selected = id;
    if (id != null) { const li = items.get(id); li.classList.add("is-selected"); li.setAttribute("aria-pressed", "true"); say(t("act.picked", { text: labelOf(id) })); }
  };

  for (const id of order) {
    const grip = el("span", { class: "act-grip", "aria-hidden": "true", title: t("act.drag") }, "⋮⋮");
    const li = el("li", { class: "act-item", role: "listitem", tabindex: -1, "aria-describedby": descId, "aria-pressed": "false", "data-id": String(id) },
      el("span", { class: "act-num", "aria-hidden": "true" }), el("div", { class: "act-body" }, renderItem(id)), grip);
    items.set(id, li);

    // ---- tocar para colocar ----
    li.addEventListener("click", () => {
      if (locked || suppressClick) { suppressClick = false; return; }
      if (selected == null) select(id);
      else if (selected === id) select(null);
      else { const s = selected; select(null); moveTo(s, pos(id)); }
    });

    // ---- teclado ----
    li.addEventListener("keydown", (ev) => {
      if (locked) return;
      const k = ev.key;
      if (k === "ArrowUp" || k === "ArrowDown") {
        ev.preventDefault();
        const d = k === "ArrowUp" ? -1 : 1;
        if (grabbed === id) { moveTo(id, pos(id) + d); li.focus(); }
        else { const nxt = items.get(order[pos(id) + d]); nxt?.focus(); }
      } else if (k === "Enter" || k === " ") {
        ev.preventDefault();
        if (grabbed === id) { grabbed = null; li.classList.remove("is-grabbed"); say(t("act.dropped", { text: labelOf(id), n: pos(id) + 1 })); }
        else { grabbed = id; grabStart = pos(id); li.classList.add("is-grabbed"); say(t("act.grabbed", { text: labelOf(id), n: pos(id) + 1, total: order.length })); }
      } else if (k === "Escape" && grabbed === id) {
        ev.preventDefault();
        moveTo(id, grabStart, false); grabbed = null; li.classList.remove("is-grabbed"); li.focus(); say(t("act.cancelled"));
      }
    });
    li.addEventListener("focus", () => { li.tabIndex = 0; });
    li.addEventListener("blur", () => { if (pos(id) !== 0) li.tabIndex = -1; });

    // ---- arrastar: rato em qualquer parte do cartão, dedo só pela pega (para não bloquear o scroll da página) ----
    li.addEventListener("pointerdown", (ev) => {
      if (locked || drag || settling || (ev.pointerType === "mouse" && ev.button !== 0)) return;
      const onGrip = grip.contains(ev.target);
      if (ev.pointerType !== "mouse" && !onGrip) return;
      if (onGrip) ev.preventDefault();
      drag = { id, li, pid: ev.pointerId, startY: ev.clientY + scrollY, y: ev.clientY, active: false, from: pos(id), target: pos(id) };
      li.setPointerCapture(ev.pointerId);
      if (onGrip) beginDrag();
    });
    li.addEventListener("pointermove", (ev) => {
      if (!drag || drag.id !== id || ev.pointerId !== drag.pid) return;
      drag.y = ev.clientY;
      if (!drag.active && Math.abs(ev.clientY + scrollY - drag.startY) > DRAG_THRESHOLD) beginDrag();
    });
    li.addEventListener("pointerup", (ev) => { if (drag?.id === id && ev.pointerId === drag.pid) finishDrag(true); });
    li.addEventListener("pointercancel", (ev) => { if (drag?.id === id && ev.pointerId === drag.pid) finishDrag(false); });
    li.addEventListener("lostpointercapture", () => { if (drag?.id === id) finishDrag(false); });
  }

  // ---- motor do arrastar: durante o gesto só se mexe em transforms (a ordem real só muda ao largar), a cada frame ----
  function beginDrag() {
    if (drag.active) return;
    drag.active = true;
    select(null);
    const gap = parseFloat(getComputedStyle(list).rowGap) || 0;
    drag.slots = order.map((o) => { const r = items.get(o).getBoundingClientRect(); return { id: o, top: r.top + scrollY, height: r.height }; });
    drag.shift = drag.slots[drag.from].height + gap;
    drag.li.classList.add("is-dragging");
    list.classList.add("is-sorting");
    document.documentElement.classList.add("act-drag-active");
    addEventListener("keydown", onDragKey, true);
    drag.raf = requestAnimationFrame(frame);
  }

  function targetIndex(center) {
    let idx = drag.from;
    drag.slots.forEach((s, i) => {
      const mid = s.top + s.height / 2;
      if (i > drag.from && center > mid) idx = Math.max(idx, i);
      if (i < drag.from && center < mid) idx = Math.min(idx, i);
    });
    return idx;
  }

  function layout(target) {
    drag.slots.forEach((s, i) => {
      if (i === drag.from) return;
      const moved = (i > drag.from && i <= target) ? -drag.shift : (i < drag.from && i >= target) ? drag.shift : 0;
      items.get(s.id).style.transform = moved ? `translate3d(0, ${moved}px, 0)` : "";
    });
  }

  function frame() {
    if (!drag?.active) return;
    // Perto das margens do ecrã a página desliza sozinha, mais depressa quanto mais perto
    const h = innerHeight;
    const edge = drag.y < SCROLL_EDGE ? drag.y - SCROLL_EDGE : drag.y > h - SCROLL_EDGE ? drag.y - (h - SCROLL_EDGE) : 0;
    if (edge) scrollBy(0, Math.round((edge / SCROLL_EDGE) * SCROLL_SPEED));
    const dy = drag.y + scrollY - drag.startY;
    const home = drag.slots[drag.from];
    const min = drag.slots[0].top - home.top - 12;
    const last = drag.slots[drag.slots.length - 1];
    const max = last.top + last.height - home.top - home.height + 12;
    const clamped = Math.max(min, Math.min(max, dy));
    drag.li.style.transform = `translate3d(0, ${clamped}px, 0) scale(1.02)`;
    const target = targetIndex(home.top + clamped + home.height / 2);
    if (target !== drag.target) { drag.target = target; layout(target); }
    drag.raf = requestAnimationFrame(frame);
  }

  const onDragKey = (ev) => { if (ev.key === "Escape" && drag?.active) { ev.preventDefault(); ev.stopPropagation(); finishDrag(false); } };

  function finishDrag(commit) {
    const d = drag;
    drag = null;
    if (!d) return;
    try { d.li.releasePointerCapture(d.pid); } catch (_) { /* já libertado */ }
    if (!d.active) return; // foi só um toque: trata-o o "tocar para colocar"
    cancelAnimationFrame(d.raf);
    removeEventListener("keydown", onDragKey, true);
    suppressClick = true;
    setTimeout(() => { suppressClick = false; }, 60);
    const target = commit ? d.target : d.from;
    // Desliza até ao lugar final e só depois troca a ordem real, sem salto visível
    settling = true;
    drag = null;
    const a = Math.min(d.from, target), b = Math.max(d.from, target);
    const home = d.slots[d.from];
    const others = d.slots.filter((_, i) => i >= a && i <= b && i !== d.from).reduce((sum, s) => sum + s.height, 0);
    const gaps = (b - a) * (d.shift - home.height);
    const offset = target === d.from ? 0 : (target > d.from ? 1 : -1) * (others + gaps);
    if (!commit) d.slots.forEach((s, i) => { if (i !== d.from) items.get(s.id).style.transform = ""; });
    d.li.classList.add("is-settling");
    d.li.style.transform = `translate3d(0, ${offset}px, 0)`;
    let done = false;
    const complete = () => {
      if (done) return;
      done = true;
      list.classList.remove("is-sorting");
      document.documentElement.classList.remove("act-drag-active");
      d.li.classList.remove("is-dragging", "is-settling");
      for (const li of items.values()) li.style.transform = "";
      settling = false;
      if (target !== d.from) moveTo(d.id, target, false);
      say(commit ? t("act.dropped", { text: labelOf(d.id), n: pos(d.id) + 1 }) : t("act.cancelled"));
    };
    d.li.addEventListener("transitionend", complete, { once: true });
    setTimeout(complete, SETTLE_MS + 60);
  }
  paint();

  function clearMarks() { for (const li of items.values()) li.classList.remove("is-wrong"); }
  return {
    getOrder: () => [...order],
    setWrong(positions) { clearMarks(); for (const p of positions || []) items.get(order[p])?.classList.add("is-wrong"); },
    clearMarks,
    lock() { locked = true; for (const li of items.values()) { li.classList.add("is-locked"); li.tabIndex = -1; li.setAttribute("aria-disabled", "true"); } },
    destroy() { host.replaceChildren(); },
  };
}
