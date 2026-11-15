"""Gerador dos sprites e texturas pixel art do PyArena (tudo original, desenhado por código).

Como correr (contentor descartável, a VM só tem Docker):
  docker run --rm -v "$PWD/frontend:/w" -w /w python:3.12-slim sh -c "pip install -q pillow && python assets/gen_assets.py"

Escreve (e podemos regenerar à vontade):
  assets/sprites/icons/*.png     ícones 16x16 (logo, modos, moeda, coração, estrela, taça, paleta, professor)
  assets/sprites/ranks/*.png     emblemas de rank provisórios (bronze ... diamante)
  assets/sprites/ui/*.png        texturas de "dither" e "scanlines"
  assets/sprites/themes/<t>/     bg.png (tile 16x16) e scene.png (cartaz 160x90, reserva 2D das cenas 3D)
  assets/icons/*.png             favicon e ícones PWA
As cores dos temas são lidas de styles/themes/<tema>.css para não haver duplicação.
"""
import random
import re
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
THEMES = ["floresta", "masmorra", "oceano", "deserto", "neve", "noite"]

PAL = {
    ".": None, "K": "#1b1424", "W": "#ffffff", "w": "#d5dde8", "g": "#8a97ab", "G": "#566079",
    "Y": "#ffd23f", "y": "#d9971a", "O": "#ff8a2b", "R": "#e8484f", "r": "#a62a3c", "P": "#ff9ec0",
    "B": "#3f8cff", "b": "#2559b8", "C": "#52e3ee", "c": "#25a8b8", "N": "#4fcf5e", "n": "#2b8f40",
    "M": "#9a6236", "m": "#5e3a20", "S": "#f6cda3", "V": "#9a6bff", "v": "#5f35b8", "L": "#bfe5ff",
}


def rgba(h, a=255):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def mix(a, b, t):
    ca, cb = rgba(a), rgba(b)
    return "#%02x%02x%02x" % tuple(round(ca[i] * (1 - t) + cb[i] * t) for i in range(3))


def pic(rows, name=""):
    assert len(rows) == 16, f"{name}: {len(rows)} linhas"
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        assert len(row) == 16, f"{name}: linha {y} tem {len(row)} colunas"
        for x, ch in enumerate(row):
            if PAL[ch]:
                im.putpixel((x, y), rgba(PAL[ch]))
    return im


def outline(im, color="K"):
    """Contorno de 1 px escuro à volta de tudo o que não é transparente (cabe numa grelha 16x16 com margem)."""
    src = im.copy()
    px, out = src.load(), im.load()
    for y in range(16):
        for x in range(16):
            if px[x, y][3] == 0:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < 16 and 0 <= ny < 16 and px[nx, ny][3] and px[nx, ny] != rgba(PAL[color]):
                        out[x, y] = rgba(PAL[color])
                        break
    return im


def canvas():
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def dots(d, pts, color):
    for x, y in pts:
        d.point((x, y), fill=rgba(PAL[color]))


# ---------- sprites desenhados à mão (ASCII 16x16) ----------
HEART = [
    "................", "................", "..KKKK....KKKK..", ".KRRRRK..KRRRRK.", "KRRWWRRKKRRRRRRK", "KRRWRRRRRRRRRRRK",
    "KRRRRRRRRRRRRRrK", "KRRRRRRRRRRRRRrK", ".KRRRRRRRRRRRrK.", "..KRRRRRRRRRrK..", "...KRRRRRRRrK...",
    "....KRRRRRrK....", ".....KRRRrK.....", "......KRrK......", ".......KK.......", "................"]
STAR = [
    "................", ".......KK.......", "......KYYK......", "......KYYK......", ".....KYWYYK.....", "KKKKKKYWYYKKKKKK",
    "KYYYYYYYYYYYYYYK", ".KYYYYYYYYYYYYK.", "..KYYYYYYYYYYK..", "...KYYYYYYYYK...", "...KYYYYYYYyK...",
    "..KYYYyKKyYYyK..", "..KYYyK..KyYyK..", ".KYYyK....KyYyK.", ".KyyK......KyyK.", "..KK........KK.."]
COIN = [
    "................", ".....KKKKKK.....", "...KKYYYYYYKK...", "..KYYWWYYYYYyK..", ".KYYWYYYYYYYyyK.", ".KYWYYYyyYYYYyK.",
    "KYYYYYyYYyYYYyyK", "KYYYYYyYYyYYYyyK", "KYYYYYyYYyYYYyyK", "KYYYYYyYYyYYYyyK", ".KYYYYYyyYYYYyK.",
    ".KYYYYYYYYYYyyK.", "..KyYYYYYYYyyK..", "...KKyyyyyyKK...", ".....KKKKKK.....", "................"]
