// Estado ao vivo de uma mesa de poker: snapshot (GET .../state, com as MINHAS cartas), eventos do WebSocket
// (/ws/extra/poker/{id}, com seq e replay) e ações idempotentes com action_id. As cartas dos outros nunca vêm no snapshot;
// só aparecem num evento/estado de showdown.
import { api } from "../../../services/api.js";
import { connectChannel } from "../../../services/socket.js";
import { newClientId } from "../../../services/storage.js";
import { normCard } from "./cards.js";

// Estados devolvidos pelas ações têm o mesmo formato do snapshot (mais `duplicate`)
const isSnap = (r) => r && r.table && r.seats;

export const ACTION = { fold: "fold", check: "check", call: "call", bet: "bet", raise: "raise", allIn: "all_in" };

// createLive(tableId, {onChange(kind), onEvent(ev), onStatus(s)}) -> {snap(), offset(), start(), refresh(), act(type, amount), sit(seat, buyIn), leave(), pending(), revealed(), destroy()}
export function createLive(tableId, { onChange, onEvent, onStatus } = {}) {
  let snap = null, offset = 0, sock = null, refreshTimer = null, loading = null, destroyed = false;
  let pendingAction = null; // {id, type, amount}: o mesmo action_id é reenviado se a rede falhar
  let revealed = new Map(); // user_id -> [cartas] (só de eventos de showdown)
  let lastHandId = null;
  const base = `/api/extra/poker/tables/${tableId}`;

  const syncClock = (iso) => { const s = iso ? Date.parse(iso) : NaN; if (!Number.isNaN(s)) offset = s - Date.now(); };

  function accept(next) {
    snap = next;
    syncClock(next.server_now);
    sock?.setLastSeq(next.last_seq);
    // As cartas dos outros só chegam por eventos de showdown; ficam visíveis até começar a mão seguinte
    const hid = next.hand?.id ?? null;
    if (hid != null && hid !== lastHandId) { lastHandId = hid; revealed = new Map(); }
    onChange?.("snapshot");
  }

  async function refresh() {
    if (destroyed) return snap;
    if (!loading) loading = api("GET", `${base}/state`).then(accept).finally(() => { loading = null; });
    try { await loading; } catch (err) { if (!snap) throw err; }
    return snap;
  }
  function scheduleRefresh(delay = 120) {
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(() => refresh().catch(() => {}), delay + Math.random() * 120);
  }

  function apply(ev) {
    const p = ev.payload || {};
    if (p.server_now) syncClock(p.server_now);
    if (ev.type === "showdown") for (const h of p.hands || p.reveal || []) if (h.cards) revealed.set(h.user_id, h.cards.map(normCard));
    if (ev.type === "hand_started") { revealed = new Map(); lastHandId = p.hand_id ?? lastHandId; }
    onEvent?.(ev, snap);
    scheduleRefresh(ev.type === "turn" ? 0 : 120); // a verdade vem sempre do snapshot; o evento serve para animar e para o registo
  }

  return {
    snap: () => snap, offset: () => offset, pending: () => pendingAction, revealed: () => revealed,
    async start() {
      await refresh();
      sock = connectChannel({
        wsPath: `/ws/extra/poker/${tableId}`, lastSeq: snap?.last_seq || 0,
        fetchSnapshot: () => api("GET", `${base}/state`),
        fetchEvents: (after) => api("GET", `${base}/events?after=${after}`),
        onEvent: apply, onClock: syncClock, onResync: accept,
        onStatus: (s) => { onStatus?.(s); if (s === "online") scheduleRefresh(0); },
      });
      addEventListener("online", () => scheduleRefresh(0));
      document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") scheduleRefresh(0); });
      return snap;
    },
    refresh,
    // Ação do jogador. O action_id fica guardado até haver resposta: se a rede falhar, o reenvio é idempotente.
    async act(type, amount) {
      if (!pendingAction || pendingAction.type !== type || pendingAction.amount !== amount) pendingAction = { id: newClientId(), type, amount };
      const body = { action_id: pendingAction.id, type };
      if (amount != null) body.amount = Math.round(amount);
      try {
        const res = await api("POST", `${base}/action`, body, { idempotent: true });
        pendingAction = null;
        if (isSnap(res)) accept(res); else scheduleRefresh(0);
        return res;
      } catch (err) {
        if (err.status && err.status < 500 && err.status !== 429 && err.status !== 408) pendingAction = null; // recusada de vez
        throw err;
      }
    },
    async sit(seat, buyIn) { const r = await api("POST", `${base}/sit`, { seat, buy_in: buyIn }); if (isSnap(r)) accept(r); else scheduleRefresh(0); return r; },
    async leave() { const r = await api("POST", `${base}/leave`, {}); scheduleRefresh(0); return r; },
    async back() { const r = await api("POST", `${base}/back`, {}); if (isSnap(r)) accept(r); else scheduleRefresh(0); return r; },
    destroy() { destroyed = true; clearTimeout(refreshTimer); sock?.close(); },
  };
}
