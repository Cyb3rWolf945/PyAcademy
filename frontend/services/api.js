// Cliente da API: JSON, cookies de sessão, CSRF automático, retry com backoff e erros como chaves i18n.
import { t } from "./i18n.js";

let csrfToken = null;
export const setCsrf = (token) => { csrfToken = token; };
export const csrf = () => csrfToken; // para pedidos que não são JSON (ex.: upload de um PDF)

export class ApiError extends Error {
  constructor(status, key) {
    super(key);
    this.status = status;
    this.key = key;
  }
}

const IDEMPOTENT = new Set(["GET", "HEAD", "PUT", "DELETE"]);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// opts.idempotent = true permite retry em POST (ex.: submissões com ID gerado no cliente)
export async function api(method, path, body, opts = {}) {
  const retryable = IDEMPOTENT.has(method) || opts.idempotent;
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET" && method !== "HEAD" && csrfToken) headers["X-CSRF-Token"] = csrfToken;

  let lastErr = new ApiError(0, "common.network");
  for (let attempt = 0; attempt < 3; attempt++) {
    if (attempt) await sleep(300 * 2 ** (attempt - 1));
    let res;
    try {
      res = await fetch(path, {
        method, headers, credentials: "same-origin",
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch (_) {
      lastErr = new ApiError(0, "common.network");
      if (retryable) continue;
      throw lastErr;
    }
    if (res.status >= 500 && retryable && attempt < 2) { lastErr = new ApiError(res.status, "common.error"); continue; }
    if (res.ok) return res.headers.get("content-type")?.includes("json") ? res.json() : res;
    let key = "common.error";
    try { key = (await res.json()).error || key; } catch (_) { /* corpo não-JSON */ }
    throw new ApiError(res.status, key);
  }
  throw lastErr;
}

// Texto traduzido para mostrar ao utilizador
export const errorText = (err) => t(err instanceof ApiError ? err.key : "common.error");
