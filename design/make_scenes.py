"""
Makes ui/scenes/*.svg and ui/scenes/scenes.js: Jarvis's five desktop scenes, drawn at 3840x2160.

    python design/make_scenes.py

Everything is drawn from code (no traced or copied artwork). Each scene leaves the middle for his voice ring and the
left and right thirds calm enough for panels and widgets to sit on. Text that comes from real data (sunset, version,
your apps...) isn't baked in: it's listed as "labels" in scenes.js and drawn over the picture by ui/desktop.js.
"""
import json
import math
import os
import random

W, H = 3840, 2160
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ui", "scenes")


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def f(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


class Scene:
    def __init__(self, key, title, seed):
        self.key, self.title = key, title
        self.defs, self.g, self.labels = [], [], []
        random.seed(seed)

    def add(self, s):
        self.g.append(s)

    def d(self, s):
        self.defs.append(s)

    def text(self, x, y, s, **a):
        attrs = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in a.items())
        self.add(f'<text x="{f(x)}" y="{f(y)}" {attrs}>{esc(s)}</text>')

    def label(self, k, tpl, x, y, **a):
        attrs = {"x": f(x), "y": f(y)}
        attrs.update({kk.replace("_", "-"): str(v) for kk, v in a.items()})
        self.labels.append({"k": k, "tpl": tpl, "attrs": attrs})

    def svg(self):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid slice">'
                f'<defs>{"".join(self.defs)}</defs>{"".join(self.g)}</svg>')


def poly(pts):
    return " ".join(f"{f(x)},{f(y)}" for x, y in pts)


def noise_loop(cx, cy, r, sx=1.0, sy=1.0, harmonics=((3, .12), (5, .07), (9, .04), (17, .015)), phases=None, step=3):
    phases = phases or [random.uniform(0, 6.283) for _ in harmonics]
    pts = []
    for i in range(0, 360, step):
        a = math.radians(i)
        k = 1 + sum(amp * math.sin(n * a + p) for (n, amp), p in zip(harmonics, phases))
        pts.append((cx + r * k * math.cos(a) * sx, cy + r * k * math.sin(a) * sy))
    return pts, phases


