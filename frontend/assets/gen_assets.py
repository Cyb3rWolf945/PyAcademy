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
THEMES = ["campus", "floresta", "masmorra", "oceano", "deserto", "neve", "noite"]

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
        if name in ISLAND:  # o campus usa o cartaz sprites/campus/poster.png (build_campus)
            scene(name, p).save(out / "scene.png")


# ---------- medalhas (ouro, bronze, cobre) 32x32 e 64x64 ----------
DIGITS = {"1": ["010", "110", "010", "010", "111"], "2": ["111", "001", "111", "100", "111"], "3": ["111", "001", "011", "001", "111"]}
MEDALS = {  # nome: (disco, sombra, brilho, dígito)
    "gold": ("#ffd23f", "#d9971a", "#fff3a8", "#7a4a00"),
    "bronze": ("#c4863a", "#8e5a22", "#e8b878", "#3d2208"),
    "copper": ("#d9573b", "#9a3320", "#f59a7e", "#3a0f08"),
}


def medal(n, name):
    disc, shade, hi, ink = MEDALS[name]
    im = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rib, rib2 = rgba("#3f8cff"), rgba("#2559b8")
    for i in range(12):  # fita em V
        d.rectangle((9 + i // 3, i, 14 + i // 3, i), fill=rib)
        d.rectangle((17 - i // 3, i, 22 - i // 3, i), fill=rib2)
    d.ellipse((5, 9, 26, 30), fill=rgba(disc))
    d.ellipse((7, 11, 24, 28), outline=rgba(shade))
    d.rectangle((9, 12, 12, 13), fill=rgba(hi))
    d.rectangle((9, 14, 10, 15), fill=rgba(hi))
    g = DIGITS[str(n)]
    for y, row in enumerate(g):  # dígito 3x5 ampliado 2x, centrado no disco
        for x, c in enumerate(row):
            if c == "1":
                d.rectangle((13 + x * 2, 14 + y * 2, 14 + x * 2, 15 + y * 2), fill=rgba(ink))
    # contorno escuro de 1 px
    src, out = im.copy(), im.load()
    px = src.load()
    for y in range(32):
        for x in range(32):
            if px[x, y][3] == 0:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < 32 and 0 <= ny < 32 and px[nx, ny][3]:
                        out[x, y] = rgba(PAL["K"])
                        break
    return im


def build_medals():
    out = ASSETS / "sprites/medals"
    out.mkdir(parents=True, exist_ok=True)
    for n, name in enumerate(["gold", "bronze", "copper"], 1):
        m = medal(n, name)
        m.save(out / f"{name}-32.png")
        m.resize((64, 64), Image.NEAREST).save(out / f"{name}-64.png")


# ---------- mais ícones (código, relógio, raio, escudo, coroa, pergaminho, baú, estados) e efeitos ----------
def build_more():
    out = ASSETS / "sprites/icons"
    fx = ASSETS / "sprites/fx"
    fx.mkdir(parents=True, exist_ok=True)
    icons = {}
    # código </>
    im, d = canvas()
    d.rectangle((1, 2, 14, 13), fill=rgba("#2b2440"))
    d.rectangle((1, 2, 14, 3), fill=rgba("#473a73"))
    dots(d, [(5, 6), (4, 7), (3, 8), (4, 9), (5, 10), (10, 6), (11, 7), (12, 8), (11, 9), (10, 10)], "C")
    dots(d, [(8, 5), (8, 6), (7, 8), (7, 9), (7, 10)], "Y")
    icons["code"] = outline(im)
    # relógio
    im, d = canvas()
    d.ellipse((1, 1, 14, 14), fill=rgba(PAL["W"]))
    d.ellipse((1, 1, 14, 14), outline=rgba(PAL["g"]))
    d.line([(8, 8), (8, 4)], fill=rgba(PAL["K"]))
    d.line([(8, 8), (11, 9)], fill=rgba(PAL["R"]))
    dots(d, [(8, 2), (8, 13), (2, 8), (13, 8)], "G")
    icons["clock"] = outline(im)
    # raio
    im, d = canvas()
    d.polygon([(9, 1), (3, 9), (7, 9), (6, 15), (13, 6), (9, 6)], fill=rgba(PAL["Y"]))
    d.line([(9, 2), (5, 8)], fill=rgba(PAL["W"]))
    d.point((12, 6), fill=rgba(PAL["y"]))
    icons["lightning"] = outline(im)
    # escudo azul
    icons["shield"] = shield("#5f9bff", "#2e63c8", "#1d3f8a", "#ffffff")
    # coroa
    im, d = canvas()
    d.polygon([(1, 5), (4, 9), (8, 3), (12, 9), (15, 5), (14, 13), (2, 13)], fill=rgba(PAL["Y"]))
    d.rectangle((2, 12, 13, 13), fill=rgba(PAL["y"]))
    dots(d, [(1, 4), (8, 2), (14, 4)], "R")
    dots(d, [(5, 11), (8, 11), (11, 11)], "R")
    icons["crown"] = outline(im)
    # pergaminho
    im, d = canvas()
    d.rectangle((3, 2, 12, 13), fill=rgba("#f6e2b3"))
    d.rectangle((2, 1, 13, 2), fill=rgba(PAL["M"]))
    d.rectangle((2, 13, 13, 14), fill=rgba(PAL["M"]))
    for y in (5, 7, 9, 11):
        d.line([(5, y), (10, y)], fill=rgba(PAL["m"]))
    icons["scroll"] = outline(im)
    # baú
    im, d = canvas()
    d.rectangle((1, 5, 14, 13), fill=rgba(PAL["M"]))
    d.rectangle((1, 3, 14, 6), fill=rgba("#b87a43"))
    d.rectangle((1, 7, 14, 7), fill=rgba(PAL["m"]))
    d.rectangle((7, 6, 8, 10), fill=rgba(PAL["Y"]))
    d.rectangle((1, 5, 14, 5), fill=rgba(PAL["y"]))
    d.rectangle((1, 12, 14, 13), fill=rgba(PAL["m"]))
    icons["chest"] = outline(im)
    # estados
    im, d = canvas()
    d.rectangle((1, 1, 14, 14), fill=rgba(PAL["N"]))
    d.rectangle((1, 1, 14, 2), fill=rgba("#8cf09a"))
    dots(d, [(4, 8), (5, 9), (6, 10), (7, 9), (8, 8), (9, 7), (10, 6), (11, 5)], "W")
    dots(d, [(4, 9), (5, 10), (6, 11), (7, 10), (8, 9), (9, 8), (10, 7), (11, 6)], "W")
    icons["check"] = outline(im)
    im, d = canvas()
    d.rectangle((1, 1, 14, 14), fill=rgba(PAL["R"]))
    d.rectangle((1, 1, 14, 2), fill=rgba("#ff8a90"))
    for i in range(6):
        dots(d, [(5 + i, 5 + i), (10 - i, 5 + i), (6 + i, 5 + i), (9 - i, 5 + i)], "W")
    icons["cross"] = outline(im)
    im, d = canvas()
    d.rectangle((1, 1, 14, 14), fill=rgba(PAL["B"]))
    d.rectangle((1, 1, 14, 2), fill=rgba("#8cbcff"))
    dots(d, [(8, 4), (7, 7), (8, 7), (8, 8), (8, 9), (8, 10), (7, 11), (8, 11), (9, 11)], "W")
    icons["info"] = outline(im)
    for name, img in icons.items():
        img.save(out / f"{name}.png")
    # nuvens e faísca (efeitos do herói)
    for name, rows in {
        "cloud-a": ["..........WWWW..........", "......WWWWWWWWWW........", "...WWWWWWWWWWWWWWWW.....", ".WWWWWWWWWWWWWWWWWWWW...", "WWWWWWWWWWWWWWWWWWWWWWW.", "wwwwwwwwwwwwwwwwwwwwwwww"],
        "cloud-b": ["....WWW.......", "..WWWWWWW.....", "WWWWWWWWWWWW..", "WWWWWWWWWWWWW.", "wwwwwwwwwwwwww"],
        "sparkle": ["...W....", "...W....", "WWWYWWW.", "...W....", "...W...."],
    }.items():
        w = max(len(r) for r in rows)
        im = Image.new("RGBA", (w, len(rows)), (0, 0, 0, 0))
        for y, r in enumerate(rows):
            for x, ch in enumerate(r):
                if PAL.get(ch):
                    c = rgba(PAL[ch]) if ch != "w" else rgba("#c5d6ea")
                    im.putpixel((x, y), c)
        im.save(fx / f"{name}.png")


# ---------- emblema da Universidade Politécnica de Tomar (UPT) em pixel art ----------
# Entrada: assets/brand/src/upt-logo-original.png (logótipo oficial). Recorta-se só o escudo + ponto, separam-se as 3 formas
# (escudo, ornamento branco, ponto), reduz-se cada uma com média de área + limiar e simetriza-se o ornamento.
# Paleta fixa: verde UPT, branco e verde escuro (contorno de 1 px para ler em qualquer tema). Só ampliações "nearest".
UPT_GREEN, UPT_DARK, UPT_WHITE = "#74bc1f", "#2f5f0c", "#ffffff"


def upt_masks():
    src = Image.open(ASSETS / "brand/src/upt-logo-original.png").convert("RGBA")
    bg = Image.new("RGBA", src.size, (255, 255, 255, 255))
    bg.alpha_composite(src)
    rgb = bg.convert("RGB").crop((30, 79, 97, 169))  # só o emblema (sem o texto)
    w, h = rgb.size
    px = rgb.load()
    notwhite = lambda p: not (p[0] > 225 and p[1] > 225 and p[2] > 225)
    # fundo = branco ligado à margem (preenchimento por inundação); o resto é escudo/ornamento/ponto
    outside = set()
    stack = [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]
    while stack:
        x, y = stack.pop()
        if (x, y) in outside or not (0 <= x < w and 0 <= y < h) or notwhite(px[x, y]):
            continue
        outside.add((x, y))
        stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    shield = Image.new("L", (w, h), 0)
    orn = Image.new("L", (w, h), 0)
    sp, op = shield.load(), orn.load()
    for y in range(h):
        for x in range(w):
            if (x, y) in outside:
                continue
            sp[x, y] = 255
            if px[x, y][0] > 222 and px[x, y][1] > 232 and px[x, y][2] > 215:
                op[x, y] = 255  # quase branco dentro do escudo = ornamento
    from PIL import ImageFilter, ImageChops
    core = shield.filter(ImageFilter.MinFilter(13))  # afasta o ornamento da orla (meios-tons do contorno não contam)
    orn = ImageChops.multiply(orn, core)
    return shield, orn, w, h


def upt_emblem(S):
    """Emblema UPT numa grelha S x S (S=16, 32 ou 64), a verde com contorno escuro."""
    shield, orn, w, h = upt_masks()
    # separa o ponto (parte de baixo, sem ornamento) do escudo
    sp = shield.load()
    rows = [y for y in range(h) if any(sp[x, y] for x in range(w))]
    gap = [y for y in range(rows[0], rows[-1]) if not any(sp[x, y] for x in range(w))]
    cut = gap[0] if gap else h
    box = shield.getbbox()
    scale = (S - 2) / (box[3] - box[1])
    tw, th = max(1, round((box[2] - box[0]) * scale)), max(1, round((box[3] - box[1]) * scale))
    def small(mask, thr, crop=None):
        m = mask.crop(box)
        return m.resize((tw, th), Image.BOX).point(lambda v: 255 if v >= thr else 0)
    sh_top = Image.new("L", shield.size, 0); sh_top.paste(shield.crop((0, 0, w, cut)), (0, 0))
    dot = Image.new("L", shield.size, 0); dot.paste(shield.crop((0, cut, w, h)), (0, cut))
    a_sh, a_dot = small(sh_top, 128), small(dot, 128)
    a_or = small(orn, 90 if S >= 64 else 70)
    # ornamento: só dentro do escudo e simétrico (esquerda/direita e cima/baixo em torno do seu centro)
    ob = a_or.getbbox() if a_sh.getbbox() else None
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ox, oy = (S - tw) // 2, (S - th) // 2
    G, D, W = rgba(UPT_GREEN), rgba(UPT_DARK), rgba(UPT_WHITE)
    shp, dtp, orp = a_sh.load(), a_dot.load(), a_or.load()
    cells = {}
    for y in range(th):
        for x in range(tw):
            if shp[x, y] or dtp[x, y]:
                cells[(x, y)] = G
    if S == 16:  # a 16 px o ornamento é um asterisco 5x5 desenhado à mão, centrado no escudo
        bb = a_sh.crop((0, 0, tw, min(th, int(tw * 1.0) + 1))).getbbox()
        scx, scy = (bb[0] + bb[2]) // 2, (bb[1] + bb[3]) // 2 - 0
        for dx, dy in [(-2, -2), (0, -2), (2, -2), (-1, -1), (0, -1), (1, -1), (-2, 0), (-1, 0), (0, 0), (1, 0), (2, 0), (-1, 1), (0, 1), (1, 1), (-2, 2), (0, 2), (2, 2)]:
            cells[(scx + dx, scy + dy)] = W
    elif ob:
        inside = [(x, y) for (x, y), c in cells.items() if orp[x, y] and shp[x, y]]
        # simetriza em torno do centro horizontal do escudo e do centro vertical do ornamento
        cx = (a_sh.getbbox()[0] + a_sh.getbbox()[2] - 1) / 2
        oys = [y for _, y in inside]
        cy = (min(oys) + max(oys)) / 2 if oys else 0
        sym = set()
        for x, y in inside:
            for X, Y in ((x, y), (round(2 * cx - x), y), (x, round(2 * cy - y)), (round(2 * cx - x), round(2 * cy - y))):
                if shp[X, Y] if 0 <= X < tw and 0 <= Y < th else False:
                    sym.add((X, Y))
        for c in sym:
            cells[c] = W
    for (x, y), c in cells.items():
        out.putpixel((ox + x, oy + y), c)
    # contorno escuro de 1 px à volta de tudo
    o2, px2 = out.copy(), out.load()
    p0 = o2.load()
    for y in range(S):
        for x in range(S):
            if p0[x, y][3] == 0:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < S and 0 <= ny < S and p0[nx, ny][3]:
                        px2[x, y] = D
                        break
    return out


def build_upt():
    out = ASSETS / "sprites/icons"
    imgs = {S: upt_emblem(S) for S in (16, 32, 64)}
    for S, im in imgs.items():
        im.save(out / f"logo-{S}.png")
    imgs[32].save(out / "logo.png")
    return imgs


# ---------- Academia: ícones dos módulos (m0..m7, bug) e selos das peças ----------
def build_academy():
    mod = ASSETS / "sprites/academy"
    mod.mkdir(parents=True, exist_ok=True)
    L, LB, NAVY = "#8cc63f", "#ece9fb", "#1f2a44"  # verde "início/fim", lilás dos blocos, azul das decisões (iguais ao fluxograma)

    def shape(name):
        im, d = canvas()
        if name == "pill":  # Início/Fim
            d.rounded_rectangle((1, 4, 14, 11), radius=3, fill=rgba(L))
            d.rectangle((3, 6, 12, 6), fill=rgba("#c9ec9c"))
        elif name == "para":  # Ler/Escrever (paralelogramo)
            d.polygon([(4, 3), (14, 3), (11, 12), (1, 12)], fill=rgba(LB))
            d.polygon([(4, 3), (14, 3), (11, 12), (1, 12)], outline=rgba("#8f86d6"))
        elif name == "rect":  # Calcular
            d.rectangle((1, 3, 14, 12), fill=rgba(LB), outline=rgba("#8f86d6"))
            d.rectangle((4, 6, 11, 6), fill=rgba("#8f86d6")); d.rectangle((4, 9, 11, 9), fill=rgba("#8f86d6"))
        elif name == "diamond":  # Decisão
            d.polygon([(8, 1), (15, 8), (8, 15), (1, 8)], fill=rgba(NAVY))
            dots(d, [(8, 6), (8, 7), (8, 9)], "W")
        elif name == "loop":  # Ciclo
            d.rectangle((3, 3, 12, 4), fill=rgba("#4f8cff")); d.rectangle((3, 11, 12, 12), fill=rgba("#4f8cff"))
            d.rectangle((11, 3, 12, 12), fill=rgba("#4f8cff")); d.rectangle((3, 3, 4, 12), fill=rgba("#4f8cff"))
            d.polygon([(1, 8), (6, 8), (3, 12)], fill=rgba("#ffd23f"))
        elif name == "func":  # Função f(x)
            d.rectangle((1, 2, 14, 13), fill=rgba("#2b2440"))
            dots(d, [(4, 4), (5, 4), (4, 5), (4, 6), (3, 6), (5, 6), (4, 7), (4, 8), (3, 9)], "C")
            dots(d, [(8, 6), (12, 6), (9, 7), (11, 7), (10, 8), (9, 9), (11, 9), (8, 10), (12, 10)], "Y")
        elif name == "list":  # Lista
            for i in range(3):
                d.rectangle((1 + i * 5, 5, 4 + i * 5, 10), fill=rgba("#ffd23f"), outline=rgba("#d9971a"))
            dots(d, [(2, 7), (7, 7), (12, 7)], "K")
        elif name == "arrows":  # Setas (M1: o fluxo entre blocos)
            d.rectangle((7, 1, 8, 9), fill=rgba("#4a4f5c"))
            d.polygon([(3, 8), (12, 8), (7, 14)], fill=rgba("#4a4f5c"))
            d.rectangle((1, 4, 6, 4), fill=rgba("#8f86d6")); d.polygon([(6, 2), (10, 4), (6, 6)], fill=rgba("#8f86d6"))
        elif name == "lupa":  # Lupa (caça aos bugs)
            d.ellipse((1, 1, 10, 10), fill=rgba("#bfe5ff"), outline=rgba("#6b7a99"))
            d.line([(9, 9), (14, 14)], fill=rgba(PAL["m"]), width=2)
            dots(d, [(3, 3), (4, 3)], "W")
        return outline(im)

    pieces = {"inicio-fim": "pill", "ler-escrever": "para", "calcular": "rect", "decisao": "diamond", "ciclo": "loop", "funcao": "func", "lista": "list", "lupa": "lupa", "setas": "arrows", "processo": "rect"}
    for n, sh in pieces.items():
        shape(sh).save(mod / f"peca-{n}.png")

    def bulb():
        im, d = canvas(); d.ellipse((3, 1, 12, 10), fill=rgba("#ffe56b")); d.rectangle((5, 10, 10, 12), fill=rgba(PAL["g"])); d.rectangle((6, 13, 9, 13), fill=rgba(PAL["G"])); dots(d, [(5, 4), (5, 5)], "W"); return outline(im)
    def flow():
        im, d = canvas(); d.rounded_rectangle((4, 0, 11, 3), radius=1, fill=rgba(L)); d.rectangle((7, 4, 8, 5), fill=rgba(PAL["G"]))
        d.rectangle((3, 6, 12, 9), fill=rgba(LB), outline=rgba("#8f86d6")); d.rectangle((7, 10, 8, 11), fill=rgba(PAL["G"])); d.rounded_rectangle((4, 12, 11, 15), radius=1, fill=rgba(L)); return outline(im)
    def pencil():
        im, d = canvas(); d.polygon([(11, 1), (14, 4), (5, 13), (2, 14), (3, 11)], fill=rgba("#ffd23f")); d.polygon([(11, 1), (14, 4), (12, 6), (9, 3)], fill=rgba(PAL["P"])); d.polygon([(3, 11), (5, 13), (2, 14)], fill=rgba(PAL["S"])); return outline(im)
    def puzzle():
        im, d = canvas(); d.rectangle((1, 5, 10, 14), fill=rgba("#4f8cff")); d.rectangle((5, 3, 7, 5), fill=rgba("#4f8cff")); d.rectangle((10, 8, 12, 10), fill=rgba("#4f8cff")); d.rectangle((9, 1, 14, 6), fill=rgba(PAL["R"])); return outline(im)
    def fork():
        im, d = canvas(); d.polygon([(8, 1), (11, 4), (8, 7), (5, 4)], fill=rgba(NAVY)); d.rectangle((7, 7, 8, 9), fill=rgba(PAL["G"]))
        d.rectangle((3, 9, 12, 9), fill=rgba(PAL["G"])); d.rectangle((3, 9, 3, 11), fill=rgba(PAL["G"])); d.rectangle((12, 9, 12, 11), fill=rgba(PAL["G"]))
        d.rectangle((1, 11, 5, 14), fill=rgba(LB), outline=rgba("#8f86d6")); d.rectangle((10, 11, 14, 14), fill=rgba(LB), outline=rgba("#8f86d6")); return outline(im)
    def gear():
        im, d = canvas(); d.ellipse((3, 3, 12, 12), fill=rgba(PAL["g"])); d.ellipse((6, 6, 9, 9), fill=rgba(PAL["K"]))
        for x, y in ((7, 1), (7, 13), (1, 7), (13, 7), (2, 2), (12, 2), (2, 12), (12, 12)): d.rectangle((x, y, x + 1, y + 1), fill=rgba(PAL["g"]))
        return outline(im)
    def listi():
        im, d = canvas(); d.rectangle((2, 1, 13, 14), fill=rgba("#f6e2b3"))
        for y in (4, 7, 10): d.rectangle((4, y, 5, y), fill=rgba(PAL["R"])); d.rectangle((7, y, 11, y), fill=rgba(PAL["m"]))
        return outline(im)
    def bug():
        im, d = canvas(); d.ellipse((4, 4, 11, 13), fill=rgba(PAL["N"])); d.ellipse((5, 1, 10, 5), fill=rgba(PAL["n"]))
        for y in (6, 9, 12): d.line([(1, y), (4, y)], fill=rgba(PAL["K"])); d.line([(11, y), (14, y)], fill=rgba(PAL["K"]))
        dots(d, [(6, 2), (9, 2), (7, 8), (8, 8)], "W"); return outline(im)
    for n, f in enumerate([bulb, flow, pencil, puzzle, fork, loopi if False else None, gear, listi]):
        pass
    def loopic():
        im, d = canvas(); d.rectangle((3, 2, 13, 3), fill=rgba("#4f8cff")); d.rectangle((12, 2, 13, 9), fill=rgba("#4f8cff")); d.rectangle((3, 12, 13, 13), fill=rgba("#4f8cff")); d.rectangle((2, 6, 3, 13), fill=rgba("#4f8cff"))
        d.polygon([(10, 7), (15, 7), (12, 11)], fill=rgba("#ffd23f")); d.polygon([(0, 8), (5, 8), (2, 4)], fill=rgba("#ffd23f")); return outline(im)
    for name, f in zip(["m0", "m1", "m2", "m3", "m4", "m5", "m6", "m7", "bugs"], [bulb, flow, pencil, puzzle, fork, loopic, gear, listi, bug]):
        f().save(mod / f"{name}.png")


# ---------- campus IPT: cartaz 2D (reserva da cena 3D), desenhado a partir de scenes/campus/layout.json ----------
def paint_campus(L, S):
    import json as _j
    ps = L["poster"]
    k = S / 6
    sky = round(ps["sky"] * k)
    W, H = round(L["size"][0] * S), round(ps["h"] * k)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    d = ImageDraw.Draw(im)
    rnd = random.Random(7)
    X = lambda x: round(x * S)
    zk = ps.get("zk", 1)
    Y = lambda z: sky + round(z * S * zk)
    # céu em bandas com dither
    px = im.load()
    for y in range(sky):
        t = y / max(1, sky - 1) * 6
        base, frac = int(t), t - int(t)
        for x in range(W):
            lvl = base + (1 if frac * 16 > BAYER[y % 4][x % 4] else 0)
            px[x, y] = rgba(mix("#5aa8e8", "#d2e9fb", min(1, lvl / 6)))
    for cx, cy, w in ((30, 8, 22), (130, 14, 16), (250, 6, 24), (300, 20, 14)):
        cx, cy, w = round(cx * k), round(cy * k), round(w * k)
        d.rectangle((cx, cy, cx + w, cy + max(2, 3 * round(k))), fill=rgba("#ffffff"))
        d.rectangle((cx + w // 4, cy - max(1, 2 * round(k)), cx + 3 * w // 4, cy), fill=rgba("#ffffff"))
    d.rectangle((0, sky, W, H), fill=rgba("#7cae47"))
    for _ in range(W * H // 40):
        x, y = rnd.randrange(W), rnd.randrange(sky, H)
        px[x, y] = rgba(rnd.choice(["#6a9d3a", "#8fc255", "#7cae47"]))
    def R(r, col, outline=None):
        x, z, w, dd = r[:4]
        x0, y0 = X(x), Y(z)
        d.rectangle((x0, y0, max(x0, X(x + w) - 1), max(y0, Y(z + dd) - 1)), fill=rgba(col), outline=rgba(outline) if outline else None)
    for r in L["lawns"]: R(r, "#8fc255")
    R(L["field"], "#5ea43b")
    fx, fz, fw, fd = L["field"]
    for i in range(0, int(fd), 2): R([fx, fz + i, fw, 1], "#68ae44")
    d.rectangle((X(fx) + 2, Y(fz) + 2, X(fx + fw) - 3, Y(fz + fd) - 3), outline=rgba("#ffffff"))
    d.line([(X(fx) + 2, Y(fz + fd / 2)), (X(fx + fw) - 3, Y(fz + fd / 2))], fill=rgba("#ffffff"))
    for r in L["parking"]: R(r, "#cfcfd2")
    for pth in L["paths"]:
        x1, z1, x2, z2, w = pth
        R([min(x1, x2) - (w / 2 if x1 == x2 else 0), min(z1, z2) - (w / 2 if z1 == z2 else 0), abs(x2 - x1) + (w if x1 == x2 else 0), abs(z2 - z1) + (w if z1 == z2 else 0)], "#b6b6b3")
    R(L["branch"], "#5f6268"); R(L["road"], "#5d6066")
    rz = L["road"]
    for x in range(2, 55, 4): R([x, rz[1] + rz[3] / 2 - 0.1, 2, 0.2], "#f1f1ee")
    cx, cz, rr = L["roundabout"]
    d.ellipse((X(cx - rr), Y(cz - rr), X(cx + rr), Y(cz + rr)), fill=rgba("#5d6066"))
    d.ellipse((X(cx - rr / 2.2), Y(cz - rr / 2.2), X(cx + rr / 2.2), Y(cz + rr / 2.2)), fill=rgba("#7fb348"))
    for r in L["pond"]: R(r, "#58a6d6")
    d.rectangle((X(33), Y(6.3), X(35), Y(6.3)), fill=rgba("#a8dcf5"))
    # sombras dos edifícios (a sudeste), depois árvores atrás dos edifícios a sul e edifícios por ordem de z
    parts = [(b, p) for b in L["buildings"] for p in b["parts"]]
    for _, (x, z, w, dd, st) in parts:
        sh = st * L["poster"]["hk"] * k
        d.rectangle((X(x) + round(sh * .6), Y(z + dd), X(x + w) + round(sh * .6), Y(z + dd) + round(sh * .5)), fill=rgba("#5a8a35"))
    trees = []
    for lw in L["lawns"]:
        for _ in range(int(lw[2] * lw[3] / 9)):
            x, z = lw[0] + rnd.random() * lw[2], lw[1] + rnd.random() * lw[3]
            if not any(p[0] - 1 < x < p[0] + p[2] + 1 and p[1] - 1 < z < p[1] + p[3] + 1 for _, p in parts):
                trees.append((x, z))
    objs = [("t", z, x) for x, z in trees] + [("b", p[1] + p[3], b, p) for b, p in parts]
    for o in sorted(objs, key=lambda o: o[1]):
        if o[0] == "t":
            x, z = o[2], o[1]
            r = max(2, round(1.0 * S))
            d.rectangle((X(x) - 1, Y(z) - r, X(x), Y(z)), fill=rgba("#6b4423"))
            d.ellipse((X(x) - r, Y(z) - 3 * r, X(x) + r, Y(z) - r // 2), fill=rgba("#2f7d32"))
            d.ellipse((X(x) - r // 2, Y(z) - 3 * r, X(x) + r // 2, Y(z) - 2 * r), fill=rgba("#4fa04a"))
        else:
            _, _, b, (x, z, w, dd, st) = o
            hpx = round(st * L["poster"]["hk"] * k)
            x0, x1, y1 = X(x), X(x + w) - 1, Y(z + dd) - 1
            roof_y0, roof_y1 = Y(z) - hpx, Y(z + dd) - hpx - 1
            fh = hpx
            brick_h = round(fh * (0.55 if st >= 2 else 1))
            d.rectangle((x0, roof_y1 + 1, x1, y1), fill=rgba("#d4472a"))
            if brick_h < fh:
                d.rectangle((x0, roof_y1 + 1 + brick_h, x1, y1), fill=rgba("#faf8f2"))
                for xx in range(x0, x1, max(3, round(2 * S / 1.5))):
                    d.rectangle((xx, roof_y1 + 1 + brick_h, xx + max(1, S // 4), y1), fill=rgba("#ffffff"))
            wy = roof_y1 + 1 + max(1, brick_h // 3)
            d.rectangle((x0 + 1, wy, x1 - 1, wy + max(1, brick_h // 3)), fill=rgba("#222c38"))
            d.rectangle((x0, roof_y0, x1, roof_y1), fill=rgba("#d8dbe0"))
            d.rectangle((x0, roof_y0, x1, roof_y0 + 1), fill=rgba("#f2f4f7"))
            d.rectangle((x1, roof_y0, x1, y1), fill=rgba("#a63018"))
    if L.get("extra"):  # mesa de cartas e painel de bits à porta do pavilhão
        tx, tz, tw, td = L["extra"]["table"]
        R([tx, tz, tw, td], "#2f8f4a"); R([tx + 0.2, tz + 0.25, 0.4, 0.5], "#ffffff")
        px0, pz0, pw, pd = L["extra"]["panel"]
        R([px0, pz0 - 0.3, pw, 0.5], "#1c2340"); R([px0 + 0.15, pz0 - 0.2, pw - 0.3, 0.25], "#52e3ee")
    # muro de entrada
    wx, wz, ww = L["wall"]
    R([wx, wz, ww, 0.5], "#f4f1ea")
    return im


def build_campus():
    import json as _j
    L = _j.load(open(ROOT / "scenes/campus/layout.json"))
    out = ASSETS / "sprites/campus"
    out.mkdir(parents=True, exist_ok=True)
    paint_campus(L, 6).save(out / "poster.png")
    paint_campus(L, 3).save(out / "poster-small.png")


# ---------- Extra: cartas de poker (52 + verso), fichas e ícones dos jogos (originais, desenhados por código) ----------
GLYPH = {  # fonte 3x5 para os valores
    "A": ["010", "101", "111", "101", "101"], "K": ["101", "101", "110", "101", "101"], "Q": ["111", "101", "101", "111", "001"],
    "J": ["001", "001", "001", "101", "010"], "0": ["111", "101", "101", "101", "111"], "1": ["110", "010", "010", "010", "111"],
    "2": ["110", "001", "010", "100", "111"], "3": ["110", "001", "010", "001", "110"], "4": ["101", "101", "111", "001", "001"],
    "5": ["111", "100", "110", "001", "110"], "6": ["011", "100", "111", "101", "111"], "7": ["111", "001", "010", "010", "010"],
    "8": ["111", "101", "111", "101", "111"], "9": ["111", "101", "111", "001", "110"],
}
SUIT7 = {
    "s": ["...#...", "..###..", ".#####.", "#######", "#######", "...#...", "..###.."],
    "h": [".##.##.", "#######", "#######", "#######", ".#####.", "..###..", "...#..."],
    "d": ["...#...", "..###..", ".#####.", "#######", ".#####.", "..###..", "...#..."],
    "c": ["..###..", "..###..", "##.#.##", "#######", "#######", "...#...", "..###.."],
}
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
INK, RED_INK, PAPER = "#1b1424", "#d62f3a", "#fbfaf4"


def _put(im, bits, x, y, scale, color):
    for r, row in enumerate(bits):
        for c, ch in enumerate(row):
            if ch in "#1":
                for dy in range(scale):
                    for dx in range(scale):
                        px, py = x + c * scale + dx, y + r * scale + dy
                        if 0 <= px < im.width and 0 <= py < im.height:
                            im.putpixel((px, py), rgba(color))


def card_face(rank, suit, big):
    W, H = (48, 64) if big else (24, 32)
    gs, ss, ps = (2, 1, 3) if big else (1, 1, 1)  # escala do valor, do naipe pequeno e do naipe central
    col = RED_INK if suit in "hd" else INK
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((1, 0, W - 2, H - 1), fill=rgba(INK)); d.rectangle((0, 1, W - 1, H - 2), fill=rgba(INK))
    d.rectangle((1, 1, W - 2, H - 2), fill=rgba(PAPER))
    d.rectangle((1, 1, W - 2, 1), fill=rgba("#ffffff"))
    glyphs = [GLYPH[ch] for ch in rank]
    gw = (3 * len(glyphs) + (len(glyphs) - 1)) * gs
    corner = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gx = 3
    for g in glyphs:
        _put(corner, g, gx, 3, gs, col); gx += 4 * gs
    _put(corner, SUIT7[suit], 3, 3 + 5 * gs + 2, ss, col)
    im.alpha_composite(corner)
    im.alpha_composite(corner.rotate(180))
    # centro: naipe grande (cartas de figuras levam a letra, em moldura colorida)
    cx, cy = (W - 7 * ps) // 2, (H - 7 * ps) // 2
    if rank in ("J", "Q", "K"):
        bw, bh = (24, 34) if big else (12, 16)
        bx, by = (W - bw) // 2, (H - bh) // 2
        d.rectangle((bx, by, bx + bw - 1, by + bh - 1), fill=rgba(mix(col, "#ffffff", 0.82)), outline=rgba(col))
        _put(im, GLYPH[rank], bx + (bw - 3 * (3 if big else 2)) // 2, by + (bh - 5 * (3 if big else 2)) // 2 - (2 if big else 1), 3 if big else 2, col)
        _put(im, SUIT7[suit], (W - 7 * ps) // 2 if big else (W - 7) // 2, by + bh - 7 * (2 if big else 1) - 2, 2 if big else 1, col)
    else:
        n = 1 if rank == "A" else int(rank)
        if n == 1:
            _put(im, SUIT7[suit], cx, cy, ps, col)
        elif not big:
            _put(im, SUIT7[suit], (W - 7) // 2, (H - 7) // 2, 1, col)       # cartas pequenas: só o naipe ao centro
        else:
            top, bot = 12, H - 12 - 7
            lin = lambda k: [top + (bot - top) * i // max(1, k - 1) for i in range(k)]
            cl, cr_, cc = W // 2 - 10, W // 2 + 3, W // 2 - 3
            k = {4: 2, 5: 2, 6: 3, 7: 3, 8: 3, 9: 4, 10: 4}.get(n, 0)
            if n in (2, 3):
                for y in ([top, bot] if n == 2 else lin(3)): _put(im, SUIT7[suit], cc, y, 1, col)
            else:
                ys = lin(k)
                for y in ys: _put(im, SUIT7[suit], cl, y, 1, col); _put(im, SUIT7[suit], cr_, y, 1, col)
                if n == 5: _put(im, SUIT7[suit], cc, (top + bot) // 2, 1, col)
                if n == 7: _put(im, SUIT7[suit], cc, (ys[0] + ys[1]) // 2, 1, col)
                if n == 8: _put(im, SUIT7[suit], cc, (ys[0] + ys[1]) // 2, 1, col); _put(im, SUIT7[suit], cc, (ys[1] + ys[2]) // 2, 1, col)
                if n == 9: _put(im, SUIT7[suit], cc, (ys[1] + ys[2]) // 2, 1, col)
                if n == 10: _put(im, SUIT7[suit], cc, (ys[0] + ys[1]) // 2, 1, col); _put(im, SUIT7[suit], cc, (ys[2] + ys[3]) // 2, 1, col)
    return im


def card_back(big, emblem):
    W, H = (48, 64) if big else (24, 32)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((1, 0, W - 2, H - 1), fill=rgba(INK)); d.rectangle((0, 1, W - 1, H - 2), fill=rgba(INK))
    d.rectangle((1, 1, W - 2, H - 2), fill=rgba("#f4f1e8"))
    d.rectangle((3, 3, W - 4, H - 4), fill=rgba("#2a3b7a"))
    for y in range(4, H - 4):
        for x in range(4, W - 4):
            if (x + y) % 4 == 0: im.putpixel((x, y), rgba("#3a52a3"))
    d.rectangle((3, 3, W - 4, H - 4), outline=rgba("#ffd23f"))
    e = emblem.resize((16 if not big else 32,) * 2, Image.NEAREST) if emblem.width != (32 if big else 16) else emblem
    box = Image.new("RGBA", (e.width + 4, e.height + 4), rgba("#f4f1e8")); box.alpha_composite(e, (2, 2))
    im.alpha_composite(box, ((W - box.width) // 2, (H - box.height) // 2))
    return im


def chip(color, size):
    S = size
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    dark = mix(color, "#000000", 0.45)
    d.ellipse((0, 0, S - 1, S - 1), fill=rgba(INK))
    d.ellipse((1, 1, S - 2, S - 2), fill=rgba(color))
    import math
    for k in range(8):  # marcas brancas na orla
        a = k * math.pi / 4
        cx, cy = S / 2 + math.cos(a) * (S / 2 - 3), S / 2 + math.sin(a) * (S / 2 - 3)
        r = max(1, S // 12)
        d.rectangle((cx - r, cy - r, cx + r - (1 if r == 1 else 0), cy + r - (1 if r == 1 else 0)), fill=rgba("#ffffff" if color != "#f4f1e8" else "#8a8a99"))
    q = S // 4
    d.ellipse((q, q, S - 1 - q, S - 1 - q), fill=rgba(dark)); d.ellipse((q + 1, q + 1, S - 2 - q, S - 2 - q), fill=rgba(color))
    d.point((S // 4 + 1, S // 4 + 1), fill=rgba("#ffffff"))
    return im


def build_extra(emb):
    cards = ASSETS / "sprites/cards"
    for big, sub in ((False, "sm"), (True, "lg")):
        (cards / sub).mkdir(parents=True, exist_ok=True)
        for r in RANKS:
            for su in "shdc":
                card_face(r, su, big).save(cards / sub / f"{r}{su}.png")
        card_back(big, emb[32 if big else 16]).save(cards / sub / "back.png")
    ch = ASSETS / "sprites/chips"; ch.mkdir(parents=True, exist_ok=True)
    for name, hexc in {"white": "#f4f1e8", "red": "#d94a4a", "blue": "#3f7fe0", "green": "#3fae5a", "black": "#3a3a48"}.items():
        for S in (16, 32): chip(hexc, S).save(ch / f"{name}-{S}.png")
    ic = ASSETS / "sprites/icons"
    # ícone do poker: carta com espada + ficha
    im, d = canvas(); d.rectangle((2, 1, 10, 13), fill=rgba("#fbfaf4"), outline=rgba(INK)); _put(im, SUIT7["s"], 3, 4, 1, INK); d.ellipse((8, 8, 15, 15), fill=rgba("#d94a4a"), outline=rgba(INK)); d.ellipse((10, 10, 13, 13), outline=rgba("#ffffff")); im.save(ic / "poker.png")
    # Bit a Bit: 4 bits acesos/apagados
    im, d = canvas(); d.rectangle((0, 3, 15, 12), fill=rgba("#1c2340"), outline=rgba(INK))
    for i, on in enumerate([1, 0, 1, 1]):
        d.rectangle((1 + i * 4, 5, 3 + i * 4, 10), fill=rgba("#52e3ee" if on else "#3a4570"))
        if on: d.point((2 + i * 4, 7), fill=rgba("#ffffff"))
    im.save(ic / "bitabit.png")
    # Extra (navegação): comando de jogo
    im, d = canvas(); d.rectangle((1, 4, 14, 12), fill=rgba("#8a97ab"), outline=rgba(INK)); d.rectangle((3, 7, 6, 8), fill=rgba(INK)); d.rectangle((4, 6, 5, 9), fill=rgba(INK))
    d.rectangle((10, 6, 11, 7), fill=rgba("#e8484f")); d.rectangle((12, 8, 13, 9), fill=rgba("#ffd23f")); d.rectangle((2, 5, 13, 5), fill=rgba("#d5dde8")); im.save(ic / "extra.png")


# ---------- favicon e ícones PWA ----------
def build_pwa(emb):
    """Favicon e ícones PWA com o emblema UPT (fundo claro para o verde e o contorno lerem bem)."""
    out = ASSETS / "icons"
    out.mkdir(parents=True, exist_ok=True)
    bgc = rgba("#f4f8ec")

    def icon(size, scale, bg=True):
        im = Image.new("RGBA", (size, size), bgc if bg else (0, 0, 0, 0))
        big = emb[64].resize((64 * scale, 64 * scale), Image.NEAREST)
        o = (size - 64 * scale) // 2
        im.alpha_composite(big, (o, o))
        return im

    emb[32].save(out / "favicon-32.png")
    icon(180, 2).save(out / "apple-touch-icon.png")
    icon(192, 2).save(out / "icon-192.png")
    icon(512, 6).save(out / "icon-512.png")
    icon(512, 5).save(out / "icon-maskable-512.png")  # zona segura de 80%


if __name__ == "__main__":
    build_icons()
    build_ui()
    build_themes()
    build_medals()
    build_more()
    build_academy()
    build_campus()
    emb = build_upt()
    build_extra(emb)
    build_pwa(emb)
    print("ok")
