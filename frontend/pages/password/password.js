// Ecrã de mudança obrigatória de palavra-passe; no fim segue para o ecrã certo do papel.
import { bootPage } from "../../services/page.js";
import { changePassword, homeFor } from "../../services/auth.js";
import { errorText } from "../../services/api.js";

await bootPage({ access: "password" });
const form = document.getElementById("pw-form");
const errorBox = form.querySelector("[data-error]");
form.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  errorBox.textContent = "";
  const v = Object.fromEntries(new FormData(form));
  try {
    location.assign(homeFor(await changePassword(v.current, v.next)));
  } catch (err) {
    errorBox.textContent = errorText(err);
  }
});
