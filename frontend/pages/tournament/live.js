// Estado ao vivo de um torneio, partilhado pelo ecrã do aluno e pelo projetor: snapshot + eventos do WebSocket
// aplicados de forma idempotente (o socket ignora seq repetidos), diferença de relógio com o servidor e resync.
import { api } from "../../services/api.js";
import { connectTournament } from "../../services/socket.js";

const REFRESH_SAFETY_MS = 30000;

// createLive(id, {onChange(type), onEvent(ev), onStatus(s)}) -> {snap(), offset(), status(), refresh(), start(), destroy()}
export function createLive(id, { onChange, onEvent, onStatus } = {}) {
  let snap = null;
  let offset = 0; // servidor - cliente (ms)
  let status = "reconnecting";
  let sock = null;
  let refreshTimer = null;
  let loading = null;
  let destroyed = false;

  const syncClock = (serverNow) => {
    const s = serverNow ? Date.parse(serverNow) : NaN;
    if (!Number.isNaN(s)) offset = s - Date.now();
  };

  function accept(next) {
    snap = next;
    syncClock(next.server_now);
    sock?.setLastSeq(next.last_seq);
    onChange?.("snapshot");
  }

  async function refresh() {
    if (destroyed) return snap;
    if (!loading) {
      loading = api("GET", `/api/tournaments/${id}/state`).then(accept).finally(() => { loading = null; });
    }
    try { await loading; } catch (err) { if (!snap) throw err; }
    return snap;
  }

  // Várias mudanças seguidas (ou 20 alunos ao mesmo tempo) = um só pedido; o jitter espalha a carga
  function scheduleRefresh(delay = 250) {
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(() => refresh().catch(() => {}), delay + Math.random() * 500);
  }

  const round = (idx) => snap?.rounds?.find((r) => r.idx === idx);

  function apply(ev) {
    if (!snap) return;
    const p = ev.payload || {};
    if (p.server_now) syncClock(p.server_now);
    const tour = snap.tournament;
    const r = p.idx != null ? round(p.idx) : null;
    switch (ev.type) {
      case "leaderboard": snap.leaderboard = p.leaderboard || []; break;
      case "team_updated": snap.teams = p.teams || []; break;
      case "round_started":
        if (r) Object.assign(r, { state: "active", ends_at: p.ends_at, remaining_s: null });
        tour.state = "round_active"; tour.current_round = p.idx; scheduleRefresh(0); break;
      case "round_paused":
        if (r) Object.assign(r, { state: "paused", remaining_s: p.remaining_s });
        tour.state = "round_paused"; break;
      case "round_resumed":
        if (r) Object.assign(r, { state: "active", ends_at: p.ends_at, remaining_s: null });
        tour.state = "round_active"; break;
      case "round_extended": if (r) { if (p.ends_at) r.ends_at = p.ends_at; if (p.remaining_s != null) r.remaining_s = p.remaining_s; } break; // em pausa vem remaining_s e ends_at null
      case "round_closed":
        if (r) r.state = "closed";
        tour.state = "between_rounds"; scheduleRefresh(); break;
      case "tournament_finished":
        tour.state = "finished"; snap.podium = p.podium || snap.podium; scheduleRefresh(); break;
      case "player_joined": if (p.players_count != null) { snap.players_count = p.players_count; tour.players_count = p.players_count; } scheduleRefresh(); break;
      case "mission_solved":
        if (p.participant_key === snap.me?.participant_key || p.participant_key === `t:${snap.me?.team_id}`) scheduleRefresh(0);
        break;
      default: break;
    }
    onChange?.(ev.type);
    onEvent?.(ev);
  }

  return {
    snap: () => snap,
    offset: () => offset,
    status: () => status,
    refresh,
    async start() {
      await refresh();
      sock = connectTournament(id, {
        lastSeq: snap?.last_seq || 0,
        onEvent: apply,
        onStatus: (s) => { status = s; onStatus?.(s); if (s === "online") scheduleRefresh(0); },
        onResync: accept,
        onClock: syncClock,
      });
      // Rede de segurança: sockets "meio mortos" na Wi-Fi da escola não deixam o ecrã desatualizado
      setInterval(() => { if (!destroyed && document.visibilityState === "visible") refresh().catch(() => {}); }, REFRESH_SAFETY_MS);
      document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") scheduleRefresh(0); });
      addEventListener("online", () => scheduleRefresh(0));
      return snap;
    },
    destroy() { destroyed = true; clearTimeout(refreshTimer); sock?.close(); },
  };
}
