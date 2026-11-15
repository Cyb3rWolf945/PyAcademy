// Lista ordenável acessível, partilhada pelas atividades "ordenar": arrastar com pointer events (rato e dedo, pela pega),
// "tocar para colocar" (tocar num item e depois no destino) e teclado (setas + Enter). Anuncia tudo num aria-live.
import { el } from "../../dom.js";
import { t } from "../../../services/i18n.js";

// makeSortable(host, {ids, renderItem(id) -> Node, labelOf(id) -> string, say(text), onChange()})
//   -> {getOrder(), setWrong(positions), clearMarks(), lock(), destroy()}
export function makeSortable(host, { ids, renderItem, labelOf, say = () => {}, onChange = () => {} }) {
  const order = [...ids];
  const items = new Map();
  let locked = false, selected = null, grabbed = null, grabStart = null, dragging = null, suppressClick = false;
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

    // ---- arrastar (pointer events) pela pega: rato e dedo, sem bloquear o scroll no resto do cartão ----
    grip.addEventListener("pointerdown", (ev) => {
      if (locked || (ev.pointerType === "mouse" && ev.button !== 0)) return;
      ev.preventDefault();
      grip.setPointerCapture(ev.pointerId);
      const r = li.getBoundingClientRect();
      dragging = { id, off: ev.clientY - r.top, pid: ev.pointerId };
      li.classList.add("is-dragging");
      select(null);
    });
    grip.addEventListener("pointermove", (ev) => {
      if (!dragging || dragging.id !== id) return;
      // índice de destino: quantos dos outros itens têm o centro acima do ponteiro
      let idx = 0;
      for (const o of order) {
        if (o === id) continue;
        const rr = items.get(o).getBoundingClientRect();
        if (rr.top + rr.height / 2 < ev.clientY) idx++;
      }
      if (idx !== pos(id)) moveTo(id, idx, false);
      li.style.transform = "";
      const top = li.getBoundingClientRect().top;
      li.style.transform = `translateY(${Math.round(ev.clientY - dragging.off - top)}px)`;
    });
    const end = (ev) => {
      if (!dragging || dragging.id !== id) return;
      li.classList.remove("is-dragging");
      li.style.transform = "";
      try { grip.releasePointerCapture(dragging.pid); } catch (_) { /* já libertado */ }
      dragging = null;
      suppressClick = true;
      setTimeout(() => { suppressClick = false; }, 0);
      say(t("act.dropped", { text: labelOf(id), n: pos(id) + 1 }));
    };
    grip.addEventListener("pointerup", end);
    grip.addEventListener("pointercancel", end);
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
