// Armazenamento local resiliente: rascunhos de código (debounce 500 ms) e fila offline de submissões com reenvio automático.
// Tudo em localStorage dentro de try/catch (modo privado ou quota cheia nunca podem partir a página).
import { api, ApiError } from "./api.js";

const DRAFT_PREFIX = "pyarena.draft.";
const QUEUE_KEY = "pyarena.queue";

function read(key) { try { return localStorage.getItem(key); } catch (_) { return null; } }
function write(key, value) { try { localStorage.setItem(key, value); return true; } catch (_) { return false; } }
function drop(key) { try { localStorage.removeItem(key); } catch (_) { /* ignora */ } }

// ---------- Rascunhos ----------
export const draftKey = (tournamentId, roundIdx, slug) => `${tournamentId ?? "free"}:${roundIdx ?? "-"}:${slug}`;
export const loadDraft = (key) => read(DRAFT_PREFIX + key);
export const clearDraft = (key) => drop(DRAFT_PREFIX + key);

const timers = new Map();
const pending = new Map();

// Guarda o rascunho 500 ms depois da última tecla (várias teclas = uma só escrita)
export function saveDraft(key, text) {
  pending.set(key, text);
  clearTimeout(timers.get(key));
  timers.set(key, setTimeout(() => flushDraft(key), 500));
}

export function flushDraft(key) {
  clearTimeout(timers.get(key));
  timers.delete(key);
  if (!pending.has(key)) return;
  write(DRAFT_PREFIX + key, pending.get(key));
  pending.delete(key);
}

// Ao esconder/fechar o separador, grava já tudo o que estiver pendente
function flushAll() { for (const k of [...pending.keys()]) flushDraft(k); }
addEventListener("pagehide", flushAll);
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") flushAll(); });

// ---------- Fila offline de submissões ----------
const listeners = new Set();
let flushing = false;
let loopStarted = false;

export const queuedSubmissions = () => {
  try { const q = JSON.parse(read(QUEUE_KEY) || "[]"); return Array.isArray(q) ? q : []; } catch (_) { return []; }
};
const saveQueue = (q) => { write(QUEUE_KEY, JSON.stringify(q)); notify({ type: "queue", count: q.length }); };
function notify(ev) { for (const fn of listeners) { try { fn(ev); } catch (_) { /* um ouvinte mau não pára os outros */ } } }

// Ouvinte de eventos da fila: {type:"queue", count} | {type:"sent", client_id, id} | {type:"failed", client_id, error}
export function onQueueEvent(fn) { listeners.add(fn); return () => listeners.delete(fn); }

export function newClientId() {
  if (crypto.randomUUID) return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40; b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

// Erros que não vale a pena repetir (o servidor recusou o pedido de vez)
const retryable = (err) => !(err instanceof ApiError) || err.status === 0 || err.status === 429 || err.status === 408 || err.status >= 500;

// Envia uma submissão. O client_id é gerado e guardado ANTES de enviar: se a rede falhar, fica na fila e
// é reenviada sozinha (o servidor é idempotente pelo client_id). Resolve {id} ou {queued:true, client_id}.
export async function submitWithQueue(payload) {
  const item = { ...payload, client_id: payload.client_id || newClientId() };
  saveQueue([...queuedSubmissions().filter((i) => i.client_id !== item.client_id), item]);
  startQueueLoop();
  try {
    const res = await api("POST", "/api/submissions", item, { idempotent: true });
    removeItem(item.client_id);
    return { id: res.id, client_id: item.client_id, status: res.status };
  } catch (err) {
    if (retryable(err)) return { queued: true, client_id: item.client_id };
    removeItem(item.client_id);
    throw err;
  }
}

function removeItem(clientId) { saveQueue(queuedSubmissions().filter((i) => i.client_id !== clientId)); }

// Tenta reenviar tudo o que está na fila (uma submissão de cada vez, por ordem)
export async function flushQueue() {
  if (flushing) return;
  flushing = true;
  try {
    for (const item of queuedSubmissions()) {
      try {
        const res = await api("POST", "/api/submissions", item, { idempotent: true });
        removeItem(item.client_id);
        notify({ type: "sent", client_id: item.client_id, id: res.id });
      } catch (err) {
        if (retryable(err)) break; // sem rede ou limite de pedidos: tenta mais tarde
        removeItem(item.client_id);
        notify({ type: "failed", client_id: item.client_id, error: err });
      }
    }
  } finally { flushing = false; }
}

export function startQueueLoop() {
  if (loopStarted) return;
  loopStarted = true;
  addEventListener("online", flushQueue);
  setInterval(() => { if (queuedSubmissions().length) flushQueue(); }, 8000);
}
