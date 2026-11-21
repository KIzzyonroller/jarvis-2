"""
His icon: the dial he shows on the desktop. A ring of ticks, the inner circle, the amber arc that sweeps while he
thinks, and the core. Small sizes (16-32 px) drop the ticks so it stays a clean shape.

    python design/make_icon.py      ->  assets/jarvis.svg, assets/jarvis.png (512), assets/jarvis.ico (16-256),
                                        assets/jarvis-small.svg, site/img/logo.svg, site/img/favicon.png
Needs rsvg-convert (or cairosvg) and Pillow.
"""
import io
import math
import shutil
import subprocess
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
BG0, BG1, INK, AMBER = "#0d2236", "#06101b", "#a9d4ff", "#ffb347"


def mark(small=False, tile=True):
    S, c = 512, 256
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}">',
         '<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
         f'<stop offset="0" stop-color="{BG0}"/><stop offset="1" stop-color="{BG1}"/></linearGradient>'
         f'<radialGradient id="core" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="{INK}" stop-opacity=".55"/>'
         f'<stop offset="1" stop-color="{INK}" stop-opacity="0"/></radialGradient></defs>']
    if tile:
        o.append(f'<rect x="16" y="16" width="480" height="480" rx="112" fill="url(#bg)"/>')
        o.append(f'<rect x="17.5" y="17.5" width="477" height="477" rx="110.5" fill="none" stroke="{INK}" stroke-opacity=".14" stroke-width="3"/>')
    R = 150 if not small else 160
    o.append(f'<circle cx="{c}" cy="{c}" r="{R * .62:.0f}" fill="url(#core)"/>')
    o.append(f'<circle cx="{c}" cy="{c}" r="{R}" fill="none" stroke="{INK}" stroke-opacity="{.9 if small else .7}" stroke-width="{22 if small else 9}"/>')
    if not small:
        for i in range(48):
            a = i / 48 * 2 * math.pi - math.pi / 2
            L = 34 if i % 12 == 0 else 20 if i % 4 == 0 else 11
            w = 9 if i % 12 == 0 else 6.5 if i % 4 == 0 else 4.5
            r0 = R + 16
            o.append(f'<line x1="{c + r0 * math.cos(a):.1f}" y1="{c + r0 * math.sin(a):.1f}" x2="{c + (r0 + L) * math.cos(a):.1f}" '
                     f'y2="{c + (r0 + L) * math.sin(a):.1f}" stroke="{INK}" stroke-width="{w}" stroke-linecap="round"/>')
    ri = R * (.66 if not small else .58)
    o.append(f'<circle cx="{c}" cy="{c}" r="{ri:.0f}" fill="none" stroke="{INK}" stroke-opacity=".35" stroke-width="{10 if small else 6}"/>')
    a0, a1 = math.radians(-90), math.radians(-90 + 115)                   # the thinking arc
    o.append(f'<path d="M {c + ri * math.cos(a0):.1f} {c + ri * math.sin(a0):.1f} A {ri:.0f} {ri:.0f} 0 0 1 '
             f'{c + ri * math.cos(a1):.1f} {c + ri * math.sin(a1):.1f}" fill="none" stroke="{AMBER}" '
             f'stroke-width="{26 if small else 16}" stroke-linecap="round"/>')
    o.append(f'<circle cx="{c}" cy="{c}" r="{30 if small else 22}" fill="{INK}"/>')
    o.append("</svg>")
    return "".join(o)


def render(svg, px):
    if shutil.which("rsvg-convert"):
        out = subprocess.run(["rsvg-convert", "-w", str(px), "-h", str(px)], input=svg.encode(), capture_output=True, check=True).stdout
    else:
        import cairosvg
        out = cairosvg.svg2png(bytestring=svg.encode(), output_width=px, output_height=px)
    return Image.open(io.BytesIO(out)).convert("RGBA")


def main():
    a = ROOT / "assets"
    a.mkdir(exist_ok=True)
    big, small = mark(), mark(small=True)
    (a / "jarvis.svg").write_text(big, encoding="utf-8")
    (a / "jarvis-small.svg").write_text(small, encoding="utf-8")
    render(big, 512).save(a / "jarvis.png")
    sizes = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]
    imgs = [render(small if s <= 32 else big, s) for s in sizes]
    imgs[-1].save(a / "jarvis.ico", sizes=[(s, s) for s in sizes], append_images=imgs[:-1])
    site = ROOT / "site" / "img"
    site.mkdir(parents=True, exist_ok=True)
    (site / "logo.svg").write_text(big, encoding="utf-8")
    render(small, 64).save(site / "favicon.png")
    render(big, 1024).save(site / "icon-1024.png")
    print("icon written")


if __name__ == "__main__":
    main()
