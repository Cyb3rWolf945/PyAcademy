// Ligação em tempo real ao torneio: WebSocket com reconexão (1, 2, 4... até 10 s), replay por seq e,
// se o WebSocket falhar 3 vezes seguidas, polling a /events de 5 em 5 s. Eventos tratados de forma idempotente.
import { api } from "./api.js";

const BACKOFF = [1000, 2000, 4000, 8000, 10000];
const POLL_MS = 5000;
const PING_MS = 15000;
const WS_RETRY_IN_POLLING_MS = 30000;

// connectTournament(id, {onEvent(ev), onStatus(status), onResync(snapshot)}) -> {close(), setLastSeq(n), lastSeq()}
// status: "online" | "reconnecting" | "offline"
export function connectTournament(id, { onEvent, onStatus, onResync, onClock, lastSeq: initialSeq = 0 }) {
  let lastSeq = initialSeq;
  let ws = null;
  let closed = false;
  let failures = 0;
  let status = "";
  let retryTimer = null;
  let pingTimer = null;
  let pollTimer = null;
  let polling = false;
  let wsRetryTimer = null;

  const setStatus = (s) => { if (s !== status) { status = s; onStatus?.(s); } };

  // Entrega um evento uma só vez: seq <= lastSeq é ignorado (replay, reconexão, polling sobreposto)
  function deliver(ev) {
    if (ev.type === "pong") { if (ev.server_now) onClock?.(ev.server_now); return; } // pong não é evento: só acerta o relógio
    if (ev.type === "resync") { resync(); return; }
    if (typeof ev.seq === "number") {
      if (ev.seq <= lastSeq) return;
      lastSeq = ev.seq;
    }
    if (ev.type === "pong" || ev.type === "ping") return;
    onEvent?.(ev);
  }

  async function resync() {
    try {
      const snap = await api("GET", `/api/tournaments/${id}/state`);
      if (typeof snap.last_seq === "number") lastSeq = Math.max(lastSeq, snap.last_seq);
      onResync?.(snap);
    } catch (_) { /* a próxima reconexão ou poll tenta outra vez */ }
  }

  function wsUrl() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${location.host}/ws/tournaments/${id}?last_seq=${lastSeq}`;
  }

  function open() {
    if (closed || ws) return;
    let opened = false;
    try { ws = new WebSocket(wsUrl()); } catch (_) { onFail(); return; }
    const mine = ws;
    mine.onopen = () => {
      opened = true; failures = 0; stopPolling();
      setStatus("online");
      clearInterval(pingTimer);
      pingTimer = setInterval(() => {
        if (mine.readyState === 1) mine.send(JSON.stringify({ type: "ping", last_seq: lastSeq }));
      }, PING_MS);
    };
    mine.onmessage = (m) => {
      let ev;
      try { ev = JSON.parse(m.data); } catch (_) { return; }
      deliver(ev);
    };
    mine.onclose = () => {
      clearInterval(pingTimer);
      if (ws === mine) ws = null;
      if (closed) return;
      if (!opened) failures += 1;
      onFail();
    };
    mine.onerror = () => { /* o onclose trata da reconexão */ };
  }

  function onFail() {
    if (closed) return;
    setStatus(navigator.onLine === false ? "offline" : "reconnecting");
    if (failures >= 3) { startPolling(); return; }
    const wait = BACKOFF[Math.min(failures, BACKOFF.length - 1)];
    clearTimeout(retryTimer);
    retryTimer = setTimeout(open, wait);
  }

  // Polling de reserva: apanha eventos novos; resync=true volta ao snapshot completo
  async function poll() {
    if (closed || !polling) return;
    try {
      const res = await api("GET", `/api/tournaments/${id}/events?after=${lastSeq}`);
      if (res.resync) await resync();
      else for (const ev of res.events || []) deliver(ev);
      setStatus("reconnecting"); // dados a chegar, mas sem tempo real
    } catch (_) { setStatus("offline"); }
    pollTimer = setTimeout(poll, POLL_MS);
  }

  function startPolling() {
    if (polling) return;
    polling = true;
    poll();
    // Mesmo em polling, vai tentando voltar ao WebSocket de tempos a tempos
    wsRetryTimer = setInterval(() => { if (!ws) { failures = 2; open(); } }, WS_RETRY_IN_POLLING_MS);
  }

  function stopPolling() {
    polling = false;
    clearTimeout(pollTimer);
    clearInterval(wsRetryTimer);
  }

  const onNetUp = () => { if (!ws && !closed) { failures = 0; clearTimeout(retryTimer); stopPolling(); open(); } };
  const onNetDown = () => { if (!closed && status === "online") setStatus("offline"); };
  addEventListener("online", onNetUp);
  addEventListener("offline", onNetDown);

  open();
  return {
    lastSeq: () => lastSeq,
    setLastSeq: (n) => { if (typeof n === "number" && n > lastSeq) lastSeq = n; },
    close() {
      closed = true;
      clearTimeout(retryTimer); clearInterval(pingTimer); stopPolling();
      removeEventListener("online", onNetUp);
      removeEventListener("offline", onNetDown);
      try { ws?.close(); } catch (_) { /* ignora */ }
    },
  };
}
