// Anti-cheat do torneio (aluno): durante a ronda, colar texto ou sair da janela toca a sirene, mostra o ecrã "apanhado" e
// avisa o servidor, que bloqueia as submissões até o professor deixar voltar. O servidor é quem decide; isto é só o aviso.
import { api, ApiError } from "../../services/api.js";
import { t } from "../../services/i18n.js";
import { el } from "../../components/dom.js";
import { toast } from "../../components/toast.js";
import { playSiren, stopSiren, unlockSiren } from "../../components/siren.js";

const BLUR_GRACE_MS = 400, RETRY_MS = 3000, POLL_MS = 4000, FLASH_MS = 600;
const PENDING = (id) => `pyarena.ac.pending.${id}`;

// Barra de luzes da polícia em pixel art: . vazio, # metal, r/b luzes (acendem à vez), w brilho
const BAR = [
  "......####....####......",
  ".....#rrrr#..#bbbb#.....",
  "....#rrwwrr##bbwwbb#....",
  "....#rrrrrr##bbbbbb#....",
  "########################",
  "#mmmmmmmmmmmmmmmmmmmmmm#",
  "########################",
];
const COLORS = { "#": "#1b1d2a", m: "#d8dcea", w: "#ffffff" };

function drawBar(canvas, redOn) {
  const g = canvas.getContext("2d");
  g.clearRect(0, 0, canvas.width, canvas.height);
  BAR.forEach((row, y) => [...row].forEach((c, x) => {
    if (c === ".") return;
    const lit = c === "r" ? redOn : c === "b" ? !redOn : true;
    g.fillStyle = c === "r" ? (lit ? "#ff2a2a" : "#5a1414") : c === "b" ? (lit ? "#2a7bff" : "#14285a") : (c === "w" && !lit ? "#888" : COLORS[c]);
    g.fillRect(x, y, 1, 1);
  }));
}

const newId = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
const store = (fn) => { try { return fn(localStorage); } catch (_) { return null; } };

