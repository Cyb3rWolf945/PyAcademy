// Painel do professor: turmas, código de entrada, importação CSV (palavras-passe temporárias mostradas 1 vez), alunos.
import { bootPage } from "../../services/page.js";
import { api, errorText } from "../../services/api.js";
import { t } from "../../services/i18n.js";
import { el } from "../../components/dom.js";
import { toast } from "../../components/toast.js";
import { initTournaments } from "./tournaments.js";

const me = await bootPage({ access: "teacher", nav: true });
if (me) init();

function init() {
  const $ = (id) => document.getElementById(id);
  let selected = null;
  const tournaments = initTournaments(document.getElementById("tournaments"));

  async function loadClasses() {
    const { classes } = await api("GET", "/api/classes");
    tournaments.setClasses(classes);
    $("no-classes").hidden = classes.length > 0;
    $("class-list").replaceChildren(...classes.map((c) =>
      el("li", {}, el("button", { class: "btn-pixel secondary w-full justify-between", type: "button", onclick: () => select(c) },
        el("span", {}, c.name), el("span", { class: "text-accent" }, c.join_code)))));
  }

  async function select(c) {
    selected = c;
    $("class-detail").hidden = false;
    $("class-title").textContent = c.name;
    $("join-code").textContent = c.join_code;
    $("import-result").hidden = true;
    await loadStudents();
  }

  async function loadStudents() {
    const { students } = await api("GET", `/api/classes/${selected.id}/students`);
    const rows = students.map((s) => el("tr", {},
      el("td", { class: "py-1 pr-3" }, s.display_name),
      el("td", { class: "py-1 pr-3 text-muted" }, s.username),
      el("td", { class: "py-1 text-muted" }, s.must_change_password ? t("admin.pending_password") : "")));
    $("students-body").replaceChildren(...rows);
  }

  $("class-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      const c = await api("POST", "/api/classes", { name: ev.target.name.value });
      ev.target.reset();
      await loadClasses();
      await select(c);
    } catch (err) { toast(errorText(err), "error"); }
  });

  $("csv-file").addEventListener("change", async (ev) => {
    const file = ev.target.files[0];
    if (file) $("import-form").csv.value = await file.text();
  });

  $("import-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      const res = await api("POST", `/api/classes/${selected.id}/students/import`, { csv: ev.target.csv.value });
      $("temp-body").replaceChildren(...res.created.map((s) => el("tr", {},
        el("td", { class: "py-1 pr-3" }, s.display_name),
        el("td", { class: "py-1 pr-3 text-muted" }, s.username),
        el("td", { class: "py-1 font-bold text-accent" }, s.temp_password))));
      $("import-errors").replaceChildren(...res.errors.map((e) => el("li", {}, `${t("admin.row")} ${e.row}: ${t(e.error)}`)));
      $("import-result").hidden = false;
      ev.target.reset();
      await loadStudents();
    } catch (err) { toast(errorText(err), "error"); }
  });

  loadClasses().catch((err) => toast(errorText(err), "error"));
}
