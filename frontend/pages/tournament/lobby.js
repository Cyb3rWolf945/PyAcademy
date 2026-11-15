// Lobby do torneio e seletor de agência: criar ou entrar numa agência (máx. 4). O seletor também aparece na ronda
// se o aluno ainda não tem agência (o servidor permite criar/entrar até o torneio acabar; mudar só antes de resolver missões).
import { el } from "../../components/dom.js";
import { api, errorText } from "../../services/api.js";
import { t } from "../../services/i18n.js";
import { toast } from "../../components/toast.js";
import { TEAM_BG, myTeam } from "./ui.js";

const MAX_MEMBERS = 4;

// Lista de agências + formulário para criar. Erros do servidor (ex. tournament.team_locked) vão para um aviso.
export function mountAgencyPicker(host, live) {
  const list = el("section", { class: "grid gap-3" });
  const form = el("form", { class: "panel-pixel grid gap-3" });
  host.replaceChildren(list, form);
  let busy = false;
  let formKey = "";

  async function act(fn) {
    if (busy) return;
    busy = true;
    try { await fn(); await live.refresh(); } catch (err) { toast(errorText(err), "error"); }
    busy = false;
    update();
  }

  function update() {
    const snap = live.snap();
    const id = snap.tournament.id;
    const mine = myTeam(snap);
    const players = snap.teams?.reduce((n, x) => n + x.members.length, 0) ?? 0;
    list.replaceChildren(
      el("p", { class: "text-sm text-muted" }, t("tournament.players_in_agencies", { n: players })),
      ...(snap.teams || []).map((team) => {
        const isMine = mine?.id === team.id;
        const full = team.members.length >= MAX_MEMBERS;
        return el("div", { class: `panel-pixel grid gap-2 ${isMine ? "outline outline-2 outline-accent" : ""}` },
          el("div", { class: "flex items-center gap-2" },
            el("span", { class: `inline-block h-4 w-4 ${TEAM_BG[team.color_idx % 8]}`, "aria-hidden": "true" }),
            el("strong", { class: "min-w-0 flex-1 truncate" }, team.name),
            el("span", { class: "text-xs text-muted" }, `${team.members.length}/${MAX_MEMBERS}`)),
          el("p", { class: "text-sm text-muted" }, team.members.map((m) => m.display_name).join(", ") || "—"),
          isMine ? el("p", { class: "text-sm text-accent" }, t("tournament.you_are_here"))
            : el("button", { type: "button", class: "btn-pixel", disabled: full, onclick: () => act(() => api("POST", `/api/tournaments/${id}/teams/${team.id}/join`)) },
              full ? t("tournament.agency_full") : mine ? t("tournament.switch_agency") : t("tournament.join_agency")));
      }));
    // O formulário só é refeito quando muda o estado, para não perder o que o aluno está a escrever
    const key = mine ? "has" : "none";
    if (key !== formKey) {
      formKey = key;
      const input = el("input", { class: "input-pixel", name: "name", maxlength: 24, required: true, autocomplete: "off", "aria-label": t("tournament.agency_name") });
      form.replaceChildren(
        el("h3", { class: "text-base" }, t("tournament.create_agency")),
        el("label", { class: "grid gap-1 text-sm" }, el("span", {}, t("tournament.agency_name")), input),
        el("button", { class: "btn-pixel btn-pixel--accent", type: "submit" }, t("tournament.create_agency_button")));
      form.onsubmit = (e) => {
        e.preventDefault();
        const name = input.value.trim();
        if (name) act(async () => { await api("POST", `/api/tournaments/${id}/teams`, { name }); input.value = ""; });
      };
    }
  }
  document.addEventListener("localechange", update);
  return { update, destroy() { document.removeEventListener("localechange", update); host.replaceChildren(); } };
}

export function mountLobby(host, live) {
  const status = el("section", { class: "panel-pixel grid gap-2" });
  const pickerHost = el("div", { class: "grid gap-3" });
  host.replaceChildren(status, pickerHost);
  let picker = null;

  function update() {
    const snap = live.snap();
    const mine = myTeam(snap);
    const agencies = snap.tournament.mode === "agencias";
    status.replaceChildren(...[
      el("h2", { class: "text-lg" }, t("tournament.lobby_title")),
      el("p", { class: "text-muted" }, t("tournament.lobby_waiting")),
      agencies
        ? el("p", { class: "text-sm" }, mine ? t("tournament.your_agency", { name: mine.name }) : t("tournament.pick_agency"))
        : el("p", { class: "text-sm text-success" }, t("tournament.individual_ready")),
      agencies ? null : el("p", { class: "text-sm text-muted" }, t("tournament.players_joined", { n: snap.players_count ?? snap.leaderboard?.length ?? 0 }))].filter(Boolean));
    if (agencies && !picker) picker = mountAgencyPicker(pickerHost, live);
    picker?.update();
  }
  document.addEventListener("localechange", update);
  return { update, destroy() { picker?.destroy(); document.removeEventListener("localechange", update); host.replaceChildren(); } };
}
