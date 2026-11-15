// Protótipo A0 da Academia: escolhe um de 4 exemplos, mostra a vista ligada (fluxograma + Python) e um "Passo a passo (demo)".
// Não usa o backend nem exige sessão: só tema e idioma.
import { applyTheme } from "../../services/theme.js";
import { getLocale, initialLocale, setLocale, t } from "../../services/i18n.js";
import { mountLangSwitch } from "../../components/lang-switch.js";
import { el } from "../../components/dom.js";
import { EXAMPLES, exampleById } from "../../components/academy/examples.js";
import { pythonText, pickText } from "../../components/academy/model.js";
import { renderLinked } from "../../components/academy/linked-view.js";

applyTheme();
await setLocale(initialLocale(), { save: false });
document.querySelectorAll("[data-lang-switch]").forEach(mountLangSwitch);

const picker = document.getElementById("picker");
const host = document.getElementById("linked");
const generated = document.getElementById("generated");
const demoBtn = document.getElementById("demo");
let current = new URLSearchParams(location.search).get("ex") || EXAMPLES[0].id;
let linked = null, timer = null;

function stopDemo() { clearTimeout(timer); timer = null; demoBtn.textContent = t("fx.step_demo"); linked?.clear(); }

function show() {
  stopDemo();
  linked?.destroy();
  const ex = exampleById(current);
  linked = renderLinked(host, ex, { locale: getLocale() });
  generated.textContent = pythonText(ex);
  picker.replaceChildren(...EXAMPLES.map((e) => el("button", {
    type: "button", class: `btn-pixel ${e.id === ex.id ? "btn-pixel--accent" : "btn-pixel--ghost"}`, "aria-pressed": String(e.id === ex.id),
    onclick: () => { current = e.id; show(); },
  }, pickText(e.titulo, getLocale()))));
}

// Percorre o demoPath do exemplo, um passo por segundo, só para mostrar a ideia (sem execução)
function startDemo() {
  const path = exampleById(current).demoPath || [];
  let i = 0;
  const tick = () => {
    if (i >= path.length) { stopDemo(); return; }
    linked.select(path[i++]);
    timer = setTimeout(tick, 1000);
  };
  tick();
}

demoBtn.addEventListener("click", () => { if (timer) { stopDemo(); return; } demoBtn.textContent = t("fx.stop_demo"); startDemo(); });
document.getElementById("clear").addEventListener("click", () => { stopDemo(); linked.clear(); });
document.addEventListener("localechange", () => { show(); });
show();
