// Avisos reutilizáveis: uma torrada salta da torradeira, com animação e som ao aparecer e ao desaparecer.
// toast("Guardado", "success") · tipos: success | error | info | warning · opções: { title, duration, sound }.
// Devolve { dismiss() }. O texto entra sempre por textContent. Atalhos: toast.success(...), toast.error(...), etc.
import { el } from "./dom.js";
import { t } from "../services/i18n.js";
import { playToastIn, playToastOut } from "../services/sfx.js";

const KINDS = ["success", "error", "info", "warning"];
const DURATION = { success: 4000, info: 4500, warning: 6000, error: 7000 }, MAX_VISIBLE = 4, OUT_MS = 460, TITLES = 3;
const live = new Map(); // texto + tipo -> aviso visível (o mesmo aviso não se repete: abana e volta a contar)
let box = null;

function funnyTitle(kind) {
  const key = `toast.${kind}.${1 + Math.floor(Math.random() * TITLES)}`, text = t(key);
  return text === key ? "" : text; // as traduções podem ainda não ter chegado
}

export function toast(message, kind = "info", { title, duration, sound = true } = {}) {
  if (!KINDS.includes(kind)) kind = "info";
  const id = `${kind}:${message}`;
  const repeated = live.get(id);
  if (repeated) { repeated.again(); return repeated; }

  if (!box) { box = el("div", { class: "pxt-box", "aria-live": "polite" }); document.body.append(box); }
  const heading = title ?? funnyTitle(kind);
  const close = el("button", { type: "button", class: "pxt__x", "aria-label": t("toast.close") }, "✕");
  const node = el("div", { class: `pxt pxt--${kind}`, role: kind === "error" ? "alert" : "status" },
    el("div", { class: "pxt__oven", "aria-hidden": "true" },
      el("img", { class: "pxt__slice", src: `/assets/sprites/toast/${kind}.png`, width: 48, height: 48, alt: "" }),
      el("img", { class: "pxt__toaster", src: "/assets/sprites/toast/toaster.png", width: 56, height: 28, alt: "" })),
    el("div", { class: "pxt__text" }, heading ? el("strong", { class: "pxt__title" }, heading) : null, el("p", { class: "pxt__msg" }, message)),
    close,
    el("span", { class: "pxt__bar", "aria-hidden": "true" }));
  const bar = node.querySelector(".pxt__bar");

  // Temporizador que para enquanto o rato ou o foco estão em cima do aviso, para dar tempo de ler
  const total = duration ?? DURATION[kind] + Math.min(3000, message.length * 25);
  let left = total, startedAt = 0, timer = 0, leaving = false;
  const paint = () => { bar.style.setProperty("--pxt-left", String(left / total)); };
  const pause = () => { if (!timer) return; clearTimeout(timer); timer = 0; left -= performance.now() - startedAt; node.classList.add("is-paused"); paint(); };
  const resume = () => {
    if (timer || leaving) return;
    startedAt = performance.now();
    timer = setTimeout(dismiss, Math.max(0, left));
    node.classList.remove("is-paused");
    bar.style.setProperty("--pxt-ms", `${Math.max(0, left)}ms`);
    bar.classList.remove("is-running"); paint(); void bar.offsetWidth; bar.classList.add("is-running");
  };

  function dismiss() {
    if (leaving) return;
    leaving = true;
    clearTimeout(timer); timer = 0;
    live.delete(id);
    if (sound) playToastOut();
    node.classList.add("is-out");
    setTimeout(() => node.remove(), OUT_MS);
  }
  const handle = {
    dismiss,
    again() { // repetido: volta a contar do início e abana
      pause(); left = total; resume();
      node.classList.remove("is-bump"); void node.offsetWidth; node.classList.add("is-bump");
    },
  };

  close.addEventListener("click", dismiss);
  node.addEventListener("pointerenter", pause);
  node.addEventListener("pointerleave", resume);
  node.addEventListener("focusin", pause);
  node.addEventListener("focusout", resume);

  live.set(id, handle);
  box.append(node);
  const visible = [...live.values()];
  if (visible.length > MAX_VISIBLE) visible[0].dismiss();
  if (sound) playToastIn(kind);
  resume();
  return handle;
}

for (const kind of KINDS) toast[kind] = (message, opts) => toast(message, kind, opts);
