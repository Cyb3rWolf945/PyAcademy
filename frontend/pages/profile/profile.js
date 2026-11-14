// Perfil: guarda preferências, muda a palavra-passe, exporta/apaga dados (RGPD) e termina sessão.
import { bootPage } from "../../services/page.js";
import { api, errorText } from "../../services/api.js";
import { changePassword, logout, savePreferences } from "../../services/auth.js";
import { applyTheme, THEMES } from "../../services/theme.js";
import { setLocale, t } from "../../services/i18n.js";
import { el } from "../../components/dom.js";
import { toast } from "../../components/toast.js";

const me = await bootPage({ access: "user", nav: true });
if (me) init(me);

function init(user) {
  const prefs = document.getElementById("prefs-form");
  prefs.display_name.value = user.display_name; // .value: nunca interpretado como HTML

  const fillSelects = () => {
    prefs.locale.replaceChildren(el("option", { value: "pt-PT" }, "🇵🇹 Português (PT)"), el("option", { value: "en" }, "🇬🇧 English"));
    prefs.locale.value = user.locale;
    prefs.preferred_theme.replaceChildren(
      el("option", { value: "" }, t("theme.auto")),
      ...THEMES.map((n) => el("option", { value: n }, t(`theme.${n}`))),
    );
    prefs.preferred_theme.value = user.preferred_theme || "";
  };
  fillSelects();
  document.addEventListener("localechange", fillSelects);

  prefs.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      Object.assign(user, await savePreferences({
        display_name: prefs.display_name.value,
        locale: prefs.locale.value,
        preferred_theme: prefs.preferred_theme.value || null,
      }));
      applyTheme(user.preferred_theme);
      await setLocale(user.locale);
      toast(t("common.saved"), "success");
    } catch (err) { toast(errorText(err), "error"); }
  });

  const pw = document.getElementById("pw-form");
  pw.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      await changePassword(pw.current.value, pw.next.value);
      pw.reset();
      toast(t("password.changed"), "success");
    } catch (err) { toast(errorText(err), "error"); }
  });

  document.getElementById("export-btn").addEventListener("click", async () => {
    try {
      const data = await api("GET", "/api/me/export");
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
      const a = el("a", { href: url, download: "pyarena-dados.json" });
      document.body.append(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) { toast(errorText(err), "error"); }
  });

  const del = document.getElementById("delete-btn");
  const delPw = document.getElementById("delete-password");
  if (user.role === "teacher") { del.hidden = true; delPw.parentElement.hidden = true; }
  del.addEventListener("click", async () => {
    if (!delPw.value) { toast(t("auth.wrong_password"), "error"); return; }
    if (!confirm(t("profile.delete_confirm"))) return;
    try {
      await api("DELETE", "/api/me", { password: delPw.value });
      location.assign("/");
    } catch (err) { toast(errorText(err), "error"); }
  });

  document.getElementById("logout-btn").addEventListener("click", async () => {
    try { await logout(); } finally { location.assign("/"); }
  });
}
