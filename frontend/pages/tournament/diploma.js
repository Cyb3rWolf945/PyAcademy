// Diploma em PNG, gerado no cliente com <canvas> em estilo pixel: nome, torneio, posição, data (idioma atual).
import { t, getLocale } from "../../services/i18n.js";
import { pick } from "../challenge/lib.js";

const W = 1200, H = 850, PX = 8;

const cssVar = (name, fallback) => getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;

// Família da fonte pixel, se estiver carregada (classe font-pixel do design); senão, monoespaçada
function pixelFont() {
  const probe = document.createElement("span");
  probe.className = "font-pixel sr-only";
  document.body.append(probe);
  const fam = getComputedStyle(probe).fontFamily;
  probe.remove();
  return fam || "monospace";
}

function fit(ctx, text, maxWidth, size, family) {
  let s = size;
  do { ctx.font = `${s}px ${family}`; s -= 2; } while (ctx.measureText(text).width > maxWidth && s > 16);
}

// drawDiploma({name, tournament, rank, points, config}) -> Promise<HTMLCanvasElement>
export async function drawDiploma({ name, tournament, rank, points, config, rankText: rankOverride, gold = false }) {
  try { await document.fonts?.ready; } catch (_) { /* sem suporte */ }
  const family = pixelFont();
  const c = document.createElement("canvas");
  c.width = W; c.height = H;
  const ctx = c.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  const bg = cssVar("--c-bg", "#1b2a1f"), surface = cssVar("--c-surface", "#26392b");
  const accent = cssVar("--c-accent", "#8bd450"), text = cssVar("--c-text", "#eaf3de"), muted = cssVar("--c-muted", "#a3b8a0");
  const goldC = cssVar("--c-gold", "#f2c94c");

  ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);
  // moldura em degraus
  ctx.fillStyle = accent; ctx.fillRect(PX * 3, PX * 3, W - PX * 6, H - PX * 6);
  ctx.fillStyle = surface; ctx.fillRect(PX * 4, PX * 4, W - PX * 8, H - PX * 8);
  ctx.fillStyle = goldC;
  for (const [x, y] of [[PX * 6, PX * 6], [W - PX * 10, PX * 6], [PX * 6, H - PX * 10], [W - PX * 10, H - PX * 10]]) ctx.fillRect(x, y, PX * 4, PX * 4);

  // emblema UPT (pixel art) no canto e nome da universidade em baixo
  try {
    const logo = await new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = rej; i.src = "/assets/sprites/icons/logo-64.png"; });
    ctx.drawImage(logo, PX * 9, PX * 9, 128, 128);
  } catch (_) { /* sem logótipo, o diploma continua válido */ }
  ctx.textAlign = "center"; ctx.textBaseline = "middle";
  const line = (txt, y, size, color, maxW = W - 220) => { fit(ctx, txt, maxW, size, family); ctx.fillStyle = color; ctx.fillText(txt, W / 2, y); };
  const title = pick(config?.diploma_title) || t("tournament.diploma_default_title");
  line("PYARENA", 140, 44, accent);
  line(title.toUpperCase(), 230, 56, goldC);
  line(t("tournament.diploma_certifies"), 330, 30, muted);
  line(name, 430, 72, text);
  line(t("tournament.diploma_completed", { name: tournament }), 530, 34, text);
  const rankText = rankOverride || t("tournament.diploma_rank", { rank, points });
  line(rankText, 630, 44, gold || rank <= 3 ? goldC : accent);
  const date = new Date().toLocaleDateString(getLocale() === "en" ? "en-GB" : "pt-PT", { day: "numeric", month: "long", year: "numeric" });
  line(date, 740, 28, muted);
  line(t("brand.university"), 800, 24, muted);
  return c;
}

export function downloadCanvas(canvas, filename) {
  canvas.toBlob((blob) => {
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename;
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  }, "image/png");
}