export function mountAnticheat(live) {
  const tid = live.snap().tournament.id;
  let armed = false, overlay = null, flash = 0, poll = 0, retry = 0, blurTimer = 0, destroyed = false, sending = false;

  const rule = el("p", { class: "ac-rule", role: "note", hidden: true }, t("tournament.ac_rule"));
  document.getElementById("view").before(rule);

  function setBackground(off) {
    for (const node of document.body.children) if (node !== overlay) node.inert = off;
  }

  function showCaught(kind) {
    if (overlay) { overlay.querySelector(".ac-why").textContent = t(`tournament.ac_kind_${kind}`); return; }
    const bar = el("canvas", { class: "ac-bar", width: BAR[0].length, height: BAR.length, "aria-hidden": "true" });
    overlay = el("div", { class: "ac-overlay", role: "alertdialog", "aria-modal": "true", "aria-labelledby": "ac-title", tabindex: "-1" },
      el("div", { class: "ac-card" }, bar,
        el("h2", { id: "ac-title", class: "ac-title" }, t("tournament.ac_title")),
        el("p", { class: "ac-why" }, t(`tournament.ac_kind_${kind}`)),
        el("p", { class: "ac-wait" }, t("tournament.ac_wait")),
        el("p", { class: "ac-status", role: "status" }, t("tournament.ac_waiting"))));
    document.body.append(overlay);
    setBackground(true);
    overlay.focus();
    drawBar(bar, true);
    // Alterna devagar (menos de 3 clarões por segundo) e fica parado para quem pede menos movimento
    if (!matchMedia("(prefers-reduced-motion: reduce)").matches) { let on = true; flash = setInterval(() => { on = !on; drawBar(bar, on); }, FLASH_MS); }
    poll = setInterval(() => live.refresh().catch(() => {}), POLL_MS);
  }

  function hideCaught() {
    if (!overlay) return;
    clearInterval(flash); clearInterval(poll);
    stopSiren();
    setBackground(false);
    overlay.remove(); overlay = null;
  }

  // Entrega garantida: fica guardado até o servidor responder, mesmo que o aluno recarregue a página ou perca a rede
  async function send() {
    const pending = store((s) => JSON.parse(s.getItem(PENDING(tid)) || "null"));
    if (!pending || sending || destroyed) return;
    sending = true;
    try {
      const res = await api("POST", `/api/tournaments/${tid}/anticheat/report`, pending);
      store((s) => s.removeItem(PENDING(tid)));
      const snap = live.snap();
      if (snap?.me) snap.me.anticheat = res;
      update();
    } catch (err) {
      if (err instanceof ApiError && err.status >= 400 && err.status < 500 && err.status !== 408 && err.status !== 429) { store((s) => s.removeItem(PENDING(tid))); hideCaught(); }
      else retry = setTimeout(send, RETRY_MS);
    } finally { sending = false; }
  }

  function caught(kind) {
    if (!armed || overlay) return;
    armed = false;
    store((s) => s.setItem(PENDING(tid), JSON.stringify({ client_id: newId(), kind })));
    showCaught(kind);
    playSiren();
    send();
  }

  // ---- deteção ----
  const onPaste = (ev) => { if (!armed) return; ev.preventDefault(); ev.stopImmediatePropagation(); caught("paste"); };
  const onDrop = (ev) => { if (!armed) return; ev.preventDefault(); ev.stopImmediatePropagation(); caught("drop"); };
  const onBeforeInput = (ev) => {
    if (!armed || (ev.inputType !== "insertFromPaste" && ev.inputType !== "insertFromDrop")) return;
    ev.preventDefault(); ev.stopImmediatePropagation(); caught(ev.inputType === "insertFromDrop" ? "drop" : "paste");
  };
  const onVisibility = () => { if (document.visibilityState === "hidden") caught("hidden"); };
  // Uma pequena tolerância evita falsos alarmes quando o sistema tira o foco por uma fração de segundo
  const onBlur = () => { clearTimeout(blurTimer); blurTimer = setTimeout(() => { if (!document.hasFocus()) caught("blur"); }, BLUR_GRACE_MS); };
  const onFocus = () => clearTimeout(blurTimer);
  const onGesture = () => unlockSiren();

  document.addEventListener("paste", onPaste, true);
  document.addEventListener("drop", onDrop, true);
  document.addEventListener("beforeinput", onBeforeInput, true);
  document.addEventListener("visibilitychange", onVisibility);
  addEventListener("blur", onBlur);
  addEventListener("focus", onFocus);
  addEventListener("pointerdown", onGesture, true);
  addEventListener("keydown", onGesture, true);

  function update() {
    const snap = live.snap();
    const ac = snap?.me?.anticheat;
    const waiting = !!store((s) => s.getItem(PENDING(tid)));
    armed = !!ac?.armed && !overlay && !waiting;
    rule.textContent = t("tournament.ac_rule");
    rule.hidden = !(ac && (ac.armed || snap.tournament.state === "lobby" || snap.tournament.state === "between_rounds"));
    if (ac?.locked) showCaught(ac.kind);
    else if (overlay && !waiting) {
      const wasLocked = overlay.dataset.confirmed === "1";
      hideCaught();
      armed = !!ac?.armed;
      if (wasLocked) toast(t("tournament.ac_released"), "success");
    }
    if (ac?.locked && overlay) overlay.dataset.confirmed = "1";
    // A competir (ou bloqueado) não há menu: carregar numa ligação faria disparar o alarme
    const nav = document.querySelector("[data-bottom-nav]");
    if (nav) nav.hidden = !!(armed || overlay || waiting);
  }

  send(); // um aviso que ficou por entregar (a página foi recarregada a meio)
  update();
  return {
    update,
    destroy() {
      destroyed = true;
      clearTimeout(retry); clearTimeout(blurTimer);
      hideCaught(); rule.remove();
      document.removeEventListener("paste", onPaste, true);
      document.removeEventListener("drop", onDrop, true);
      document.removeEventListener("beforeinput", onBeforeInput, true);
      document.removeEventListener("visibilitychange", onVisibility);
      removeEventListener("blur", onBlur);
      removeEventListener("focus", onFocus);
      removeEventListener("pointerdown", onGesture, true);
      removeEventListener("keydown", onGesture, true);
    },
  };
}
