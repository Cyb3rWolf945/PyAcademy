// Ecrã de entrada: login e registo com código de turma. Depois de autenticar, vai para a página certa.
import { bootPage } from "../../services/page.js";
import { login, join, homeFor } from "../../services/auth.js";
import { errorText } from "../../services/api.js";

await bootPage({ access: "public" });

function wire(form, action) {
  const errorBox = form.querySelector("[data-error]");
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const btn = form.querySelector("button[type=submit]");
    btn.disabled = true;
    errorBox.textContent = "";
    try {
      const user = await action(Object.fromEntries(new FormData(form)));
      location.assign(homeFor(user));
    } catch (err) {
      errorBox.textContent = errorText(err); // textContent: nunca HTML em bruto
      btn.disabled = false;
    }
  });
}

wire(document.getElementById("login-form"), (v) => login(v.username, v.password));
wire(document.getElementById("join-form"), (v) => join(v));