TROPHY = [
    "................", "..KKKKKKKKKKKK..", "KKKYYYYYYYYYYKKK", "KYKYWWYYYYYYYKYK", "KYKYWYYYYYYYyKYK", "KYKYWYYYYYYYyKYK",
    ".KKYYYYYYYYYyKK.", "...KYYYYYYYYyK..", "....KYYYYYYyK...", ".....KKYYyKK....", ".......KyyK.....",
    ".......KyyK.....", "......KKyyKK....", ".....KYYYYYYK...", ".....KKKKKKKK...", "................"]


def sword(im, flip=False):
    d = ImageDraw.Draw(im)
    f = (lambda x: 15 - x) if flip else (lambda x: x)
    for i in range(9):  # lâmina diagonal com 2 px de largura
        d.point((f(13 - i), 2 + i), fill=rgba(PAL["w"]))
        d.point((f(12 - i), 2 + i), fill=rgba(PAL["W"]))
    d.point((f(13), 1), fill=rgba(PAL["W"]))
    for i in range(5):  # guarda
        d.point((f(3 + i), 6 + i), fill=rgba(PAL["Y"]))
        d.point((f(4 + i), 6 + i), fill=rgba(PAL["y"]))
    d.line([(f(4), 10), (f(2), 12)], fill=rgba(PAL["M"]))
    d.point((f(3), 11), fill=rgba(PAL["m"]))
    d.point((f(1), 13), fill=rgba(PAL["Y"]))
    return im


def shield(fill, shade, border, gem=None):
    im, d = canvas()
    widths = [6, 6, 6, 6, 6, 6, 5, 5, 4, 3, 2, 1]
    for i, w in enumerate(widths):
        y = 2 + i
        for x in range(8 - w, 8 + w):
            c = fill if x < 8 else shade
            if x in (8 - w, 7 + w) or i == 0:
                c = border
            d.point((x, y), fill=rgba(c))
    if gem:
        for x, y in ((8, 5), (7, 6), (8, 6), (9, 6), (6, 7), (7, 7), (8, 7), (9, 7), (10, 7), (7, 8), (8, 8), (9, 8), (8, 9)):
            d.point((x, y), fill=rgba(gem))
        d.point((7, 6), fill=rgba("#ffffff"))
    return outline(im)


