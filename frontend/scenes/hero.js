// Escolhe a cena do herói conforme o tema: "campus" (por omissão) = campus 3D do IPT e hub dos modos; os outros temas
// continuam com a ilha de voxels. Troca sem recarregar a página (themechange). Tudo é carregado depois do primeiro pixel.
// mountHero(el, { theme, lift, onHotspot }) -> { setTheme(theme), focus(id), dispose() }
import { currentUser } from "../services/auth.js";

export async function mountHero(el, { theme, lift = 0, onHotspot } = {}) {
  let cur = null, kind = "", token = 0;
  async function use(name) {
    const want = name === "campus" ? "campus" : "island";
    if (kind === want) { cur?.setTheme?.(name); return; }
    const my = ++token;
    cur?.dispose?.(); cur = null; kind = want;
    const next = want === "campus"
      ? await import("./campus/campus.js").then((m) => m.mountCampus(el, { theme: name, onHotspot, lift, isTeacher: () => currentUser()?.role === "teacher" }))
      : await import("./lobby-island.js").then((m) => m.mountLobby(el, { theme: name, lift }));
    if (my !== token) { next?.dispose?.(); return; }
    cur = next;
  }
  await use(theme);
  return { setTheme: use, focus: (id) => cur?.focus?.(id), dispose() { token++; cur?.dispose?.(); cur = null; kind = ""; } };
}
