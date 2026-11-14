// Sessão do utilizador: me, login, logout, join, mudar palavra-passe; guarda o utilizador atual em memória.
import { api, setCsrf, ApiError } from "./api.js";

let user = null;
export const currentUser = () => user;

function remember(data) {
  user = data.user;
  setCsrf(data.csrf_token);
  return user;
}

export async function loadMe() {
  try {
    return remember(await api("GET", "/api/me"));
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return null;
    throw err;
  }
}

export const login = async (username, password) => remember(await api("POST", "/api/auth/login", { username, password }));
export const join = async (payload) => remember(await api("POST", "/api/auth/join", payload));
export const changePassword = async (current_password, new_password) =>
  remember(await api("POST", "/api/auth/change-password", { current_password, new_password }));

export async function logout() {
  await api("POST", "/api/auth/logout");
  user = null;
  setCsrf(null);
}

export async function savePreferences(prefs) {
  const data = await api("PATCH", "/api/me/preferences", prefs);
  user = data.user;
  return user;
}

// Para onde ir depois de autenticado
export function homeFor(u) {
  if (u.must_change_password) return "/pages/password/password.html";
  return u.role === "teacher" ? "/pages/admin/admin.html" : "/pages/home/home.html";
}