# =====================================================================================================================
# 1. Drafting bench: his engineering drawings at night, the listening core he keeps improving
# =====================================================================================================================
def bench():
    S = Scene("bench", "Drafting bench", 3)
    ink, paper, warm = "#a9d4ff", "#0b1b2e", "#ffcf8a"
    MONO = "'IBM Plex Mono',Consolas,monospace"
    HAND = "'Segoe Print','Bradley Hand','Comic Sans MS',cursive"
    S.d(f'<radialGradient id="lampb" cx="18%" cy="8%" r="75%"><stop offset="0" stop-color="{warm}" stop-opacity=".16"/>'
        f'<stop offset=".5" stop-color="{warm}" stop-opacity=".03"/><stop offset="1" stop-color="{warm}" stop-opacity="0"/></radialGradient>'
        '<radialGradient id="vigb" cx="50%" cy="50%" r="75%"><stop offset=".55" stop-color="#000" stop-opacity="0"/>'
        '<stop offset="1" stop-color="#000" stop-opacity=".55"/></radialGradient>'
        f'<pattern id="g1" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M32 0H0V32" fill="none" stroke="{ink}" stroke-opacity=".07" stroke-width="1.2"/></pattern>'
        f'<pattern id="g5" width="160" height="160" patternUnits="userSpaceOnUse"><path d="M160 0H0V160" fill="none" stroke="{ink}" stroke-opacity=".16" stroke-width="1.6"/></pattern>'
        f'<pattern id="hatch" width="14" height="14" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><path d="M0 0V14" stroke="{ink}" stroke-opacity=".45" stroke-width="1.6"/></pattern>'
        '<filter id="soft"><feGaussianBlur stdDeviation="6"/></filter>')
    S.add(f'<rect width="{W}" height="{H}" fill="#08131f"/>')
    # the sheet underneath, a little rotated, then the main sheet
    S.add(f'<g transform="rotate(-1.6 {W/2} {H/2})"><rect x="140" y="120" width="{W-220}" height="{H-180}" fill="#0a1828"/>'
          f'<rect x="140" y="120" width="{W-220}" height="{H-180}" fill="url(#g1)"/></g>')
    S.add(f'<rect x="60" y="60" width="{W-120}" height="{H-120}" fill="{paper}"/>')
    S.add(f'<rect x="60" y="60" width="{W-120}" height="{H-120}" fill="url(#g1)"/><rect x="60" y="60" width="{W-120}" height="{H-120}" fill="url(#g5)"/>')
    for _ in range(2600):                                                     # paper tooth
        S.add(f'<circle cx="{random.uniform(60, W-60):.0f}" cy="{random.uniform(60, H-60):.0f}" r="{random.choice((.8, 1, 1.4))}" '
              f'fill="{ink}" fill-opacity="{random.uniform(.03, .09):.2f}"/>')
    S.add(f'<rect x="60" y="60" width="{W-120}" height="{H-120}" fill="none" stroke="{ink}" stroke-opacity=".55" stroke-width="3"/>')
    S.add(f'<rect x="100" y="100" width="{W-200}" height="{H-200}" fill="none" stroke="{ink}" stroke-opacity=".35" stroke-width="1.5"/>')
    for x in range(100, W - 99, 160):                                           # zone markers on the border
        S.add(f'<line x1="{x}" y1="60" x2="{x}" y2="100" stroke="{ink}" stroke-opacity=".35"/><line x1="{x}" y1="{H-100}" x2="{x}" y2="{H-60}" stroke="{ink}" stroke-opacity=".35"/>')
    for i, x in enumerate(range(180, W - 100, 160)):
        S.text(x, 88, str(i + 1), fill=ink, fill_opacity=".5", font_size="20", text_anchor="middle", font_family=MONO)
    for i, y in enumerate(range(180, H - 100, 160)):
        S.text(80, y + 7, "ABCDEFGHJKLMN"[i], fill=ink, fill_opacity=".5", font_size="20", text_anchor="middle", font_family=MONO)
    # long construction lines in pencil
    for _ in range(14):
        a = random.uniform(0, math.pi)
        x0, y0 = random.uniform(400, W - 400), random.uniform(300, H - 300)
        S.add(f'<line x1="{f(x0 - 3000*math.cos(a))}" y1="{f(y0 - 3000*math.sin(a))}" x2="{f(x0 + 3000*math.cos(a))}" '
              f'y2="{f(y0 + 3000*math.sin(a))}" stroke="{ink}" stroke-opacity=".05" stroke-width="1.2"/>')

    cx, cy = 1920, 1060
    # ---- the listening core, front view
    def gear(cx, cy, r, teeth, depth, op=.75, sw=2.2):
        pts = []
        for i in range(teeth):
            a0 = i * 2 * math.pi / teeth
            for da, rr in ((0, r - depth), (.18, r - depth), (.3, r), (.62, r), (.74, r - depth), (1, r - depth)):
                a = a0 + da * 2 * math.pi / teeth
                pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        return f'<polygon points="{poly(pts)}" fill="none" stroke="{ink}" stroke-opacity="{op}" stroke-width="{sw}"/>'
    S.add(gear(cx, cy, 700, 96, 26))
    for r, op, sw, dash in ((640, .45, 1.6, ""), (600, .7, 2.2, ""), (520, .35, 1.4, "18 8"), (470, .7, 2.2, ""),
                            (300, .7, 2.2, ""), (262, .45, 1.6, ""), (150, .7, 2.2, ""), (96, .55, 1.6, ""), (60, .8, 2.4, "")):
        S.add(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{ink}" stroke-opacity="{op}" stroke-width="{sw}"'
              + (f' stroke-dasharray="{dash}"' if dash else "") + "/>")
    # bearing balls between 470 and 600
    for i in range(22):
        a = i * 2 * math.pi / 22
        S.add(f'<circle cx="{f(cx + 535*math.cos(a))}" cy="{f(cy + 535*math.sin(a))}" r="26" fill="none" stroke="{ink}" stroke-opacity=".55" stroke-width="1.6"/>')
    # six spokes with rounded roots, lightening holes between them
    for i in range(6):
        a = i * math.pi / 3 + .26
        for side in (-1, 1):
            off = side * .085
            S.add(f'<path d="M {f(cx + 150*math.cos(a+off*2))} {f(cy + 150*math.sin(a+off*2))} L {f(cx + 470*math.cos(a+off))} '
                  f'{f(cy + 470*math.sin(a+off))}" stroke="{ink}" stroke-opacity=".7" stroke-width="2.2"/>')
        b = a + math.pi / 6
        S.add(f'<circle cx="{f(cx + 380*math.cos(b))}" cy="{f(cy + 380*math.sin(b))}" r="56" fill="none" stroke="{ink}" stroke-opacity=".5" stroke-width="1.6"/>')
        S.add(f'<circle cx="{f(cx + 205*math.cos(a))}" cy="{f(cy + 205*math.sin(a))}" r="18" fill="none" stroke="{ink}" stroke-opacity=".6" stroke-width="1.6"/>')
    # sectioned quadrant (hatched) at lower right
    S.d(f'<clipPath id="quad"><path d="M {cx} {cy} L {cx+760} {cy} A 760 760 0 0 1 {cx} {cy+760} Z"/></clipPath>')
    S.add(f'<g clip-path="url(#quad)"><path d="M {cx-600} {cy} a 600 600 0 1 0 1200 0 a 600 600 0 1 0 -1200 0 M {cx-470} {cy} '
          f'a 470 470 0 1 1 940 0 a 470 470 0 1 1 -940 0" fill="url(#hatch)" fill-rule="evenodd"/>'
          f'<path d="M {cx-300} {cy} a 300 300 0 1 0 600 0 a 300 300 0 1 0 -600 0 M {cx-150} {cy} a 150 150 0 1 1 300 0 '
          f'a 150 150 0 1 1 -300 0" fill="url(#hatch)" fill-rule="evenodd"/></g>')
    # keyway
    S.add(f'<rect x="{cx-14}" y="{cy-96}" width="28" height="38" fill="none" stroke="{ink}" stroke-opacity=".7" stroke-width="2"/>')
    # centre lines
    S.add(f'<line x1="{cx-860}" y1="{cy}" x2="{cx+860}" y2="{cy}" stroke="{ink}" stroke-opacity=".38" stroke-width="1.6" stroke-dasharray="44 10 8 10"/>')
    S.add(f'<line x1="{cx}" y1="{cy-860}" x2="{cx}" y2="{cy+860}" stroke="{ink}" stroke-opacity=".38" stroke-width="1.6" stroke-dasharray="44 10 8 10"/>')
    # ---- meshing pinion, upper right
    px, py = cx + 700 + 170, cy - 470
    S.add(f'<g transform="rotate(4 {px} {py})">{gear(px, py, 210, 28, 24, .65, 2)}</g>')
    for r in (170, 120, 46):
        S.add(f'<circle cx="{f(px)}" cy="{f(py)}" r="{r}" fill="none" stroke="{ink}" stroke-opacity=".5" stroke-width="1.6"' + (' stroke-dasharray="12 7"' if r == 120 else "") + "/>")
    S.add(f'<line x1="{cx}" y1="{cy}" x2="{f(px)}" y2="{f(py)}" stroke="{ink}" stroke-opacity=".3" stroke-dasharray="30 8 6 8"/>')
    # ---- dimensions
    def dim_h(x1, x2, y, label, ext_from):
        S.add(f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{ink}" stroke-opacity=".65" stroke-width="1.6"/>')
        for x, s in ((x1, 1), (x2, -1)):
            S.add(f'<path d="M {x} {y} l {s*22} -7 l 0 14 Z" fill="{ink}" fill-opacity=".7"/>')
            S.add(f'<line x1="{x}" y1="{ext_from}" x2="{x}" y2="{y + 18}" stroke="{ink}" stroke-opacity=".25" stroke-width="1.2"/>')
        S.text((x1 + x2) / 2, y - 14, label, fill=ink, fill_opacity=".8", font_size="30", text_anchor="middle", font_family=MONO)
    dim_h(cx - 700, cx + 700, cy + 820, "Ø 1400", cy)
    dim_h(cx - 470, cx + 470, cy + 760, "Ø 940  BEARING SEAT", cy)
    # radius callout
    a = math.radians(-128)
    S.add(f'<line x1="{cx}" y1="{cy}" x2="{f(cx + 300*math.cos(a))}" y2="{f(cy + 300*math.sin(a))}" stroke="{ink}" stroke-opacity=".6" stroke-width="1.6"/>')
    S.text(cx + 330 * math.cos(a) - 20, cy + 330 * math.sin(a), "R300", fill=ink, fill_opacity=".8", font_size="28", text_anchor="end", font_family=MONO)
    # ---- balloons
    for n, (ax, ay, bx, by) in enumerate(((cx + 690, cy + 120, cx + 960, cy + 330), (cx + 330, cy - 310, cx + 560, cy - 640),
                                          (cx - 535, cy, cx - 900, cy - 360), (cx - 70, cy - 120, cx - 520, cy - 720),
                                          (px - 150, py - 120, px - 420, py - 380), (cx + 40, cy + 300, cx + 420, cy + 940))):
        S.add(f'<line x1="{f(ax)}" y1="{f(ay)}" x2="{f(bx)}" y2="{f(by)}" stroke="{ink}" stroke-opacity=".55" stroke-width="1.4"/>')
        S.add(f'<circle cx="{f(ax)}" cy="{f(ay)}" r="5" fill="{ink}" fill-opacity=".7"/>')
        S.add(f'<circle cx="{f(bx)}" cy="{f(by)}" r="30" fill="{paper}" stroke="{ink}" stroke-opacity=".75" stroke-width="2"/>')
        S.text(bx, by + 10, str(n + 1), fill=ink, fill_opacity=".9", font_size="30", text_anchor="middle", font_family=MONO)
    # ---- exploded view, lower left: parts stacked along a slanted axis
    ex, ey = 560, 1500
    S.add(f'<line x1="{ex - 120}" y1="{ey + 300}" x2="{ex + 640}" y2="{ey - 520}" stroke="{ink}" stroke-opacity=".35" stroke-dasharray="26 8 6 8" stroke-width="1.4"/>')
    for i, (rx, ry, h, name) in enumerate(((210, 70, 40, "cover"), (250, 84, 70, "outer ring"), (190, 64, 30, "bearing"),
                                           (150, 50, 90, "spokes"), (70, 24, 120, "hub"))):
        x, y = ex + i * 130, ey - i * 140
        S.add(f'<path d="M {x-rx} {y} L {x-rx} {y+h} A {rx} {ry} 0 0 0 {x+rx} {y+h} L {x+rx} {y}" fill="#0c1f34" stroke="{ink}" stroke-opacity=".6" stroke-width="1.8"/>')
        S.add(f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" fill="#0e2340" stroke="{ink}" stroke-opacity=".7" stroke-width="1.8"/>')
        S.add(f'<ellipse cx="{x}" cy="{y}" rx="{rx*.35:.0f}" ry="{ry*.35:.0f}" fill="none" stroke="{ink}" stroke-opacity=".5" stroke-width="1.4"/>')
        S.text(x + rx + 24, y + 10, name, fill=ink, fill_opacity=".55", font_size="24", font_family=MONO)
    S.text(ex - 160, ey + 380, "fig. 2: exploded, not to scale", fill=ink, fill_opacity=".6", font_size="26", font_family=MONO)
    # ---- protractor and ruler
    qx, qy = 760, 700
    S.add(f'<path d="M {qx-240} {qy} a 240 240 0 0 1 480 0 Z" fill="{ink}" fill-opacity=".03" stroke="{ink}" stroke-opacity=".4" stroke-width="1.6"/>')
    for d in range(0, 181, 5):
        a = math.radians(180 + d)
        L = 26 if d % 30 == 0 else 16 if d % 10 == 0 else 9
        S.add(f'<line x1="{f(qx + 240*math.cos(a))}" y1="{f(qy + 240*math.sin(a))}" x2="{f(qx + (240-L)*math.cos(a))}" '
              f'y2="{f(qy + (240-L)*math.sin(a))}" stroke="{ink}" stroke-opacity=".5" stroke-width="1.3"/>')
    S.add(f'<line x1="{qx}" y1="{qy}" x2="{f(qx + 230*math.cos(math.radians(-40)))}" y2="{f(qy + 230*math.sin(math.radians(-40)))}" stroke="{ink}" stroke-opacity=".45" stroke-width="1.4"/>')
    S.text(qx + 40, qy - 24, "40°", fill=ink, fill_opacity=".6", font_size="22", font_family=MONO)
    S.add(f'<rect x="130" y="300" width="56" height="1560" fill="{ink}" fill-opacity=".03" stroke="{ink}" stroke-opacity=".4" stroke-width="1.4"/>')
    for i in range(0, 157):
        L = 30 if i % 10 == 0 else 18 if i % 5 == 0 else 10
        S.add(f'<line x1="130" y1="{310 + i*10}" x2="{130 + L}" y2="{310 + i*10}" stroke="{ink}" stroke-opacity=".5" stroke-width="1.2"/>')
        if i % 10 == 0:
            S.text(176, 318 + i * 10, str(i // 10), fill=ink, fill_opacity=".5", font_size="18", text_anchor="end", font_family=MONO)
    # ---- coffee ring (he denies it)
    for r, op, da in ((118, .10, "620 120"), (110, .06, "300 90 200 60"), (124, .04, "")):
        S.add(f'<circle cx="3420" cy="1260" r="{r}" fill="none" stroke="{warm}" stroke-opacity="{op}" stroke-width="7"' + (f' stroke-dasharray="{da}"' if da else "") + "/>")
    # ---- revision table, top right
    tx, ty, tw = 2780, 140, 940
    rows = [("REV", "DATE", "DESCRIPTION", "BY"), ("25", "09/22", "bigger ears, smaller mouth", "J."),
            ("26", "10/30", "three voices merged into one", "J."), ("27", "11/05", "listening core, rev. 27", "J.")]
    for i, r in enumerate(rows):
        y = ty + i * 44
        S.add(f'<rect x="{tx}" y="{y}" width="{tw}" height="44" fill="{ink if i == 0 else "none"}" fill-opacity=".06" stroke="{ink}" stroke-opacity=".45" stroke-width="1.4"/>')
        for x, txt in zip((tx + 16, tx + 106, tx + 246, tx + tw - 50), r):
            S.text(x, y + 30, txt, fill=ink, fill_opacity=".75" if i == 0 else ".6", font_size="22", font_family=MONO)
    # ---- parts list, bottom right
    tx, ty, tw = 2620, 1560, 1100
    rows = [("ITEM", "QTY", "PART", "MATERIAL"), ("1", "1", "outer ring", "anodised aluminium"), ("2", "6", "spoke", "carbon, wet layup"),
            ("3", "22", "bearing ball", "silicon nitride"), ("4", "1", "hub", "titanium"), ("5", "1", "pinion", "hardened steel"),
            ("6", "1", "cover plate", "smoked acrylic")]
    for i, r in enumerate(rows):
        y = ty + i * 44
        S.add(f'<rect x="{tx}" y="{y}" width="{tw}" height="44" fill="{ink if i == 0 else "none"}" fill-opacity=".06" stroke="{ink}" stroke-opacity=".45" stroke-width="1.4"/>')
        for x, txt in zip((tx + 16, tx + 120, tx + 220, tx + 560), r):
            S.text(x, y + 30, txt, fill=ink, fill_opacity=".75" if i == 0 else ".6", font_size="22", font_family=MONO)
    # ---- title block, bottom left
    bx, by = 260, 1860
    S.add(f'<rect x="{bx}" y="{by}" width="1060" height="200" fill="{paper}" stroke="{ink}" stroke-opacity=".6" stroke-width="2"/>')
    for yy in (by + 70, by + 135):
        S.add(f'<line x1="{bx}" y1="{yy}" x2="{bx + 1060}" y2="{yy}" stroke="{ink}" stroke-opacity=".45" stroke-width="1.4"/>')
    for xx in (bx + 520, bx + 800):
        S.add(f'<line x1="{xx}" y1="{by + 70}" x2="{xx}" y2="{by + 200}" stroke="{ink}" stroke-opacity=".45" stroke-width="1.4"/>')
    S.text(bx + 24, by + 48, "J.A.R.V.I.S.  HOME BENCH  /  LISTENING CORE", fill=ink, fill_opacity=".85", font_size="30", font_family=MONO)
    S.text(bx + 24, by + 112, "Drawn by J.", fill=ink, fill_opacity=".7", font_size="24", font_family=MONO)
    S.text(bx + 544, by + 112, "Sheet 1 of 2", fill=ink, fill_opacity=".7", font_size="24", font_family=MONO)
    S.text(bx + 824, by + 112, "Scale 1:1", fill=ink, fill_opacity=".7", font_size="24", font_family=MONO)
    S.text(bx + 24, by + 178, "Units mm. Break all sharp edges.", fill=ink, fill_opacity=".6", font_size="22", font_family=MONO)
    S.text(bx + 824, by + 178, "3rd angle", fill=ink, fill_opacity=".6", font_size="22", font_family=MONO)
    S.label("checked", "Checked: {address}", bx + 544, by + 178, fill=ink, fill_opacity=".7", font_size="24", font_family=MONO)
    # ---- margin notes in his hand
    S.text(280, 250, "fig. 1", fill=ink, fill_opacity=".7", font_size="34", font_family=MONO)
    S.label("rev", "listening core, rev. {rev}", 280, 296, fill=ink, fill_opacity=".6", font_size="28", font_family=MONO)
    S.text(280, 340, "tolerance ±0.02, do not over-tighten", fill=ink, fill_opacity=".5", font_size="26", font_family=MONO)
    S.label("fix", "{fix}", 3080, 820, fill=ink, fill_opacity=".65", font_size="32", font_family=HAND)
    S.text(3080, 872, "the old bearing squeaked. never again.", fill=ink, fill_opacity=".45", font_size="28", font_family=HAND)
    S.text(3080, 924, "J.", fill=ink, fill_opacity=".55", font_size="30", font_family=HAND)
    S.text(2960, 1180, "check the mesh here", fill=ink, fill_opacity=".5", font_size="30", font_family=HAND)
    S.add(f'<path d="M 2950 1150 Q 2860 1000 2700 830" fill="none" stroke="{ink}" stroke-opacity=".45" stroke-width="2"/>')
    # tape on the corners
    for x, y, r in ((60, 60, -32), (W - 60, 60, 32), (60, H - 60, 32), (W - 60, H - 60, -32)):
        S.add(f'<rect x="{x - 90}" y="{y - 26}" width="180" height="52" fill="#d9e6f2" fill-opacity=".07" transform="rotate({r} {x} {y})"/>')
    S.add(f'<rect width="{W}" height="{H}" fill="url(#lampb)"/><rect width="{W}" height="{H}" fill="url(#vigb)"/>')
    return S, (cx, cy), {"rev": "27", "fix": "the old bearing squeaked. replaced 11/05", "address": "you"}


# =====================================================================================================================
# 2. Orbital station: deck 3's observation window, above a planet always turning to night
# =====================================================================================================================
def station():
    S = Scene("station", "Orbital station", 7)
    ink = "#8fd8ff"
    UI = "Rajdhani,'Bahnschrift','Segoe UI',sans-serif"
    S.d('<radialGradient id="sky" cx="50%" cy="30%" r="80%"><stop offset="0" stop-color="#071225"/><stop offset="1" stop-color="#010309"/></radialGradient>'
        '<filter id="blur40"><feGaussianBlur stdDeviation="40"/></filter><filter id="blur8"><feGaussianBlur stdDeviation="8"/></filter>'
        '<filter id="blur3"><feGaussianBlur stdDeviation="3"/></filter>'
        '<radialGradient id="ocean" cx="35%" cy="8%" r="75%"><stop offset="0" stop-color="#2a7fb6"/><stop offset=".35" stop-color="#14527e"/>'
        '<stop offset=".7" stop-color="#0a2c49"/><stop offset="1" stop-color="#051526"/></radialGradient>'
        '<linearGradient id="night" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#000814" stop-opacity="0"/>'
        '<stop offset=".46" stop-color="#000814" stop-opacity="0"/><stop offset=".58" stop-color="#000814" stop-opacity=".82"/>'
        '<stop offset="1" stop-color="#000814" stop-opacity=".94"/></linearGradient>'
        '<radialGradient id="moon" cx="35%" cy="35%" r="70%"><stop offset="0" stop-color="#cfd8e6"/><stop offset="1" stop-color="#5d6a80"/></radialGradient>'
        '<linearGradient id="aur" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#5dffc8" stop-opacity=".55"/>'
        '<stop offset=".5" stop-color="#5dd9ff" stop-opacity=".18"/><stop offset="1" stop-color="#9a7dff" stop-opacity="0"/></linearGradient>'
        '<linearGradient id="glass" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".05"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
        '<linearGradient id="frame" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#101a2a"/><stop offset="1" stop-color="#070c16"/></linearGradient>')
    S.add(f'<rect width="{W}" height="{H}" fill="url(#sky)"/>')
    # nebula
    for x, y, rx, ry, c, op in ((900, 520, 900, 380, "#3b2a7a", .35), (1500, 380, 700, 260, "#1d5a7a", .3),
                                (2900, 420, 820, 300, "#2a1f5f", .28), (3300, 700, 500, 220, "#124a5c", .25)):
        S.add(f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" fill="{c}" fill-opacity="{op}" filter="url(#blur40)"/>')
    # stars, three depths
    for _ in range(1800):
        S.add(f'<circle cx="{random.uniform(0, W):.0f}" cy="{random.uniform(0, H*.72):.0f}" r="{random.choice((.8, 1, 1.2))}" fill="#dfe9ff" fill-opacity="{random.uniform(.2, .7):.2f}"/>')
    for _ in range(220):
        x, y = random.uniform(0, W), random.uniform(0, H * .7)
        S.add(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="2.2" fill="#eef4ff" fill-opacity="{random.uniform(.5, .95):.2f}"/>')
    for _ in range(14):
        x, y, L = random.uniform(200, W - 200), random.uniform(120, H * .55), random.uniform(18, 34)
        S.add(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="9" fill="#cfe6ff" fill-opacity=".35" filter="url(#blur3)"/><circle cx="{x:.0f}" cy="{y:.0f}" r="3" fill="#fff"/>'
              f'<path d="M {x-L:.0f} {y:.0f} H {x+L:.0f} M {x:.0f} {y-L:.0f} V {y+L:.0f}" stroke="#e6f2ff" stroke-opacity=".55" stroke-width="1.2"/>')
    # a moon, far off
    mx, my = 3160, 520
    S.add(f'<circle cx="{mx}" cy="{my}" r="96" fill="url(#moon)"/>')
    for _ in range(14):
        a, r = random.uniform(0, 6.28), random.uniform(0, 80)
        S.add(f'<circle cx="{mx + r*math.cos(a):.0f}" cy="{my + r*math.sin(a):.0f}" r="{random.uniform(4, 13):.0f}" fill="#3e4a5e" fill-opacity=".45"/>')
    S.d(f'<clipPath id="moonc"><circle cx="{mx}" cy="{my}" r="96"/></clipPath>')
    S.add(f'<circle clip-path="url(#moonc)" cx="{mx + 46}" cy="{my + 18}" r="100" fill="#010309" fill-opacity=".82"/>')
    # the planet
    PR, PX, PY = 4200, 1920, 2160 + 3260
    S.d(f'<clipPath id="planet"><circle cx="{PX}" cy="{PY}" r="{PR}"/></clipPath>')
    S.add(f'<circle cx="{PX}" cy="{PY}" r="{PR + 60}" fill="#5fc4ff" fill-opacity=".2" filter="url(#blur40)"/>')
    S.add(f'<circle cx="{PX}" cy="{PY}" r="{PR}" fill="url(#ocean)"/>')
    land = []
    for cxl, cyl, r in ((900, 2050, 520), (2350, 2000, 640), (3500, 2120, 420), (1650, 2240, 300)):
        pts, _ = noise_loop(cxl, cyl, r, 1.6, .35, ((2, .2), (3, .16), (7, .08), (13, .04), (23, .02)))
        land.append(pts)
        S.add(f'<polygon clip-path="url(#planet)" points="{poly(pts)}" fill="#1f4a3a" fill-opacity=".9" stroke="#86c9a8" stroke-opacity=".25" stroke-width="2"/>')
        inner, _ = noise_loop(cxl + 40, cyl + 10, r * .55, 1.6, .3, ((3, .2), (5, .1), (11, .05)))
        S.add(f'<polygon clip-path="url(#planet)" points="{poly(inner)}" fill="#4a5a3a" fill-opacity=".55"/>')
    # cloud bands
    for i in range(16):
        y = 1950 + i * 22 + random.uniform(-8, 8)
        x0 = random.uniform(-200, 2600)
        S.add(f'<path clip-path="url(#planet)" d="M {x0:.0f} {y:.0f} q {random.uniform(300, 600):.0f} {random.uniform(-40, 40):.0f} '
              f'{random.uniform(900, 1600):.0f} {random.uniform(-20, 20):.0f}" fill="none" stroke="#e8f6ff" stroke-opacity="{random.uniform(.08, .2):.2f}" '
              f'stroke-width="{random.uniform(6, 22):.0f}" stroke-linecap="round" filter="url(#blur3)"/>')
    # night side
    S.add(f'<circle cx="{PX}" cy="{PY}" r="{PR}" fill="url(#night)"/>')
    # city lights on the night side, along the land
    def inside(pts, x, y):
        c = False
        for i in range(len(pts)):
            (x1, y1), (x2, y2) = pts[i], pts[i - 1]
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-9) + x1:
                c = not c
        return c
    lights = 0
    while lights < 900:
        x, y = random.uniform(2200, 3840), random.uniform(1880, 2160)
        if (x - PX) ** 2 + (y - PY) ** 2 > PR ** 2 or not any(inside(p, x, y) for p in land):
            continue
        lights += 1
        S.add(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{random.choice((1.4, 1.8, 2.4))}" fill="#ffd27f" fill-opacity="{random.uniform(.35, .95):.2f}"/>')
    for _ in range(40):
        x, y = random.uniform(2400, 3700), random.uniform(1950, 2150)
        S.add(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="22" fill="#ffb347" fill-opacity=".12" filter="url(#blur8)"/>')
    # atmosphere rim
    for w, op in ((70, .12), (30, .25), (10, .5), (3, .9)):
        S.add(f'<circle cx="{PX}" cy="{PY}" r="{PR}" fill="none" stroke="#7fd6ff" stroke-opacity="{op}" stroke-width="{w}" filter="url(#blur3)"/>')
    # aurora over the night side
    S.add('<g filter="url(#blur3)">')
    for i in range(120):
        x = 2500 + i * 10
        base = 1770 + 60 * math.sin(i / 9) + 20 * math.sin(i / 3.1)
        h = 120 + 90 * abs(math.sin(i / 7)) + random.uniform(0, 40)
        S.add(f'<rect x="{x}" y="{base - h:.0f}" width="11" height="{h:.0f}" fill="url(#aur)" opacity="{.25 + .5*abs(math.sin(i/11)):.2f}"/>')
    S.add('</g>')
    # a supply station far off: truss and panels
    sx, sy = 640, 640
    S.add(f'<g transform="rotate(-14 {sx} {sy})" opacity=".8">')
    S.add(f'<rect x="{sx - 260}" y="{sy - 6}" width="520" height="12" fill="#8aa0b8"/>')
    for k in range(-2, 3):
        S.add(f'<rect x="{sx + k*110 - 40}" y="{sy - 90}" width="80" height="70" fill="#14335a" stroke="#7fb0d8" stroke-width="2"/>'
              f'<rect x="{sx + k*110 - 40}" y="{sy + 20}" width="80" height="70" fill="#14335a" stroke="#7fb0d8" stroke-width="2"/>')
        S.add(f'<path d="M {sx + k*110 - 40} {sy - 55} h 80 M {sx + k*110} {sy - 90} v 70 M {sx + k*110 - 40} {sy + 55} h 80 M {sx + k*110} {sy + 20} v 70" stroke="#7fb0d8" stroke-opacity=".5"/>')
    S.add(f'<circle cx="{sx}" cy="{sy}" r="34" fill="#c8d6e6"/><circle cx="{sx + 280}" cy="{sy}" r="7" fill="#ff5a5a"/></g>')
    # ---- the window frame (you're on deck 3)
    S.add('<polygon points="0,0 3840,0 3840,170 3300,170 3200,260 640,260 540,170 0,170" fill="url(#frame)"/>')
    S.add(f'<polyline points="0,170 540,170 640,260 3200,260 3300,170 3840,170" fill="none" stroke="{ink}" stroke-opacity=".45" stroke-width="3"/>')
    S.add('<polygon points="0,2160 0,1990 520,1990 600,1920 3240,1920 3320,1990 3840,1990 3840,2160" fill="url(#frame)"/>')
    S.add(f'<polyline points="0,1990 520,1990 600,1920 3240,1920 3320,1990 3840,1990" fill="none" stroke="{ink}" stroke-opacity=".45" stroke-width="3"/>')
    # side struts, in perspective
    S.add('<polygon points="0,170 300,170 210,1990 0,1990" fill="#0a111d"/><polygon points="3840,170 3540,170 3630,1990 3840,1990" fill="#0a111d"/>')
    S.add(f'<line x1="300" y1="170" x2="210" y2="1990" stroke="{ink}" stroke-opacity=".4" stroke-width="3"/><line x1="3540" y1="170" x2="3630" y2="1990" stroke="{ink}" stroke-opacity=".4" stroke-width="3"/>')
    for y in range(260, 1960, 120):                                     # strut ribs and rivets
        t = (y - 170) / 1820
        xl, xr = 300 - 90 * t, 3540 + 90 * t
        S.add(f'<line x1="0" y1="{y}" x2="{xl:.0f}" y2="{y}" stroke="{ink}" stroke-opacity=".12" stroke-width="2"/><line x1="{xr:.0f}" y1="{y}" x2="3840" y2="{y}" stroke="{ink}" stroke-opacity=".12" stroke-width="2"/>')
        S.add(f'<circle cx="{xl - 26:.0f}" cy="{y + 20}" r="5" fill="{ink}" fill-opacity=".3"/><circle cx="{xr + 26:.0f}" cy="{y + 20}" r="5" fill="{ink}" fill-opacity=".3"/>')
    for x in range(680, 3160, 64):                                      # top band: status segments
        S.add(f'<rect x="{x}" y="222" width="38" height="10" fill="{ink}" fill-opacity="{.5 if (x // 64) % 6 == 0 else .14}"/>')
    for x in range(660, 3200, 300):                                     # panel seams + screws on the sill
        S.add(f'<line x1="{x}" y1="1930" x2="{x}" y2="2160" stroke="{ink}" stroke-opacity=".12" stroke-width="2"/>'
              f'<circle cx="{x + 20}" cy="1960" r="4" fill="{ink}" fill-opacity=".25"/>')
    S.add(f'<rect x="1600" y="2010" width="640" height="70" rx="6" fill="none" stroke="{ink}" stroke-opacity=".3" stroke-width="2"/>')
    for i in range(10):
        S.add(f'<circle cx="{1640 + i*62}" cy="2045" r="9" fill="{"#5dffc8" if i % 4 else "#ffb347"}" fill-opacity="{.7 if i % 3 else .25}"/>')
    S.text(640, 120, "OBSERVATION RING  ·  DECK 3", fill=ink, fill_opacity=".8", font_size="36", letter_spacing="8", font_family=UI, font_weight="600")
    S.label("orbit", "ORBIT {days}{night}", 3200, 120, fill=ink, fill_opacity=".8", font_size="36", letter_spacing="8",
            text_anchor="end", font_family=UI, font_weight="600")
    S.text(700, 2130, "HULL INTEGRITY NOMINAL", fill=ink, fill_opacity=".45", font_size="26", letter_spacing="6", font_family=UI)
    # reflections on the glass
    S.add('<polygon points="900,260 1300,260 600,1920 200,1920" fill="url(#glass)"/><polygon points="1420,260 1500,260 820,1920 740,1920" fill="url(#glass)"/>')
    return S, (1920, 980), {"days": "1", "night": ""}


# =====================================================================================================================
# 3. The archive: his private library at night, a tall window at the far end
# =====================================================================================================================
def archive():
    S = Scene("archive", "The archive", 11)
    VX, VY = 1920, 900                                     # vanishing point
    SERIF = "'Cormorant Garamond',Georgia,serif"
    S.d('<linearGradient id="wallg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#17120c"/><stop offset="1" stop-color="#0c0906"/></linearGradient>'
        '<radialGradient id="moonw" cx="50%" cy="45%" r="60%"><stop offset="0" stop-color="#bcd6ff" stop-opacity=".55"/><stop offset="1" stop-color="#3a4d6e" stop-opacity=".15"/></radialGradient>'
        '<linearGradient id="shaft" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#b8d2ff" stop-opacity=".16"/><stop offset="1" stop-color="#b8d2ff" stop-opacity="0"/></linearGradient>'
        '<radialGradient id="lampg" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#ffd38a" stop-opacity=".55"/><stop offset="1" stop-color="#ffd38a" stop-opacity="0"/></radialGradient>'
        '<radialGradient id="pend" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#ffcf8a" stop-opacity=".35"/><stop offset="1" stop-color="#ffcf8a" stop-opacity="0"/></radialGradient>'
        '<filter id="b6"><feGaussianBlur stdDeviation="6"/></filter><filter id="b30"><feGaussianBlur stdDeviation="30"/></filter>'
        '<linearGradient id="deskg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3a2a1a"/><stop offset="1" stop-color="#1a120b"/></linearGradient>')
    S.add(f'<rect width="{W}" height="{H}" fill="url(#wallg)"/>')
    # far wall
    fx0, fx1, fy0, fy1 = 1500, 2340, 380, 1260
    S.add(f'<rect x="{fx0}" y="{fy0}" width="{fx1-fx0}" height="{fy1-fy0}" fill="#120e0a"/>')
    # the tall arched window
    wx0, wx1, wy0, wy1 = 1700, 2140, 470, 1180
    arch = f"M {wx0} {wy1} V {wy0 + 220} A {(wx1-wx0)/2} 220 0 0 1 {wx1} {wy0 + 220} V {wy1} Z"
    S.add(f'<path d="{arch}" fill="url(#moonw)"/>')
    for x in range(wx0 + 110, wx1, 110):
        S.add(f'<line x1="{x}" y1="{wy0 + 40}" x2="{x}" y2="{wy1}" stroke="#2a2016" stroke-width="10"/>')
    for y in range(wy0 + 260, wy1, 150):
        S.add(f'<line x1="{wx0}" y1="{y}" x2="{wx1}" y2="{y}" stroke="#2a2016" stroke-width="10"/>')
    S.add(f'<path d="{arch}" fill="none" stroke="#5a4630" stroke-width="22"/>')
    S.add(f'<circle cx="2010" cy="640" r="46" fill="#eef4ff" fill-opacity=".85" filter="url(#b6)"/>')
    # ceiling and floor planes
    S.add(f'<polygon points="0,0 {W},0 {fx1},{fy0} {fx0},{fy0}" fill="#0d0a07"/>')
    for i in range(1, 9):                                           # coffers
        t = i / 9
        x0, x1 = fx0 * t, W - (W - fx1) * t
        y = fy0 * t
        S.add(f'<line x1="{x0:.0f}" y1="{y:.0f}" x2="{x1:.0f}" y2="{y:.0f}" stroke="#4a3a28" stroke-opacity=".35" stroke-width="2"/>')
    for k in range(-6, 7):
        S.add(f'<line x1="{VX + k*320}" y1="0" x2="{VX + k*(fx1-fx0)/12:.0f}" y2="{fy0}" stroke="#4a3a28" stroke-opacity=".25" stroke-width="2"/>')
    S.add(f'<polygon points="0,{H} {W},{H} {fx1},{fy1} {fx0},{fy1}" fill="#120d08"/>')
    for k in range(-14, 15):                                        # floor boards
        S.add(f'<line x1="{VX + k*280}" y1="{H}" x2="{VX + k*(fx1-fx0)/28:.0f}" y2="{fy1}" stroke="#2c2117" stroke-width="2"/>')
    # rug in perspective
    def floor_pt(u, d):           # u -1..1 across, d 0 (near) .. 1 (far wall)
        y = H + (fy1 - H) * d
        half = (W / 2) * (1 - d) + ((fx1 - fx0) / 2) * d
        return VX + u * half, y
    rug = [floor_pt(-.42, .1), floor_pt(.42, .1), floor_pt(.42, .62), floor_pt(-.42, .62)]
    S.add(f'<polygon points="{poly(rug)}" fill="#3a1f1a" fill-opacity=".8" stroke="#8a5a3a" stroke-opacity=".6" stroke-width="3"/>')
    rug2 = [floor_pt(-.36, .16), floor_pt(.36, .16), floor_pt(.36, .56), floor_pt(-.36, .56)]
    S.add(f'<polygon points="{poly(rug2)}" fill="none" stroke="#c8a46a" stroke-opacity=".35" stroke-width="2"/>')
    for i in range(1, 6):
        a, b = floor_pt(-.36 + i * .12, .16), floor_pt(-.36 + i * .12, .56)
        S.add(f'<line x1="{a[0]:.0f}" y1="{a[1]:.0f}" x2="{b[0]:.0f}" y2="{b[1]:.0f}" stroke="#c8a46a" stroke-opacity=".12" stroke-width="2"/>')
    # moonlight shafts onto the floor
    S.add(f'<polygon points="{wx0},{wy1} {wx1},{wy1} 2900,2160 940,2160" fill="url(#shaft)"/>')
    S.add(f'<polygon points="{wx0 + 110},{wy1} {wx0 + 220},{wy1} 1660,2160 1380,2160" fill="url(#shaft)"/>')
    # ---- shelf walls, left and right, books in perspective
    palette = ["#3a2618", "#4a2e1c", "#2a3a4a", "#1e2c3a", "#5a3a20", "#2e2418", "#4a3a26", "#3a1e1e", "#26322a", "#5e4a2a"]
    def wall(side):
        near_x = 0 if side < 0 else W
        far_x = fx0 if side < 0 else fx1
        S.add(f'<polygon points="{near_x},0 {far_x},{fy0} {far_x},{fy1} {near_x},{H}" fill="#140f0a"/>')
        rows = 9
        for r in range(rows + 1):
            yn, yf = r * H / rows, fy0 + r * (fy1 - fy0) / rows
            S.add(f'<line x1="{near_x}" y1="{yn:.0f}" x2="{far_x}" y2="{yf:.0f}" stroke="#6b5235" stroke-opacity=".75" stroke-width="{max(2, 14 - r):.0f}"/>')
        for r in range(rows):
            t = 0.0
            while t < .97:
                # depth t: 0 at the near edge, 1 at the far wall (perspective-spaced)
                z = 1 / (1 + 6 * t)
                bw = (random.choice((.006, .008, .010, .012, .016)) * z * 2.4)
                t2 = t + bw
                def P(tt, rr):
                    x = near_x + (far_x - near_x) * (1 - 1 / (1 + 6 * tt)) * 7 / 6
                    yn, yf = rr * H / rows, fy0 + rr * (fy1 - fy0) / rows
                    y = yn + (yf - yn) * (x - near_x) / (far_x - near_x)
                    return x, y
                xa, ya_top = P(t, r)
                xb, yb_top = P(t2, r)
                _, ya_bot = P(t, r + 1)
                _, yb_bot = P(t2, r + 1)
                hfrac = random.uniform(.62, .92)
                top_a = ya_bot - (ya_bot - ya_top) * hfrac
                top_b = yb_bot - (yb_bot - yb_top) * hfrac
                col = random.choice(palette)
                S.add(f'<polygon points="{xa:.1f},{top_a:.1f} {xb:.1f},{top_b:.1f} {xb:.1f},{yb_bot - 3:.1f} {xa:.1f},{ya_bot - 3:.1f}" fill="{col}" stroke="#000" stroke-opacity=".35"/>')
                if random.random() < .35:
                    for k in (.22, .3):
                        ya = top_a + (ya_bot - top_a) * k
                        yb = top_b + (yb_bot - top_b) * k
                        S.add(f'<line x1="{xa:.1f}" y1="{ya:.1f}" x2="{xb:.1f}" y2="{yb:.1f}" stroke="#c8a46a" stroke-opacity=".5" stroke-width="{max(1, 3*z):.1f}"/>')
                t = t2 + random.choice((0, 0, .001, .004)) * z
        # end pillar
        S.add(f'<line x1="{far_x}" y1="{fy0}" x2="{far_x}" y2="{fy1}" stroke="#6b5235" stroke-opacity=".7" stroke-width="6"/>')
    wall(-1)
    wall(1)
    # rolling ladder on the right wall
    for off in (0, 70):
        S.add(f'<line x1="{3040 + off}" y1="140" x2="{3260 + off}" y2="2080" stroke="#8a6a44" stroke-width="12"/>')
    for i in range(1, 15):
        t = i / 15
        S.add(f'<line x1="{3040 + 220*t:.0f}" y1="{140 + 1940*t:.0f}" x2="{3110 + 220*t:.0f}" y2="{140 + 1940*t:.0f}" stroke="#8a6a44" stroke-width="8"/>')
    # pendant lamps
    for x, y, L in ((1240, 520, 520), (2600, 520, 520), (1920, 300, 300)):
        S.add(f'<line x1="{x}" y1="0" x2="{x}" y2="{y - 40}" stroke="#5a4630" stroke-width="3"/>')
        S.add(f'<circle cx="{x}" cy="{y + 40}" r="320" fill="url(#pend)"/>')
        S.add(f'<path d="M {x - 60} {y + 20} Q {x} {y - 50} {x + 60} {y + 20} Z" fill="#4a3a20" stroke="#c8a46a" stroke-opacity=".5" stroke-width="2"/>')
        S.add(f'<ellipse cx="{x}" cy="{y + 22}" rx="50" ry="10" fill="#ffd38a" fill-opacity=".8"/>')
    # dust in the moonlight
    for _ in range(260):
        x, y = random.uniform(1000, 2800), random.uniform(1200, 2100)
        S.add(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{random.choice((1, 1.5, 2))}" fill="#dbe8ff" fill-opacity="{random.uniform(.08, .3):.2f}"/>')
    # ---- the reading desk in front
    S.add(f'<polygon points="760,1840 3080,1840 3260,2160 580,2160" fill="url(#deskg)" stroke="#8a6a44" stroke-opacity=".6" stroke-width="3"/>')
    S.add(f'<line x1="760" y1="1840" x2="3080" y2="1840" stroke="#c8a46a" stroke-opacity=".5" stroke-width="3"/>')
    # banker's lamp, left
    S.add(f'<circle cx="1060" cy="1760" r="380" fill="url(#lampg)"/>')
    S.add(f'<path d="M 960 1730 Q 1060 1650 1160 1730 Z" fill="#1d4a2c" stroke="#7fd69a" stroke-opacity=".4" stroke-width="2"/>')
    S.add(f'<ellipse cx="1060" cy="1732" rx="100" ry="10" fill="#ffe2a8" fill-opacity=".9"/>')
    S.add(f'<line x1="1060" y1="1740" x2="1060" y2="1880" stroke="#c8a46a" stroke-width="7"/><ellipse cx="1060" cy="1886" rx="70" ry="14" fill="#c8a46a" fill-opacity=".8"/>')
    # open book in the middle of the desk
    S.add(f'<path d="M 1700 1930 Q 1810 1890 1915 1925 L 1915 2010 Q 1810 1975 1690 2010 Z" fill="#e6d6b4" fill-opacity=".85"/>'
          f'<path d="M 2140 1930 Q 2030 1890 1925 1925 L 1925 2010 Q 2030 1975 2150 2010 Z" fill="#efe1c2" fill-opacity=".85"/>')
    for i in range(6):
        S.add(f'<line x1="{1720}" y1="{1940 + i*11}" x2="{1895}" y2="{1935 + i*11}" stroke="#5a4630" stroke-opacity=".35" stroke-width="2"/>'
              f'<line x1="{1945}" y1="{1935 + i*11}" x2="{2120}" y2="{1940 + i*11}" stroke="#5a4630" stroke-opacity=".35" stroke-width="2"/>')
    # card catalogue, right
    cx0, cy0 = 2520, 1560
    S.add(f'<rect x="{cx0}" y="{cy0}" width="420" height="300" fill="#3a2614" stroke="#8a6a44" stroke-width="3"/>')
    for r in range(4):
        for c in range(4):
            x, y = cx0 + 14 + c * 100, cy0 + 14 + r * 70
            S.add(f'<rect x="{x}" y="{y}" width="92" height="62" fill="#4a3018" stroke="#2a1a0c" stroke-width="2"/>')
            S.add(f'<rect x="{x + 30}" y="{y + 12}" width="32" height="14" fill="#e6d6b4" fill-opacity=".7"/>')
            S.add(f'<path d="M {x + 34} {y + 40} q 12 10 24 0" fill="none" stroke="#d8b878" stroke-width="4"/>')
    # index cards fanned on the desk
    for i in range(5):
        S.add(f'<rect x="{2280 + i*14}" y="{1900 - i*6}" width="180" height="110" fill="#efe1c2" fill-opacity=".75" transform="rotate({-8 + i*4} 2370 1950)"/>')
    # the brass plate on the desk front (text comes from his memory)
    S.add(f'<rect x="1320" y="2050" width="1200" height="74" rx="8" fill="#6b5232" stroke="#d8b878" stroke-opacity=".6" stroke-width="2"/>')
    S.label("plate", "The catalogue: {memories} cards  ·  {routines} routines  ·  kept since {since}", 1920, 2098,
            fill="#f3e2b8", fill_opacity=".85", font_size="34", text_anchor="middle", font_style="italic", font_family=SERIF)
    return S, (1920, 830), {"memories": "0", "routines": "0", "since": "today"}


# =====================================================================================================================
# 4. Listening post: a signals room. Your voice, the house and the network are traces on his instruments.
# =====================================================================================================================
def signal():
    S = Scene("signal", "Listening post", 5)
    c, amber, bg = "#5dffc8", "#ffcf5d", "#03100d"
    MONO = "'Share Tech Mono','Cascadia Mono',Consolas,monospace"
    S.d(f'<pattern id="grille" width="12" height="12" patternUnits="userSpaceOnUse"><circle cx="6" cy="6" r="2" fill="#000" fill-opacity=".5"/></pattern>'
        f'<pattern id="scan" width="6" height="6" patternUnits="userSpaceOnUse"><rect width="6" height="2" fill="#000" fill-opacity=".22"/></pattern>'
        f'<radialGradient id="crt" cx="50%" cy="50%" r="65%"><stop offset="0" stop-color="#0b2a22"/><stop offset="1" stop-color="#03120e"/></radialGradient>'
        f'<radialGradient id="glow" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="{c}" stop-opacity=".18"/><stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient>'
        '<filter id="ph"><feGaussianBlur stdDeviation="2.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
        '<linearGradient id="metal" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#14201c"/><stop offset="1" stop-color="#0a1210"/></linearGradient>')
    S.add(f'<rect width="{W}" height="{H}" fill="{bg}"/>')
    S.add(f'<rect width="{W}" height="{H}" fill="url(#metal)"/>')
    def screw(x, y):
        S.add(f'<circle cx="{x}" cy="{y}" r="9" fill="#24342e" stroke="#000" stroke-opacity=".5"/><line x1="{x-6}" y1="{y-2}" x2="{x+6}" y2="{y+2}" stroke="#000" stroke-opacity=".6" stroke-width="2"/>')
    def bezel(x, y, w, h, title=None):
        S.add(f'<rect x="{x-18}" y="{y-18}" width="{w+36}" height="{h+36}" rx="18" fill="#0e1a17" stroke="#2a3c36" stroke-width="3"/>')
        S.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="22" fill="url(#crt)" stroke="#000" stroke-width="4"/>')
        for sx, sy in ((x - 6, y - 6), (x + w + 6, y - 6), (x - 6, y + h + 6), (x + w + 6, y + h + 6)):
            screw(sx, sy)
        if title:
            S.text(x, y - 32, title, fill=c, fill_opacity=".55", font_size="24", letter_spacing="4", font_family=MONO)
    # ---- the big scope in the middle (his ring sits on it)
    cx, cy, R = 1920, 1000, 560
    S.add(f'<circle cx="{cx}" cy="{cy}" r="{R + 70}" fill="#0e1a17" stroke="#2a3c36" stroke-width="4"/>')
    S.add(f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="url(#crt)" stroke="#000" stroke-width="6"/>')
    S.add(f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="url(#glow)"/>')
    for k in range(1, 6):
        S.add(f'<circle cx="{cx}" cy="{cy}" r="{R*k/6:.0f}" fill="none" stroke="{c}" stroke-opacity=".12" stroke-width="1.6"/>')
    for k in range(12):
        a = k * math.pi / 6
        S.add(f'<line x1="{cx}" y1="{cy}" x2="{f(cx + R*math.cos(a))}" y2="{f(cy + R*math.sin(a))}" stroke="{c}" stroke-opacity=".08" stroke-width="1.4"/>')
    for d in range(0, 360, 3):
        a = math.radians(d)
        L = 22 if d % 30 == 0 else 10
        S.add(f'<line x1="{f(cx + (R+8)*math.cos(a))}" y1="{f(cy + (R+8)*math.sin(a))}" x2="{f(cx + (R+8+L)*math.cos(a))}" y2="{f(cy + (R+8+L)*math.sin(a))}" stroke="{c}" stroke-opacity=".45" stroke-width="1.6"/>')
    for d in range(0, 360, 30):
        a = math.radians(d - 90)
        S.text(cx + (R + 52) * math.cos(a), cy + (R + 52) * math.sin(a) + 9, f"{d:03d}", fill=c, fill_opacity=".55", font_size="24", text_anchor="middle", font_family=MONO)
    S.add(f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="url(#scan)"/>')
    # ---- left bank: waterfall, vectorscope, level history
    bezel(240, 260, 1000, 420, "CH1  VOICE  ·  WATERFALL")
    cols = ["#03120e", "#0a3b2c", "#118a62", "#34d39a", "#b8ffe3", "#ffcf5d"]
    for row in range(0, 420, 12):
        for col in range(0, 1000, 16):
            v = abs(math.sin(col / 70 + row / 90)) * .6 + random.uniform(0, .45) * (1 - row / 600)
            v *= .4 + .6 * math.exp(-((col - 500) / 260) ** 2)
            i = min(len(cols) - 1, int(v * len(cols)))
            if i:
                S.add(f'<rect x="{240 + col}" y="{260 + row}" width="16" height="12" fill="{cols[i]}" fill-opacity=".85"/>')
    bezel(240, 820, 470, 420, "VECTOR")
    pts = []
    for i in range(0, 900):
        t = i / 900 * 2 * math.pi
        pts.append((475 + 190 * math.sin(3 * t + .4) * (0.9 + .1*math.sin(11*t)), 1030 + 170 * math.sin(2 * t)))
    S.add(f'<polyline points="{poly(pts)}" fill="none" stroke="{c}" stroke-opacity=".8" stroke-width="2.2" filter="url(#ph)"/>')
    S.add(f'<path d="M 475 840 V 1220 M 260 1030 H 690" stroke="{c}" stroke-opacity=".15"/>')
    bezel(770, 820, 470, 420, "LEVEL  60s")
    pts = [(770 + i * 4.7, 1180 - (abs(math.sin(i / 9)) * 180 + random.uniform(0, 60)) * (0.4 + .6 * (i % 37 > 8))) for i in range(100)]
    S.add(f'<polyline points="{poly(pts)}" fill="none" stroke="{c}" stroke-opacity=".85" stroke-width="2.4" filter="url(#ph)"/>')
    for y in range(870, 1240, 60):
        S.add(f'<line x1="770" y1="{y}" x2="1240" y2="{y}" stroke="{c}" stroke-opacity=".1"/>')
    # ---- right bank: frequency dial, VU meters, switches
    bezel(2600, 260, 1000, 420, "BAND")
    S.d('<clipPath id="bandc"><rect x="2600" y="260" width="1000" height="420" rx="22"/></clipPath>')
    S.add('<g clip-path="url(#bandc)">')
    dx, dy, dr = 3100, 1060, 700
    S.add(f'<circle cx="{dx}" cy="{dy}" r="{dr}" fill="none" stroke="{c}" stroke-opacity=".5" stroke-width="2"/>')
    for i in range(0, 121):
        a = math.radians(-125 + i * 0.58)
        L = 40 if i % 10 == 0 else 18
        S.add(f'<line x1="{f(dx + dr*math.cos(a))}" y1="{f(dy + dr*math.sin(a))}" x2="{f(dx + (dr-L)*math.cos(a))}" y2="{f(dy + (dr-L)*math.sin(a))}" stroke="{c}" stroke-opacity=".55" stroke-width="1.8"/>')
    for i, name in enumerate(("VOICE", "HOUSE", "NET", "GAME", "MAIL", "NEWS", "MISC")):
        a = math.radians(-122 + i * 11)
        S.text(dx + (dr - 80) * math.cos(a), dy + (dr - 80) * math.sin(a) + 8, name, fill=c, fill_opacity=".7", font_size="24", text_anchor="middle", font_family=MONO)
    a = math.radians(-100)
    S.add(f'<line x1="{dx}" y1="{dy}" x2="{f(dx + (dr + 40)*math.cos(a))}" y2="{f(dy + (dr + 40)*math.sin(a))}" stroke="{amber}" stroke-width="4"/>')
    S.add('</g>')
    S.add(f'<rect x="2600" y="260" width="1000" height="420" rx="22" fill="url(#scan)"/>')
    for k, (vx, nm) in enumerate(((2600, "L"), (3135, "R"))):
        bezel(vx, 820, 465, 300, f"VU  {nm}")
        mx, my = vx + 232, 1100
        S.add(f'<path d="M {mx-180} {my-120} A 220 220 0 0 1 {mx+180} {my-120}" fill="none" stroke="{c}" stroke-opacity=".6" stroke-width="2"/>')
        for i in range(21):
            a = math.radians(-125 + i * 3.5)
            L = 22 if i % 5 == 0 else 12
            col = amber if i > 15 else c
            S.add(f'<line x1="{f(mx + 220*math.cos(a))}" y1="{f(my + 220*math.sin(a) - 4)}" x2="{f(mx + (220-L)*math.cos(a))}" y2="{f(my + (220-L)*math.sin(a) - 4)}" stroke="{col}" stroke-opacity=".7" stroke-width="2"/>')
        a = math.radians(-112 + k * 9)
        S.add(f'<line x1="{mx}" y1="{my}" x2="{f(mx + 200*math.cos(a))}" y2="{f(my + 200*math.sin(a))}" stroke="#e8fff6" stroke-opacity=".85" stroke-width="3"/>')
        S.add(f'<circle cx="{mx}" cy="{my}" r="12" fill="#1a2a24" stroke="{c}" stroke-opacity=".5"/>')
    for i in range(8):                                                     # toggle switches + lamps
        x = 2640 + i * 118
        S.add(f'<rect x="{x}" y="1230" width="56" height="96" rx="10" fill="#0e1a17" stroke="#2a3c36" stroke-width="3"/>')
        up = i % 3 != 1
        S.add(f'<line x1="{x+28}" y1="1278" x2="{x+28}" y2="{1246 if up else 1310}" stroke="#c8d8d2" stroke-width="10" stroke-linecap="round"/>')
        S.add(f'<circle cx="{x+28}" cy="1360" r="11" fill="{c if up else "#1a2a24"}" fill-opacity="{.85 if up else 1}"/>')
        S.text(x + 28, 1410, ("MIC", "AEC", "VAD", "LOG", "NET", "HUE", "BOT", "AUX")[i], fill=c, fill_opacity=".55", font_size="20", text_anchor="middle", font_family=MONO)
    # ---- patch bay at the bottom, with cables
    S.add(f'<rect x="200" y="1600" width="3440" height="300" rx="14" fill="#0b1513" stroke="#2a3c36" stroke-width="3"/>')
    S.add(f'<rect x="200" y="1600" width="3440" height="300" rx="14" fill="url(#grille)" fill-opacity=".4"/>')
    jacks = []
    for row in range(2):
        for i in range(40):
            x, y = 290 + i * 82, 1680 + row * 130
            jacks.append((x, y))
            S.add(f'<circle cx="{x}" cy="{y}" r="20" fill="#020806" stroke="#4a5c56" stroke-width="4"/><circle cx="{x}" cy="{y}" r="7" fill="#000"/>')
            if row == 0 and i % 4 == 0:
                S.text(x + 123, y - 34, f"{i // 4 + 1:02d}", fill=c, fill_opacity=".45", font_size="20", text_anchor="middle", font_family=MONO)
    for col, (a, b) in zip(("#ff6a4d", "#ffcf5d", "#5dffc8", "#6aa8ff", "#ff6a4d", "#e8fff6", "#ffcf5d"),
                           ((3, 52), (9, 47), (14, 66), (21, 58), (30, 71), (36, 44), (61, 18))):
        (x1, y1), (x2, y2) = jacks[a], jacks[b]
        sag = 160 + abs(x2 - x1) * .12
        S.add(f'<path d="M {x1} {y1} C {x1} {y1 + sag}, {x2} {y2 + sag}, {x2} {y2}" fill="none" stroke="#000" stroke-opacity=".5" stroke-width="16"/>'
              f'<path d="M {x1} {y1} C {x1} {y1 + sag}, {x2} {y2 + sag}, {x2} {y2}" fill="none" stroke="{col}" stroke-opacity=".75" stroke-width="10"/>')
        for x, y in ((x1, y1), (x2, y2)):
            S.add(f'<circle cx="{x}" cy="{y}" r="16" fill="#c8d8d2"/>')
    # top strip: channel names (live readings come from deskfacts.py)
    S.add(f'<rect x="0" y="0" width="{W}" height="150" fill="#0a1411"/><line x1="0" y1="150" x2="{W}" y2="150" stroke="{c}" stroke-opacity=".3" stroke-width="2"/>')
    S.label("ch", "CH1 VOICE      CH2 HOUSE {house}      CH3 NETWORK {net}", 240, 96, fill=c, fill_opacity=".75", font_size="36", font_family=MONO)
    S.text(3100, 96, "LISTENING POST  ·  J.", fill=c, fill_opacity=".5", font_size="30", text_anchor="end", font_family=MONO)
    S.add(f'<rect width="{W}" height="{H}" fill="url(#scan)" opacity=".5"/>')
    return S, (cx, cy), {"house": "", "net": ""}


# =====================================================================================================================
# 5. Cartographer: a sea chart of your digital island; the places are named after the apps you live in
# =====================================================================================================================
def chart():
    S = Scene("chart", "Cartographer", 9)
    ink, accent, sea = "#9fe3d6", "#ff9f5a", "#071a1e"
    SERIF = "Fraunces,'Cambria',Georgia,serif"
    S.d('<radialGradient id="seag" cx="45%" cy="50%" r="70%"><stop offset="0" stop-color="#0c2a2f"/><stop offset="1" stop-color="#051114"/></radialGradient>'
        f'<pattern id="stip" width="18" height="18" patternUnits="userSpaceOnUse"><circle cx="4" cy="4" r="1.4" fill="{ink}" fill-opacity=".35"/><circle cx="13" cy="12" r="1.1" fill="{ink}" fill-opacity=".25"/></pattern>'
        '<filter id="b2"><feGaussianBlur stdDeviation="2"/></filter>')
    S.add(f'<rect width="{W}" height="{H}" fill="url(#seag)"/>')
    for _ in range(3000):
        S.add(f'<circle cx="{random.uniform(0, W):.0f}" cy="{random.uniform(0, H):.0f}" r="1" fill="{ink}" fill-opacity="{random.uniform(.02, .06):.2f}"/>')
    # graticule
    for x in range(160, W, 400):
        S.add(f'<line x1="{x}" y1="100" x2="{x}" y2="{H-100}" stroke="{ink}" stroke-opacity=".08" stroke-width="1.6"/>')
    for y in range(140, H, 400):
        S.add(f'<line x1="100" y1="{y}" x2="{W-100}" y2="{y}" stroke="{ink}" stroke-opacity=".08" stroke-width="1.6"/>')
    # compass rose and its rhumb lines
    rx, ry = 3060, 560
    for k in range(32):
        a = k * math.pi / 16
        S.add(f'<line x1="{rx}" y1="{ry}" x2="{f(rx + 4400*math.cos(a))}" y2="{f(ry + 4400*math.sin(a))}" stroke="{accent if k % 8 == 0 else ink}" '
              f'stroke-opacity="{.16 if k % 8 == 0 else .06}" stroke-width="1.6"/>')
    # the island: shallows, then rising contour bands
    cx, cy = 1800, 1100
    _, phases = noise_loop(0, 0, 1)
    def ring(r, ex=0):
        pts, _ = noise_loop(cx, cy, r, 1.45, .9, ((2, .1), (3, .13), (5, .07), (9, .04), (17, .015)), phases[:4] + [1.3], step=2)
        return pts
    S.add(f'<polygon points="{poly(ring(860))}" fill="url(#stip)" opacity=".7"/>')
    S.add(f'<polygon points="{poly(ring(800))}" fill="#0f3a3c" fill-opacity=".55" stroke="{ink}" stroke-opacity=".25" stroke-dasharray="6 10" stroke-width="2"/>')
    tints = ["#18413a", "#1f4c40", "#285846", "#33644c", "#3e7052", "#4a7c58", "#58875f", "#689266", "#7a9d6e", "#8ea878", "#a3b382", "#b8bf8e"]
    for k, r in enumerate(range(740, 60, -56)):
        S.add(f'<polygon points="{poly(ring(r))}" fill="{tints[min(k, len(tints)-1)]}" fill-opacity=".55" stroke="{ink}" '
              f'stroke-opacity="{.6 if k == 0 else .32 if k % 3 == 0 else .16}" stroke-width="{3 if k == 0 else 1.6}"/>')
    # islets
    for ix, iy, ir in ((3000, 1500, 120), (2900, 1680, 60), (700, 1700, 90), (980, 560, 70)):
        pts, _ = noise_loop(ix, iy, ir, 1.3, .9)
        S.add(f'<polygon points="{poly(pts)}" fill="#1f4c40" fill-opacity=".7" stroke="{ink}" stroke-opacity=".55" stroke-width="2"/>')
        pts, _ = noise_loop(ix, iy, ir + 30, 1.3, .9)
        S.add(f'<polygon points="{poly(pts)}" fill="none" stroke="{ink}" stroke-opacity=".2" stroke-dasharray="5 9" stroke-width="2"/>')
    # rivers from the peak
    for ang in (-2.2, -.4, 1.1, 2.6):
        pts = []
        for s in range(0, 41):
            r = 70 + s * 17
            a = ang + .16 * math.sin(s * .55 + ang) + .05 * math.sin(s * 1.9)
            pts.append((cx + r * 1.45 * math.cos(a), cy + r * .9 * math.sin(a)))
        d = f"M {pts[0][0]:.0f} {pts[0][1]:.0f}" + "".join(
            f" Q {pts[i][0]:.0f} {pts[i][1]:.0f} {(pts[i][0] + pts[i+1][0]) / 2:.0f} {(pts[i][1] + pts[i+1][1]) / 2:.0f}" for i in range(1, len(pts) - 1))
        S.add(f'<path d="{d}" fill="none" stroke="#6ad0ff" stroke-opacity=".55" stroke-width="3" stroke-linecap="round"/>')
    # hachures round the summit
    for i in range(0, 360, 6):
        a = math.radians(i)
        r0 = 170 + 20 * math.sin(5 * a)
        S.add(f'<line x1="{f(cx + r0*1.45*math.cos(a))}" y1="{f(cy + r0*.9*math.sin(a))}" x2="{f(cx + (r0+40)*1.45*math.cos(a))}" '
              f'y2="{f(cy + (r0+40)*.9*math.sin(a))}" stroke="#20302a" stroke-opacity=".55" stroke-width="2"/>')
    # soundings in the sea
    for _ in range(140):
        x, y = random.uniform(160, W - 160), random.uniform(180, H - 180)
        if ((x - cx) / 1450) ** 2 + ((y - cy) / 860) ** 2 < 1 or (abs(x - rx) < 300 and abs(y - ry) < 300):
            continue
        S.text(x, y, str(random.choice((7, 9, 12, 14, 18, 22, 27, 31, 36, 44, 52))), fill=ink, fill_opacity=".28", font_size="22", font_style="italic", font_family=SERIF)
    # the route, waypoints, and where he is
    route = [(1150, 1540), (1350, 1420), (1560, 1290), (1800, 1100), (2120, 960), (2480, 880), (2860, 980)]
    S.add(f'<polyline points="{poly(route)}" fill="none" stroke="{accent}" stroke-opacity=".8" stroke-width="4" stroke-dasharray="14 14" stroke-linecap="round"/>')
    for x, y in route:
        S.add(f'<circle cx="{x}" cy="{y}" r="9" fill="{sea}" stroke="{accent}" stroke-width="3"/>')
    # compass rose (drawn last so it sits on top of its lines)
    S.add(f'<circle cx="{rx}" cy="{ry}" r="260" fill="#071a1e" fill-opacity=".85" stroke="{ink}" stroke-opacity=".5" stroke-width="2"/>')
    S.add(f'<circle cx="{rx}" cy="{ry}" r="230" fill="none" stroke="{ink}" stroke-opacity=".35" stroke-width="1.6"/>')
    for d in range(0, 360, 2):
        a = math.radians(d)
        L = 22 if d % 10 == 0 else 10
        S.add(f'<line x1="{f(rx + 258*math.cos(a))}" y1="{f(ry + 258*math.sin(a))}" x2="{f(rx + (258-L)*math.cos(a))}" y2="{f(ry + (258-L)*math.sin(a))}" stroke="{ink}" stroke-opacity=".45" stroke-width="1.4"/>')
    for k in range(16):
        a = k * math.pi / 8 - math.pi / 2
        L = 220 if k % 4 == 0 else 150 if k % 2 == 0 else 100
        w = 26 if k % 4 == 0 else 18 if k % 2 == 0 else 12
        tip = (rx + L * math.cos(a), ry + L * math.sin(a))
        l = (rx + w * math.cos(a - math.pi / 2), ry + w * math.sin(a - math.pi / 2))
        r = (rx + w * math.cos(a + math.pi / 2), ry + w * math.sin(a + math.pi / 2))
        S.add(f'<polygon points="{poly([(rx, ry), l, tip])}" fill="{ink}" fill-opacity="{.75 if k % 4 == 0 else .45}"/>'
              f'<polygon points="{poly([(rx, ry), r, tip])}" fill="#071a1e" stroke="{ink}" stroke-opacity=".6" stroke-width="1.4"/>')
    S.add(f'<circle cx="{rx}" cy="{ry}" r="16" fill="{accent}"/>')
    for k, nm in enumerate(("N", "E", "S", "W")):
        a = k * math.pi / 2 - math.pi / 2
        S.text(rx + 296 * math.cos(a), ry + 296 * math.sin(a) + 14, nm, fill=ink, fill_opacity=".85", font_size="40", text_anchor="middle", font_family=SERIF)
    # neatline with the black-and-white degree border
    S.add(f'<rect x="100" y="100" width="{W-200}" height="{H-200}" fill="none" stroke="{ink}" stroke-opacity=".6" stroke-width="3"/>')
    S.add(f'<rect x="70" y="70" width="{W-140}" height="{H-140}" fill="none" stroke="{ink}" stroke-opacity=".4" stroke-width="1.6"/>')
    for i, x in enumerate(range(100, W - 100, 80)):
        if i % 2 == 0:
            S.add(f'<rect x="{x}" y="70" width="80" height="30" fill="{ink}" fill-opacity=".35"/><rect x="{x}" y="{H-100}" width="80" height="30" fill="{ink}" fill-opacity=".35"/>')
    for i, y in enumerate(range(100, H - 100, 80)):
        if i % 2 == 0:
            S.add(f'<rect x="70" y="{y}" width="30" height="80" fill="{ink}" fill-opacity=".35"/><rect x="{W-100}" y="{y}" width="30" height="80" fill="{ink}" fill-opacity=".35"/>')
    for i, x in enumerate(range(160, W - 100, 400)):
        S.text(x, 56, f"{12 + i}°", fill=ink, fill_opacity=".6", font_size="26", text_anchor="middle", font_family=SERIF)
    # sea names
    S.text(500, 420, "THE QUIET SEA", fill=ink, fill_opacity=".4", font_size="40", letter_spacing="22", font_style="italic", font_family=SERIF)
    S.text(2600, 1980, "Bay of Unread", fill=ink, fill_opacity=".45", font_size="36", font_style="italic", font_family=SERIF)
    S.text(400, 1180, "Deep Backlog", fill=ink, fill_opacity=".35", font_size="34", font_style="italic", font_family=SERIF, transform="rotate(-8 400 1180)")
    # cartouche and scale bar
    S.add(f'<rect x="200" y="1760" width="900" height="280" fill="#071a1e" fill-opacity=".9" stroke="{ink}" stroke-opacity=".55" stroke-width="2"/>')
    S.add(f'<rect x="216" y="1776" width="868" height="248" fill="none" stroke="{ink}" stroke-opacity=".3" stroke-width="1.4"/>')
    S.text(650, 1850, "A Chart of the Island", fill=ink, fill_opacity=".9", font_size="52", text_anchor="middle", font_style="italic", font_family=SERIF)
    S.text(650, 1900, "surveyed and kept by J.  ·  soundings in fathoms", fill=ink, fill_opacity=".6", font_size="26", text_anchor="middle", font_family=SERIF)
    for i in range(5):
        S.add(f'<rect x="{350 + i*80}" y="1945" width="80" height="16" fill="{ink if i % 2 == 0 else "none"}" fill-opacity=".6" stroke="{ink}" stroke-opacity=".6"/>')
    S.text(350, 1995, "0", fill=ink, fill_opacity=".6", font_size="22", text_anchor="middle", font_family=SERIF)
    S.text(750, 1995, "5 leagues", fill=ink, fill_opacity=".6", font_size="22", text_anchor="middle", font_family=SERIF)
    # place names (your most-used apps, from deskfacts.py)
    for k, (x, y, sz) in zip(("p1", "p2", "p3", "p4"), ((1080, 820, 44), (2080, 1420, 44), (1560, 600, 46), (2420, 760, 40))):
        S.label(k, "{" + k + "}", x, y, fill="#e6f7f1", fill_opacity=".8", font_size=str(sz), font_style="italic", font_family=SERIF)
    return S, (1800, 1100), {"p1": "Render Ridge", "p2": "Queue Basin", "p3": "Mount Inbox", "p4": "Patchnote Shoals"}


# =====================================================================================================================
# 6. Greenhouse: a glasshouse at night in the rain; his plants grow with your streaks
# =====================================================================================================================
def greenhouse():
    S = Scene("greenhouse", "Greenhouse", 23)
    ink, accent = "#b9f0c8", "#ffc46b"
    HAND = "'Segoe Print','Bradley Hand','Comic Sans MS',cursive"
    MONO = "'IBM Plex Mono',Consolas,monospace"
    VX, VY = 1920, 980
    S.d('<linearGradient id="skyg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#050b12"/><stop offset=".7" stop-color="#0b1a22"/><stop offset="1" stop-color="#1b2a2a"/></linearGradient>'
        '<linearGradient id="glassg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#9fd8c0" stop-opacity=".06"/><stop offset="1" stop-color="#9fd8c0" stop-opacity=".02"/></linearGradient>'
        '<radialGradient id="bulb" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#ffd59a" stop-opacity=".6"/><stop offset="1" stop-color="#ffd59a" stop-opacity="0"/></radialGradient>'
        '<radialGradient id="city" cx="50%" cy="100%" r="70%"><stop offset="0" stop-color="#ff9e5a" stop-opacity=".25"/><stop offset="1" stop-color="#ff9e5a" stop-opacity="0"/></radialGradient>'
        '<linearGradient id="floorg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#101814"/><stop offset="1" stop-color="#070b09"/></linearGradient>'
        '<linearGradient id="benchg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3b2a1c"/><stop offset="1" stop-color="#1c140d"/></linearGradient>'
        '<filter id="gb4"><feGaussianBlur stdDeviation="4"/></filter><filter id="gb24"><feGaussianBlur stdDeviation="24"/></filter>')
    S.add(f'<rect width="{W}" height="{H}" fill="url(#skyg)"/>')
    # the night outside: distant hills, a town's glow, trees, all seen through wet glass
    S.add(f'<rect x="0" y="700" width="{W}" height="700" fill="url(#city)"/>')
    hills = [(0, 1180)] + [(x, 1150 - 60 * math.sin(x / 520) - 30 * math.sin(x / 190)) for x in range(0, W + 1, 40)] + [(W, 1180)]
    S.add(f'<polygon points="{poly(hills)}" fill="#0a1613"/>')
    for _ in range(140):                                   # far windows
        x, y = random.uniform(300, 3500), random.uniform(1060, 1150)
        S.add(f'<rect x="{x:.0f}" y="{y:.0f}" width="6" height="5" fill="#ffcf8a" fill-opacity="{random.uniform(.25, .7):.2f}"/>')
    for x in range(-100, W + 200, 170):                    # tree line
        h = random.uniform(140, 300)
        pts, _ = noise_loop(x, 1180 - h / 2, h / 2, .7, 1, step=12)
        S.add(f'<polygon points="{poly(pts)}" fill="#07110e"/>')
    for _ in range(900):                                    # rain streaks on the glass, baked faintly (they also move, live)
        x, y = random.uniform(0, W), random.uniform(0, 1500)
        L = random.uniform(18, 60)
        S.add(f'<line x1="{x:.0f}" y1="{y:.0f}" x2="{x - L * .12:.0f}" y2="{y + L:.0f}" stroke="#cfe9ff" stroke-opacity="{random.uniform(.05, .16):.2f}" stroke-width="1.6"/>')
    for _ in range(400):                                    # beads of water
        x, y = random.uniform(0, W), random.uniform(0, 1450)
        S.add(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{random.uniform(2, 6):.1f}" fill="#dff2ff" fill-opacity="{random.uniform(.06, .2):.2f}"/>')
    # the glasshouse frame: back wall panes, the arched roof, the side walls in perspective
    bx0, bx1, by0, by1 = 760, 3080, 360, 1380
    S.add(f'<rect x="{bx0}" y="{by0}" width="{bx1 - bx0}" height="{by1 - by0}" fill="url(#glassg)"/>')
    for x in range(bx0, bx1 + 1, 145):
        S.add(f'<line x1="{x}" y1="{by0}" x2="{x}" y2="{by1}" stroke="#1d2b25" stroke-width="{12 if (x - bx0) % 580 == 0 else 6}"/>')
    for y in range(by0, by1 + 1, 170):
        S.add(f'<line x1="{bx0}" y1="{y}" x2="{bx1}" y2="{y}" stroke="#1d2b25" stroke-width="6"/>')
    roof = f"M 0 380 Q {VX} -260 {W} 380"
    S.add(f'<path d="{roof}" fill="none" stroke="#24352d" stroke-width="26"/>')
    S.add(f'<path d="M {bx0} {by0} Q {VX} 120 {bx1} {by0}" fill="none" stroke="#24352d" stroke-width="16"/>')
    for k in range(-8, 9):                                  # roof ribs from the near arch to the far one
        t = (k + 8) / 16
        nx = t * W
        ny = 380 - 4 * 640 * t * (1 - t) + 0
        fx = bx0 + t * (bx1 - bx0)
        fy = by0 - 4 * 240 * t * (1 - t)
        S.add(f'<line x1="{nx:.0f}" y1="{ny:.0f}" x2="{fx:.0f}" y2="{fy:.0f}" stroke="#1d2b25" stroke-width="7"/>')
    for side in (-1, 1):                                     # side walls
        x_near = 0 if side < 0 else W
        x_far = bx0 if side < 0 else bx1
        S.add(f'<polygon points="{x_near},380 {x_far},{by0} {x_far},{by1} {x_near},{H}" fill="url(#glassg)"/>')
        for i in range(1, 7):
            t = i / 7
            xa = x_near + (x_far - x_near) * t
            S.add(f'<line x1="{xa:.0f}" y1="{380 + (by0 - 380) * t:.0f}" x2="{xa:.0f}" y2="{H + (by1 - H) * t:.0f}" stroke="#1d2b25" stroke-width="{10 - i}"/>')
        for yy in (700, 1000, 1300, 1600):
            S.add(f'<line x1="{x_near}" y1="{yy + (0 if side < 0 else 0)}" x2="{x_far}" y2="{by0 + (yy - 380) * (by1 - by0) / (H - 380):.0f}" stroke="#1d2b25" stroke-width="5"/>')
    # floor: brick path down the middle, gravel either side
    S.add(f'<polygon points="0,{H} {W},{H} {bx1},{by1} {bx0},{by1}" fill="url(#floorg)"/>')
    path = [(1500, H), (2340, H), (2040, by1), (1800, by1)]
    S.add(f'<polygon points="{poly(path)}" fill="#2a1b14" fill-opacity=".8"/>')
    for i in range(1, 22):
        t = (i / 22) ** 1.6
        y = H + (by1 - H) * t
        xl = 1500 + (1800 - 1500) * t
        xr = 2340 + (2040 - 2340) * t
        S.add(f'<line x1="{xl:.0f}" y1="{y:.0f}" x2="{xr:.0f}" y2="{y:.0f}" stroke="#4a3020" stroke-opacity=".5" stroke-width="2"/>')
    for _ in range(1600):
        x, y = random.uniform(0, W), random.uniform(by1, H)
        S.add(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{random.uniform(1, 3):.1f}" fill="#9fb6a6" fill-opacity="{random.uniform(.03, .09):.2f}"/>')

    def leaf(x, y, L, wdt, ang, col, op=.9):
        a = math.radians(ang)
        tx, ty = x + L * math.cos(a), y + L * math.sin(a)
        nx, ny = -math.sin(a) * wdt, math.cos(a) * wdt
        mx, my = (x + tx) / 2, (y + ty) / 2
        S.add(f'<path d="M {x:.0f} {y:.0f} Q {mx + nx:.0f} {my + ny:.0f} {tx:.0f} {ty:.0f} Q {mx - nx:.0f} {my - ny:.0f} {x:.0f} {y:.0f} Z" '
              f'fill="{col}" fill-opacity="{op}"/>')
        S.add(f'<line x1="{x:.0f}" y1="{y:.0f}" x2="{tx:.0f}" y2="{ty:.0f}" stroke="#0b1a12" stroke-opacity=".5" stroke-width="2"/>')

    greens = ["#1f4a32", "#2b5e3f", "#356f48", "#3f7f52", "#4e915d", "#5fa267"]

    def plant(x, y, size, kind):
        if kind == "fern":
            for k in range(14):
                ang = -90 + random.uniform(-80, 80)
                leaf(x, y, size * random.uniform(.7, 1.1), size * .09, ang, random.choice(greens))
        elif kind == "palm":
            S.add(f'<line x1="{x}" y1="{y}" x2="{x + 10}" y2="{y - size * .8:.0f}" stroke="#4a3a26" stroke-width="{size * .06:.0f}"/>')
            for k in range(9):
                leaf(x + 10, y - size * .8, size * .8, size * .12, -180 + k * 22 + random.uniform(-6, 6), random.choice(greens))
        else:                                                # broad leaves
            for k in range(8):
                ang = -90 + random.uniform(-70, 70)
                leaf(x, y, size * random.uniform(.6, 1.0), size * .28, ang, random.choice(greens), .95)

    def pot(x, y, w, h, col="#8a4a2e"):
        S.add(f'<polygon points="{x - w / 2:.0f},{y} {x + w / 2:.0f},{y} {x + w * .38:.0f},{y + h} {x - w * .38:.0f},{y + h}" fill="{col}"/>'
              f'<rect x="{x - w * .55:.0f}" y="{y - h * .14:.0f}" width="{w * 1.1:.0f}" height="{h * .18:.0f}" fill="{col}" />'
              f'<rect x="{x - w * .55:.0f}" y="{y - h * .14:.0f}" width="{w * 1.1:.0f}" height="{h * .05:.0f}" fill="#000" fill-opacity=".25"/>')

    # benches, left and right, with pots and plants (the middle stays clear for his ring)
    for side in (-1, 1):
        x0 = 120 if side < 0 else 2620
        x1 = 1220 if side < 0 else 3720
        top = 1500
        S.add(f'<rect x="{x0}" y="{top}" width="{x1 - x0}" height="46" fill="url(#benchg)"/>')
        S.add(f'<rect x="{x0}" y="{top + 46}" width="{x1 - x0}" height="12" fill="#120c07"/>')
        for lx in (x0 + 60, x1 - 80):
            S.add(f'<rect x="{lx}" y="{top + 58}" width="22" height="{H - top}" fill="#1c140d"/>')
        for i, px_ in enumerate(range(x0 + 150, x1 - 60, 260)):
            sz = random.uniform(240, 360)
            plant(px_, top - 100, sz, ("fern", "broad", "palm", "broad", "fern")[(i + (side > 0)) % 5])
            pot(px_, top - 90, 150, 90, random.choice(("#8a4a2e", "#6e3c26", "#a35a36")))
    # big plants in the near corners framing the view
    for x, y, sz, kind in ((90, 2200, 700, "broad"), (3640, 2120, 820, "broad"), (1120, 2200, 520, "fern"), (3160, 2200, 560, "fern")):
        plant(x, y, sz, kind)
    # hanging bulbs
    for x, y in ((1100, 520), (1920, 380), (2740, 520), (1500, 640), (2340, 640)):
        S.add(f'<line x1="{x}" y1="0" x2="{x}" y2="{y}" stroke="#0e1512" stroke-width="3"/>')
        S.add(f'<circle cx="{x}" cy="{y}" r="200" fill="url(#bulb)"/>')
        S.add(f'<circle cx="{x}" cy="{y}" r="16" fill="#ffe2b0"/>')
    # the slate sign and plant tags (live text from deskfacts.py)
    S.add(f'<rect x="380" y="1700" width="600" height="300" rx="10" fill="#1b2421" stroke="#5a4630" stroke-width="18"/>')
    S.text(680, 1772, "the greenhouse", fill="#dfe8e2", fill_opacity=".8", font_size="44", text_anchor="middle", font_family=HAND)
    S.label("streak", "watered {days} days", 420, 1850, fill="#dfe8e2", fill_opacity=".75", font_size="36", font_family=HAND)
    S.label("outside", "outside: {temp}", 420, 1910, fill="#dfe8e2", fill_opacity=".7", font_size="36", font_family=HAND)
    S.label("planted", "planted {planted}", 420, 1965, fill="#dfe8e2", fill_opacity=".55", font_size="30", font_family=HAND)
    for k, (x, y) in zip(("t1", "t2", "t3"), ((2700, 1600), (3020, 1600), (3340, 1600))):
        S.add(f'<rect x="{x - 10}" y="{y - 32}" width="230" height="44" fill="#e8e2cf" fill-opacity=".85"/>')
        S.label(k, "{" + k + "}", x, y, fill="#2a2a20", font_size="24", font_family=MONO)
    return S, (VX, VY), {"days": "12", "temp": "18°", "planted": "the first night", "t1": "basil", "t2": "fern no. 3",
                         "t3": "stubborn one"}


# ---------------------------------------------------------------------------------------------------- colours + output
THEME = {
    "bench": dict(bg="#0b1b2e", ink="#a9d4ff", accent="#ffb347", panel="rgba(9,24,42,.9)", border="rgba(169,212,255,.5)",
                  text="#e7f2ff", dim="#9cb7d3", style="sheet", ring=.15),
    "station": dict(bg="#03060c", ink="#8fd8ff", accent="#7fe7ff", panel="rgba(8,16,30,.86)", border="rgba(143,216,255,.45)",
                    text="#eaf6ff", dim="#9bb6cc", style="module", ring=.12),
    "archive": dict(bg="#0a0806", ink="#e8d3a8", accent="#7fd6ff", panel="rgba(28,22,15,.93)", border="rgba(200,164,106,.55)",
                    text="#f3e9d6", dim="#b8a68a", style="card", ring=.11),
    "signal": dict(bg="#03100d", ink="#5dffc8", accent="#ffcf5d", panel="rgba(3,20,16,.9)", border="rgba(93,255,200,.45)",
                   text="#d9fff1", dim="#8fc7b4", style="scope", ring=.14),
    "greenhouse": dict(bg="#06100c", ink="#b9f0c8", accent="#ffc46b", panel="rgba(8,20,15,.9)", border="rgba(185,240,200,.45)",
                       text="#eafaf0", dim="#9fbfa9", style="card", ring=.12),
    "chart": dict(bg="#071a1e", ink="#9fe3d6", accent="#ff9f5a", panel="rgba(6,28,32,.9)", border="rgba(159,227,214,.5)",
                  text="#eafaf6", dim="#9cc4bc", style="legend", ring=.1),
}

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    meta = {}
    for make in (bench, station, archive, signal, chart, greenhouse):
        S, (vx, vy), defaults = make()
        data = S.svg()
        open(os.path.join(OUT, S.key + ".svg"), "w", encoding="utf-8").write(data)
        meta[S.key] = dict(title=S.title, viz=[vx / W, vy / H], size=[W, H], labels=S.labels, defaults=defaults, **THEME[S.key])
        print(f"{S.key:8s} {len(data) // 1024:5d} KB")
    with open(os.path.join(OUT, "scenes.js"), "w", encoding="utf-8") as fh:
        fh.write("// The desktop scenes, made by design/make_scenes.py (the pictures; ui/ambient.js adds the small things that move).\n"
                 "// labels: text from your real data (deskfacts.py), drawn over the picture. viz: where his ring sits.\n"
                 "window.SCENES = " + json.dumps(meta, indent=1, ensure_ascii=False) + ";\n")
