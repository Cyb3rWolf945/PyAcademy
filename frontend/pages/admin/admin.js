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
  let classes = [];
  const selectedClassIds = new Set();
  const tournaments = initTournaments(document.getElementById("tournaments"));

  function renderClasses() {
    const query = $("class-search").value.trim().toLocaleLowerCase();
    const visible = classes.filter((c) => `${c.name} ${c.join_code}`.toLocaleLowerCase().includes(query));
    $("class-list").replaceChildren(...visible.map((c) => {
      const checkbox = el("input", { type: "checkbox", class: "h-5 w-5", checked: selectedClassIds.has(c.id), "aria-label": c.name });
      checkbox.addEventListener("click", (ev) => ev.stopPropagation());
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) selectedClassIds.add(c.id); else selectedClassIds.delete(c.id);
        updateBulkControls();
      });
      return el("li", { class: "flex items-center gap-2" },
        checkbox,
        el("button", { class: "btn-pixel secondary flex-1 justify-between", type: "button", onclick: () => select(c) },
          el("span", { class: "truncate" }, c.name), el("span", { class: "text-accent" }, c.join_code)));
    }));
    updateBulkControls(visible);
  }

  function updateBulkControls(visible = classes) {
    $("delete-selected-classes").disabled = selectedClassIds.size === 0;
    const visibleIds = visible.map((c) => c.id);
    $("select-visible-classes").disabled = visibleIds.length === 0;
    $("select-visible-classes").checked = visibleIds.length > 0 && visibleIds.every((id) => selectedClassIds.has(id));
  }

  async function loadClasses() {
    const result = await api("GET", "/api/classes");
    classes = result.classes;
    for (const id of [...selectedClassIds]) if (!classes.some((c) => c.id === id)) selectedClassIds.delete(id);
    tournaments.setClasses(classes);
    $("no-classes").hidden = classes.length > 0;
    renderClasses();
  }

  async function select(c) {
    selected = c;
    tournaments.setActiveClass(c.id);
    $("class-detail").hidden = false;
    $("class-title").textContent = c.name;
    $("join-code").textContent = c.join_code;
    $("import-result").hidden = true;
    await loadStudents();
  }

  $("delete-class-btn").addEventListener("click", async () => {
    if (!selected || !confirm(t("admin.delete_class_confirm"))) return;
    try {
      await api("DELETE", `/api/classes/${selected.id}`);
      selected = null;
      $("class-detail").hidden = true;
      await loadClasses();
      toast(t("admin.class_deleted"), "success");
    } catch (err) { toast(errorText(err), "error"); }
  });

  $("class-search").addEventListener("input", renderClasses);
  $("select-visible-classes").addEventListener("change", (ev) => {
    const query = $("class-search").value.trim().toLocaleLowerCase();
    for (const c of classes.filter((x) => `${x.name} ${x.join_code}`.toLocaleLowerCase().includes(query))) {
      if (ev.target.checked) selectedClassIds.add(c.id); else selectedClassIds.delete(c.id);
    }
    renderClasses();
  });
  $("delete-selected-classes").addEventListener("click", async () => {
    const ids = [...selectedClassIds];
    if (!ids.length || !confirm(t("admin.delete_selected_confirm", { n: ids.length }))) return;
    try {
      await api("POST", "/api/classes/bulk-delete", { class_ids: ids });
      if (selected && selectedClassIds.has(selected.id)) {
        selected = null;
        $("class-detail").hidden = true;
      }
      selectedClassIds.clear();
      await loadClasses();
      toast(t("admin.classes_deleted"), "success");
    } catch (err) { toast(errorText(err), "error"); }
  });

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