def build_icons():
    out = ASSETS / "sprites/icons"
    out.mkdir(parents=True, exist_ok=True)
    icons = {}
    icons["heart"] = pic(HEART, "heart")
    icons["star"] = pic(STAR, "star")
    icons["coin"] = pic(COIN, "coin")
    icons["trophy"] = pic(TROPHY, "trophy")
    icons["tournament"] = icons["trophy"].copy()

    # logo: escudo ciano com um "P" branco e borda dourada
    im, d = canvas()
    widths = [7, 7, 7, 7, 7, 7, 6, 6, 5, 4, 3, 2, 1]
    for i, w in enumerate(widths):
        y = 1 + i
        for x in range(8 - w, 8 + w):
            c = PAL["C"] if x < 8 else PAL["c"]
            if x in (8 - w, 7 + w) or i == 0:
                c = PAL["Y"]
            d.point((x, y), fill=rgba(c))
    for (x, y) in [(5, 3), (6, 3), (7, 3), (8, 3), (5, 4), (9, 4), (5, 5), (9, 5), (5, 6), (6, 6), (7, 6), (8, 6), (5, 7), (5, 8), (5, 9)]:
        d.point((x + 1, y + 0), fill=rgba(PAL["W"]))
    icons["logo"] = outline(im)

    # mundo: globo com continentes
    im, d = canvas()
    d.ellipse((1, 1, 14, 14), fill=rgba(PAL["B"]))
    d.ellipse((1, 1, 14, 14), outline=rgba(PAL["b"]))
    for r in ((4, 3, 7, 5), (3, 6, 5, 8), (9, 7, 12, 10), (7, 11, 9, 12), (10, 4, 12, 5)):
        d.rectangle(r, fill=rgba(PAL["N"]))
    dots(d, [(4, 6), (11, 6), (9, 10)], "n")
    dots(d, [(4, 3), (3, 4), (5, 2)], "W")
    icons["world"] = outline(im)

    # arena (espada) e duelo (duas espadas cruzadas)
    im, _ = canvas()
    icons["arena"] = outline(sword(im))
    im, _ = canvas()
    sword(im)
    sword(im, flip=True)
    icons["duel"] = outline(im)

    # ranking: pódio
    im, d = canvas()
    d.rectangle((1, 8, 5, 14), fill=rgba(PAL["g"]))
    d.rectangle((6, 5, 10, 14), fill=rgba(PAL["Y"]))
    d.rectangle((11, 10, 14, 14), fill=rgba(PAL["O"]))
    d.rectangle((6, 5, 10, 5), fill=rgba(PAL["W"]))
    d.rectangle((1, 8, 5, 8), fill=rgba(PAL["W"]))
    d.rectangle((11, 10, 14, 10), fill=rgba("#ffd0a0"))
    dots(d, [(8, 2), (7, 3), (8, 3), (9, 3), (8, 4)], "R")
    dots(d, [(3, 10), (8, 8), (12, 12)], "K")
    icons["ranking"] = outline(im)

    # perfil: cabeça + corpo
    im, d = canvas()
    d.rectangle((5, 2, 10, 8), fill=rgba(PAL["S"]))
    d.rectangle((5, 2, 10, 3), fill=rgba(PAL["m"]))
    d.rectangle((4, 3, 4, 6), fill=rgba(PAL["m"]))
    d.rectangle((11, 3, 11, 6), fill=rgba(PAL["m"]))
    dots(d, [(6, 5), (9, 5)], "K")
    dots(d, [(7, 7), (8, 7)], "R")
    d.rectangle((3, 10, 12, 14), fill=rgba(PAL["B"]))
    d.rectangle((6, 9, 9, 9), fill=rgba(PAL["S"]))
    d.rectangle((3, 10, 12, 10), fill=rgba(PAL["L"]))
    icons["profile"] = outline(im)

    # professor: quadro verde com giz
    im, d = canvas()
    d.rectangle((1, 2, 14, 11), fill=rgba(PAL["m"]))
    d.rectangle((2, 3, 13, 10), fill=rgba(PAL["n"]))
    dots(d, [(4, 5), (5, 5), (6, 5), (7, 5), (4, 7), (5, 7), (8, 7), (9, 7), (10, 7), (11, 5)], "W")
    d.rectangle((3, 12, 12, 13), fill=rgba(PAL["M"]))
    dots(d, [(10, 12)], "w")
    icons["teacher"] = outline(im)

    # paleta de cores
    im, d = canvas()
    d.ellipse((1, 2, 14, 13), fill=rgba(PAL["M"]))
    d.ellipse((1, 2, 14, 13), outline=rgba(PAL["m"]))
    d.rectangle((10, 9, 12, 11), fill=rgba(PAL["K"]))
    for (x, y), c in zip([(4, 5), (7, 4), (10, 5), (4, 8)], "RYNB"):
        d.rectangle((x, y, x + 1, y + 1), fill=rgba(PAL[c]))
    icons["palette"] = outline(im)

    for name, img in icons.items():
        img.save(out / f"{name}.png")

    # emblemas de rank (provisórios, mesma forma, cor muda)
    rk = ASSETS / "sprites/ranks"
    rk.mkdir(parents=True, exist_ok=True)
    specs = {
        "bronze": ("#d98a4e", "#a8612c", "#7a431c", "#ffd0a0"),
        "silver": ("#e3e9f2", "#a9b4c7", "#7d899e", "#ffffff"),
        "gold": ("#ffd23f", "#d9971a", "#a8700e", "#fff2a8"),
        "platinum": ("#8fe8d8", "#4fbfae", "#2d8c7f", "#e8fffb"),
        "diamond": ("#8ec3ff", "#4a86e0", "#2a56a8", "#ffffff"),
    }
    for name, (f, s, b, g) in specs.items():
        shield(f, s, b, g).save(rk / f"{name}.png")
    return icons


# ---------- texturas de interface ----------
def build_ui():
    out = ASSETS / "sprites/ui"
    out.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGBA", (4, 4), (0, 0, 0, 0))  # dither em xadrez 50%
    for y in range(4):
        for x in range(4):
            if (x + y) % 2 == 0:
                im.putpixel((x, y), (0, 0, 0, 38))
    im.save(out / "dither.png")
    im = Image.new("RGBA", (1, 4), (0, 0, 0, 0))  # linha de scanline a cada 4 px
    im.putpixel((0, 3), (0, 0, 0, 46))
    im.save(out / "scanlines.png")


# ---------- temas: tile de fundo e cartaz 2D ----------
def read_theme(name):
    css = (ROOT / "styles/themes" / f"{name}.css").read_text()
    return {k: v for k, v in re.findall(r"--c-([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})", css)}


BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]


