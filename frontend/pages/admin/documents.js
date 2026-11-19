// Painel do professor, secção "Leitura recomendada": carregar PDFs (com barra de progresso), pré-visualizar e apagar.
// Tocar na "Leitura recomendada" de qualquer secção da Academia abre o PDF mais recente (marcado "Em uso").
import { api, csrf, errorText, ApiError } from "../../services/api.js";
import { t } from "../../services/i18n.js";
import { el } from "../../components/dom.js";
import { toast } from "../../components/toast.js";

const MAX_MB = 100;
const reader = (doc, page) => import("../../components/academy/doc-reader.js").then((r) => r.openReader({ ...doc, page }));

// Upload com XMLHttpRequest só para ter progresso; o corpo é o próprio PDF
function uploadPdf(file, titulo, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/academy/documents?titulo=${encodeURIComponent(titulo)}`);
    xhr.setRequestHeader("Content-Type", "application/pdf");
    xhr.setRequestHeader("Accept", "application/json");
    if (csrf()) xhr.setRequestHeader("X-CSRF-Token", csrf());
    xhr.upload.onprogress = (ev) => { if (ev.lengthComputable) onProgress(Math.round((ev.loaded / ev.total) * 100)); };
    xhr.onload = () => {
      let body = {};
      try { body = JSON.parse(xhr.responseText || "{}"); } catch (_) { /* sem JSON */ }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body);
      else reject(new ApiError(xhr.status, body.error || (xhr.status === 413 ? "common.too_large" : "common.error")));
    };
    xhr.onerror = () => reject(new ApiError(0, "common.network"));
    xhr.send(file);
  });
}

export function initDocuments(root) {
  let docs = [];

  const titleInput = el("input", { class: "input-pixel", name: "titulo", maxlength: 120, required: true });
  const fileInput = el("input", { class: "input-pixel", type: "file", accept: "application/pdf,.pdf", required: true });
  const rights = el("input", { type: "checkbox", class: "h-6 w-6 shrink-0", required: true });
  const sendBtn = el("button", { type: "submit", class: "btn-pixel btn-pixel--accent" });
  const bar = el("span");
  const progress = el("div", { class: "docs-bar", hidden: true, role: "progressbar", "aria-valuemin": "0", "aria-valuemax": "100" }, bar);
  const form = el("form", { class: "grid gap-3" });
  const docList = el("ul", { class: "grid gap-2" });

  fileInput.addEventListener("change", () => {
    const f = fileInput.files?.[0];
    if (f && !titleInput.value.trim()) titleInput.value = f.name.replace(/\.pdf$/i, "").slice(0, 120);
  });

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const f = fileInput.files?.[0];
    if (!f) return;
    if (f.size > MAX_MB * 1024 * 1024) { toast(t("common.too_large"), "error"); return; }
    sendBtn.disabled = true; progress.hidden = false;
    const setP = (v) => { bar.style.setProperty("--v", String(v)); progress.setAttribute("aria-valuenow", String(v)); };
    setP(0);
    try {
      const doc = await uploadPdf(f, titleInput.value.trim() || f.name, setP);
      toast(t("admin.docs.uploaded", { title: doc.titulo, pages: doc.pages }), "success");
      form.reset();
      await load();
    } catch (err) { toast(errorText(err), "error"); }
    finally { sendBtn.disabled = false; progress.hidden = true; }
  });

  function paintShell() {
    sendBtn.textContent = t("admin.docs.upload");
    form.replaceChildren(
      el("label", { class: "grid gap-1 text-sm" }, el("span", {}, t("admin.docs.file")), fileInput),
      el("label", { class: "grid gap-1 text-sm" }, el("span", {}, t("admin.docs.title_field")), titleInput),
      el("label", { class: "flex min-h-[44px] items-center gap-3 text-sm" }, rights, el("span", {}, t("admin.docs.rights"))),
      progress, sendBtn);
    root.replaceChildren(
      el("h2", { class: "text-lg" }, t("admin.docs.heading")),
      el("p", { class: "text-sm text-muted" }, t("admin.docs.help")),
      form,
      el("h3", {}, t("admin.docs.list")), docList);
  }

  function paintDocs() {
    if (!docs.length) { docList.replaceChildren(el("li", { class: "text-sm text-muted" }, t("admin.docs.none"))); return; }
    docList.replaceChildren(...docs.map((d, i) => el("li", { class: "flex flex-wrap items-center gap-2" },
      el("span", { class: "min-w-0 flex-1" }, el("strong", {}, d.titulo), i === 0 ? el("span", { class: "badge-pixel ml-2" }, t("admin.docs.in_use")) : null, el("br"),
        el("span", { class: "text-sm text-muted" }, t("admin.docs.meta", { pages: d.pages, mb: (d.size_bytes / 1048576).toFixed(1) }))),
      el("button", { type: "button", class: "btn-pixel btn-pixel--ghost", onclick: () => reader(d, 1) }, t("admin.docs.preview")),
      el("button", { type: "button", class: "btn-pixel btn-pixel--danger", onclick: async () => {
        if (!confirm(t("admin.docs.delete_confirm", { title: d.titulo }))) return;
        try { await api("DELETE", `/api/academy/documents/${d.id}`); toast(t("admin.docs.deleted"), "success"); await load(); }
        catch (err) { toast(errorText(err), "error"); }
      } }, t("admin.docs.delete")))));
  }

  async function load() {
    try { docs = (await api("GET", "/api/academy/documents")).documents; }
    catch (err) { toast(errorText(err), "error"); return; }
    paintDocs();
  }

  paintShell();
  load();
  document.addEventListener("localechange", () => { paintShell(); paintDocs(); });
}
