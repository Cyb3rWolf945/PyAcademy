// Controlos do Bit a Bit: leitura do objetivo, teclado numérico/campo decimal (linhas bin→dec), botões de bits (linhas dec→bin),
// botão OK e atalhos de teclado (setas escolhem o bit, Espaço alterna, dígitos + Enter respondem). A vista é só DOM com el().
import { el } from "../../dom.js";
import { t } from "../../../services/i18n.js";

export function createControls(host, { onSubmit, onChange, sfx = () => {} }) {
  let row = null, bits = [], cursor = 0, buf = "";
  const fine = matchMedia("(pointer: fine)").matches;

  const now = el("p", { class: "bit-now", "aria-live": "polite" });
  const input = el("input", { class: "input-pixel bit-input", type: "text", inputmode: fine ? "numeric" : "none", maxlength: 3, autocomplete: "off", "data-i18n-aria": "bit.input_label", "aria-label": t("bit.input_label"), "data-i18n-placeholder": "bit.input_ph", placeholder: t("bit.input_ph") });
  const keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"].map((d) => el("button", { type: "button", class: "btn-pixel secondary bit-key", "data-d": d }, d));
  const back = el("button", { type: "button", class: "btn-pixel secondary bit-key bit-key--wide", "data-act": "back", "aria-label": t("bit.erase"), "data-i18n-aria": "bit.erase" }, "⌫");
  const pad = el("div", { class: "bit-numpad" }, keys, back);
  const dec = pad;
  const switches = el("div", { class: "bit-switches", role: "group", "data-i18n-aria": "bit.switches", "aria-label": t("bit.switches") });
  const ok = el("button", { type: "button", class: "btn-pixel btn-pixel--accent btn-pixel--lg bit-ok", "data-act": "ok" }, t("bit.check"));
  ok.dataset.i18n = "bit.check";
  const line = el("div", { class: "bit-line" }, now, input);
  host.replaceChildren(line, pad, switches, ok);

  const value = () => (row.kind === "b2d" ? (buf === "" ? NaN : Number(buf)) : parseInt(bits.join("") || "0", 2));
  const emit = () => { if (row) onChange?.(row, { bits, buf, cursor }); };

  function setRow(next) {
    row = next; buf = ""; input.value = ""; cursor = 0;
    if (!row) { host.hidden = true; return; }
    host.hidden = false;
    bits = Array(row.bits).fill(0);
    dec.hidden = row.kind !== "b2d"; input.hidden = row.kind !== "b2d";
    switches.hidden = row.kind !== "d2b";
    now.textContent = row.kind === "b2d" ? t("bit.now_bd", { bits: row.value.toString(2).padStart(row.bits, "0") }) : t("bit.now_db", { n: row.value });
    switches.replaceChildren(...Array.from({ length: row.bits }, (_, i) => {
      const w = 2 ** (row.bits - 1 - i);
      return el("button", { type: "button", class: "bit-sw", "aria-pressed": "false", "data-i": i, "aria-label": t("bit.switch", { w }) }, el("b", {}, "0"), el("small", {}, String(w)));
    }));
    if (fine && row.kind === "b2d") input.focus({ preventScroll: true });
    paintSwitches();
    emit();
  }

  function paintSwitches() {
    switches.querySelectorAll(".bit-sw").forEach((b, i) => { b.setAttribute("aria-pressed", String(bits[i] === 1)); b.firstChild.textContent = String(bits[i]); b.classList.toggle("is-cursor", i === cursor); });
  }
  function toggle(i) { if (!row || row.kind !== "d2b") return; cursor = i; bits[i] ^= 1; sfx("toggle"); paintSwitches(); emit(); }
  function type(d) { if (!row || row.kind !== "b2d" || buf.length >= 3) return; buf += d; input.value = buf; sfx("key"); emit(); }
  function erase() { buf = buf.slice(0, -1); input.value = buf; emit(); }
  function submit() { if (!row) return; const v = value(); if (Number.isNaN(v)) return; onSubmit(v); }

  host.addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    if (b.dataset.d) type(b.dataset.d);
    else if (b.dataset.act === "back") erase();
    else if (b.dataset.act === "ok") submit();
    else if (b.classList.contains("bit-sw")) toggle(Number(b.dataset.i));
  });
  switches.addEventListener("focusin", (e) => { const b = e.target.closest(".bit-sw"); if (b) { cursor = Number(b.dataset.i); paintSwitches(); emit(); } });
  input.addEventListener("input", () => { buf = input.value.replace(/\D/g, "").slice(0, 3); input.value = buf; emit(); });

  return {
    setRow,
    toggleAt: toggle,
    reset() { buf = ""; input.value = ""; bits = bits.map(() => 0); paintSwitches(); emit(); },
    // teclado global durante o jogo; devolve true se a tecla foi tratada
    key(e) {
      if (!row || e.ctrlKey || e.metaKey || e.altKey) return false;
      if (e.target.closest?.("[data-keep]")) return false; // botões Pausa/Som/Terminar mantêm o comportamento nativo
      const k = e.key;
      if (row.kind === "d2b") {
        if (k === "ArrowLeft") { cursor = (cursor + row.bits - 1) % row.bits; }
        else if (k === "ArrowRight") { cursor = (cursor + 1) % row.bits; }
        else if (k === " " || k === "Spacebar") { toggle(cursor); return true; }
        else if (k === "1" || k === "0") { bits[cursor] = Number(k); sfx("toggle"); }
        else if (k !== "Enter") return false;
        if (k === "Enter") { submit(); return true; }
        paintSwitches(); emit(); return true;
      }
      if (/^\d$/.test(k)) { if (e.target !== input) type(k); else return false; return true; }
      if (k === "Backspace") { if (e.target !== input) { erase(); return true; } return false; }
      if (k === "Enter") { submit(); return true; }
      return false;
    },
    paint: paintSwitches,
    get state() { return { bits, buf, cursor }; },
    focusInput() { if (fine && row?.kind === "b2d") input.focus({ preventScroll: true }); },
  };
}
