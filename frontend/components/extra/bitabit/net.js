// Chamadas à API do Bit a Bit. Se o servidor ainda não tem os endpoints (404/rede), o jogo corre em "modo treino" e não dá pontos.
import { api, ApiError } from "../../../services/api.js";

const BASE = "/api/extra/bitabit";

export async function startGame() {
  try {
    const g = await api("POST", `${BASE}/start`);
    if (g && Number.isFinite(g.seed) && g.game_id != null) return { practice: false, ...g };
  } catch (e) { if (!(e instanceof ApiError)) throw e; }
  const seed = crypto.getRandomValues(new Uint32Array(1))[0];
  return { practice: true, game_id: null, seed, config: {} };
}

// {score, points_awarded, best, today_remaining} ou null se falhar
export async function finishGame(game, answers, score) {
  if (game.practice) return null;
  try { return await api("POST", `${BASE}/${encodeURIComponent(game.game_id)}/finish`, { answers, score }, { idempotent: true }); } catch (_) { return null; }
}

export async function loadTop() {
  try {
    const d = await api("GET", `${BASE}/leaderboard`);
    const list = Array.isArray(d) ? d : d?.entries ?? d?.top ?? d?.items ?? [];
    return list.slice(0, 10).map((e, i) => ({ rank: e.rank ?? i + 1, name: e.display_name ?? e.name ?? "?", score: e.best ?? e.score ?? e.points ?? 0, me: !!(e.is_me ?? e.me) }));
  } catch (_) { return null; }
}

// {today_points, daily_cap, today_remaining, best_score, games_today} ou null
export async function loadMine() {
  try { return await api("GET", `${BASE}/me`); } catch (_) { return null; }
}