def tile(p, seed):
    rnd = random.Random(seed)
    im = Image.new("RGBA", (16, 16), rgba(p["bg"]))
    for _ in range(26):
        x, y = rnd.randrange(16), rnd.randrange(16)
        c = mix(p["bg"], p["text"], 0.07) if rnd.random() < 0.5 else mix(p["bg"], p["border"], 0.22)
        im.putpixel((x, y), rgba(c))
    for _ in range(4):  # pequenos "tufos" de 2 px, na cor da superfície
        x, y = rnd.randrange(15), rnd.randrange(16)
        for dx in (0, 1):
            im.putpixel((x + dx, y), rgba(mix(p["bg"], p["surface-3"], 0.5)))
    return im


ISLAND = {  # topo, lado, fundo da ilha flutuante por tema
    "floresta": ("#6fcf4a", "#7a5230", "#4a3220"),
    "masmorra": ("#7d7a93", "#56536c", "#34324a"),
    "oceano": ("#f2dca0", "#d2b070", "#a07e48"),
    "deserto": ("#f0c070", "#d49a50", "#a8703a"),
    "neve": ("#ffffff", "#bcd4ec", "#7f9cc0"),
    "noite": ("#3a3a7a", "#26265a", "#16163a"),
}


def scene(name, p):
    W, H = 160, 90
    im = Image.new("RGBA", (W, H), rgba(p["sky-1"]))
    px = im.load()
    s1, s2 = p["sky-1"], p["sky-2"]
    for y in range(H):  # céu em bandas com dither de Bayer
        t = y / (H - 1) * 7
        base, frac = int(t), t - int(t)
        for x in range(W):
            lvl = base + (1 if frac * 16 > BAYER[y % 4][x % 4] else 0)
            px[x, y] = rgba(mix(s1, s2, min(1, lvl / 7)))
    d = ImageDraw.Draw(im)
    rnd = random.Random(name)
    top, side, deep = ISLAND[name]
    # astro
    if name == "noite":
        for _ in range(60):
            d.point((rnd.randrange(W), rnd.randrange(55)), fill=rgba("#ffffff" if rnd.random() < .6 else "#9aa0ff"))
        d.ellipse((118, 10, 134, 26), fill=rgba("#fff6c8"))
        d.ellipse((124, 8, 138, 22), fill=rgba(mix(p["sky-1"], p["sky-2"], .12)))
    else:
        c = {"masmorra": "#c9b6ff", "neve": "#fff7d6", "oceano": "#fff2b0"}.get(name, "#fff2a8")
        d.ellipse((120, 10, 136, 26), fill=rgba(c))
    # nuvens
    for cx, cy in ((22, 18), (70, 10), (140, 40), (30, 50)):
        if name == "noite":
            continue
        cc = "#ffffff" if name not in ("masmorra",) else "#8a7aa8"
        for dx, dy, w in ((0, 0, 14), (4, -3, 9), (-3, 2, 8)):
            d.rectangle((cx + dx, cy + dy, cx + dx + w, cy + dy + 3), fill=rgba(cc))
    if name == "oceano":
        d.rectangle((0, 62, W, H), fill=rgba("#1f7fc0"))
        for y in range(62, H, 4):
            for x in range((y // 4) % 2 * 3, W, 8):
                d.rectangle((x, y, x + 3, y), fill=rgba("#7fd0f0"))
    # ilha: topo plano + base em cone invertido com degraus
    cx, ty = 80, 52
    for i in range(0, 30):
        half = max(2, 44 - int(i * 1.45))
        col = side if i < 6 else deep
        d.rectangle((cx - half, ty + i, cx + half, ty + i), fill=rgba(col))
    d.rectangle((cx - 44, ty - 3, cx + 44, ty), fill=rgba(top))
    d.rectangle((cx - 44, ty, cx + 44, ty + 2), fill=rgba(mix(top, side, .5)))
    # decoração por bioma
    def tri(x, by, h, w, c):
        for i in range(h):
            hw = int(w * (i + 1) / h / 2)
            d.rectangle((x - hw, by - h + i + 1, x + hw, by - h + i + 1), fill=rgba(c))

    if name == "floresta":
        for x, h in ((40, 16), (52, 12), (104, 17), (118, 12), (66, 9)):
            d.rectangle((x - 1, ty - 4, x, ty - 1), fill=rgba("#6b4423"))
            tri(x, ty - 3, h, 11, "#2e8f3a"); tri(x, ty - 3 - h // 3, h - 3, 8, "#45b04c")
        d.rectangle((80, ty - 8, 92, ty - 1), fill=rgba("#e8d8b8")); tri(86, ty - 8, 6, 16, "#c8503c")
    elif name == "masmorra":
        for x, h in ((46, 24), (112, 30)):
            d.rectangle((x - 6, ty - h, x + 6, ty - 1), fill=rgba("#9a97b4"))
            for k in range(-6, 7, 4):
                d.rectangle((x + k, ty - h - 3, x + k + 1, ty - h), fill=rgba("#9a97b4"))
            d.rectangle((x - 1, ty - h + 6, x + 1, ty - h + 9), fill=rgba("#ffc94d"))
        d.rectangle((78, ty - 14, 98, ty - 1), fill=rgba("#6c698a")); d.rectangle((85, ty - 8, 91, ty - 1), fill=rgba("#16141f"))
        d.rectangle((60, ty - 5, 61, ty - 3), fill=rgba("#ff9a3c")); d.rectangle((70, ty - 5, 71, ty - 3), fill=rgba("#ff9a3c"))
    elif name == "oceano":
        d.rectangle((78, ty - 14, 80, ty - 1), fill=rgba("#8a5a33"))
        for dx, dy in ((-8, -13), (-4, -16), (0, -17), (5, -16), (9, -13)):
            d.rectangle((79 + dx, ty + dy, 79 + dx + 6, ty + dy + 2), fill=rgba("#3fb34a"))
        d.rectangle((118, 66, 134, 69), fill=rgba("#8a5a33")); tri(126, 66, 12, 9, "#ffffff")
        d.rectangle((30, 72, 44, 74), fill=rgba("#c8503c")); tri(37, 72, 9, 7, "#fff3d0")
    elif name == "deserto":
        for k in range(-40, 41, 2):
            hh = int(5 + 4 * __import__("math").sin(k / 7))
            d.rectangle((cx + k, ty - hh, cx + k + 1, ty - 1), fill=rgba("#f4cf86"))
        tri(112, ty - 3, 18, 26, "#d9a24e")
        for x, h in ((48, 12), (64, 8)):
            d.rectangle((x, ty - h - 3, x + 2, ty - 3), fill=rgba("#2e8f3a")); d.rectangle((x - 3, ty - h + 1, x - 2, ty - h + 4), fill=rgba("#2e8f3a")); d.rectangle((x + 5, ty - h - 1, x + 6, ty - h + 3), fill=rgba("#2e8f3a"))
    elif name == "neve":
        for x, h, w in ((48, 28, 30), (86, 36, 38), (116, 22, 24)):
            tri(x, ty - 1, h, w, "#c8dcf2"); tri(x, ty - 1 - h + h // 3, h // 3 + 2, w // 3 + 2, "#ffffff")
        for x in (64, 100, 70):
            tri(x, ty - 1, 12, 8, "#3c7f6a"); tri(x, ty - 7, 5, 6, "#ffffff")
    elif name == "noite":
        for x, h, c in ((48, 18, "#7af0ff"), (70, 12, "#ff7ad9"), (100, 22, "#ffe34d"), (118, 13, "#7af0ff")):
            cy = ty - 8 - h // 2
            for dy in range(-h // 2, h // 2 + 1):
                w = max(0, (h // 2 - abs(dy)) // 2)
                d.rectangle((x - w, cy + dy, x + w, cy + dy), fill=rgba(c))
            d.rectangle((x - 1, cy - h // 4, x - 1, cy - h // 4 + 1), fill=rgba("#ffffff"))
    return im


def build_themes():
    for i, name in enumerate(THEMES):
        p = read_theme(name)
        out = ASSETS / "sprites/themes" / name
        out.mkdir(parents=True, exist_ok=True)
        tile(p, i).save(out / "bg.png")
        scene(name, p).save(out / "scene.png")


# ---------- favicon e ícones PWA ----------
def build_pwa(logo):
    out = ASSETS / "icons"
    out.mkdir(parents=True, exist_ok=True)
    bgc = rgba("#16241a")

    def icon(size, scale, bg=True):
        im = Image.new("RGBA", (size, size), bgc if bg else (0, 0, 0, 0))
        big = logo.resize((16 * scale, 16 * scale), Image.NEAREST)
        o = (size - 16 * scale) // 2
        im.alpha_composite(big, (o, o))
        return im

    icon(32, 2, bg=False).save(out / "favicon-32.png")
    icon(180, 10).save(out / "apple-touch-icon.png")
    icon(192, 10).save(out / "icon-192.png")
    icon(512, 28).save(out / "icon-512.png")
    icon(512, 24).save(out / "icon-maskable-512.png")  # zona segura de 80%


if __name__ == "__main__":
    ic = build_icons()
    build_ui()
    build_themes()
    build_pwa(ic["logo"])
    print("ok")
