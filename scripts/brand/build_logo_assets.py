"""Build the 5-file Nucleus brand pack (locked 2026-05-15). Visual metaphor:
nucleus_architecture_v4.1.md §9. Tagline per ADR-002 §8.1; locks after PoC #5.
Build-time deps (not pinned): pip install resvg-py Pillow.
  https://github.com/Kludex/resvg-py | https://pillow.readthedocs.io/en/stable/
"""
import math, sys
from io import BytesIO
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
OUT = REPO / "assets" / "brand"
R, INSET, STROKE, CX, CY = 180.0, 4.0, 6.0, 256.0, 256.0
OFFSET_FRACTION = 0.28        # founder-locked 2026-05-15
COLORS = ["#132A65", "#F37840", "#72A6F7", "#3273FB", "#2E65DD", "#0F3193"]
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif"
NAVY, CREAM = "#09224F", "#FAF9F6"   # CREAM sampled from nucleus-logo-option-2-composable.png


def _wedges():
    V = [(CX + R * math.cos(math.radians(a)), CY - R * math.sin(math.radians(a)))
         for a in (0, 60, 120, 180, 240, 300)]
    C = (CX, CY)
    return [[C, V[1], V[2]], [C, V[0], V[1]], [C, V[5], V[0]],
            [C, V[4], V[5]], [C, V[3], V[4]], [C, V[2], V[3]]]

def _poly(verts, is_orange=False):
    gx, gy = sum(v[0] for v in verts) / 3, sum(v[1] for v in verts) / 3
    pts = [(x + INSET * (gx - x) / math.hypot(gx - x, gy - y),
            y + INSET * (gy - y) / math.hypot(gx - x, gy - y)) for x, y in verts]
    if is_orange:
        d = OFFSET_FRACTION * R
        ox, oy = d * math.cos(math.radians(30)), -d * math.sin(math.radians(30))
        pts = [(x + ox, y + oy) for x, y in pts]
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)

def _verify():
    rs = [math.hypot(sum(v[0] for v in w) / 3 - w[0][0],
                     sum(v[1] for v in w) / 3 - w[0][1])
          for i, w in enumerate(_wedges()) if i != 1]
    sp = max(rs) - min(rs)
    assert sp < 0.5, f"non-uniform seams: spread={sp:.3f}px"
    print(f"PASS: 5 blue triangles uniform within {sp:.4f} px")

def _premium(resvg, Image, mark_svg, out):
    # 1024x683 cream-paper canvas + vertical lockup + zero-mean paper-grain.
    from PIL import ImageDraw, ImageFont, ImageChops
    W, H = 1024, 683
    canvas = Image.new("RGB", (W, H), CREAM)
    mark = Image.open(BytesIO(bytes(resvg.svg_to_bytes(svg_string=mark_svg, width=360)))).convert("RGBA")
    canvas.paste(mark, ((W - 360) // 2, 70), mark)
    font = ImageFont.load_default()
    for n in ("arial.ttf", "DejaVuSans.ttf", "Helvetica.ttf"):
        try: font = ImageFont.truetype(n, 92); break
        except OSError: pass
    draw = ImageDraw.Draw(canvas)
    bw = draw.textbbox((0, 0), "nucleus", font=font)[2]
    draw.text(((W - bw) // 2, 470), "nucleus", fill=NAVY, font=font)
    # Paper-grain: 1/4-res Gaussian noise upscaled bilinear, additively blended
    # around 128 so cream stays cream and the grain has paper-like coarseness.
    grain = Image.effect_noise((W // 4, H // 4), 22).resize((W, H), Image.BILINEAR).convert("RGB")
    ImageChops.add(canvas, grain, scale=1.0, offset=-128).save(out, format="PNG", optimize=True)

def main():
    try: import resvg_py; from PIL import Image
    except ImportError as e:
        print(f"ERROR: pip install resvg-py Pillow ({e})", file=sys.stderr); return 1
    OUT.mkdir(parents=True, exist_ok=True)
    tri = "\n  ".join(
        f'<polygon points="{_poly(w, i==1)}" fill="{COLORS[i]}" stroke="{COLORS[i]}" '
        f'stroke-width="{STROKE}" stroke-linejoin="round" stroke-linecap="round"/>'
        for i, w in enumerate(_wedges()))
    svg = lambda vb, body: f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vb}" role="img" aria-label="Nucleus">\n  {body}\n</svg>\n'
    mark = svg("512 512", tri)
    vlogo = svg("512 720", tri + f'\n  <text x="256" y="660" text-anchor="middle" font-family="{FONT}" font-size="92" font-weight="400" letter-spacing="0.06em" fill="{NAVY}">nucleus</text>')
    (OUT / "nucleus-mark.svg").write_text(mark, encoding="utf-8")
    (OUT / "favicon.svg").write_text(mark, encoding="utf-8")
    (OUT / "nucleus-logo.svg").write_text(vlogo, encoding="utf-8")
    _premium(resvg_py, Image, mark, OUT / "nucleus-logo.png")
    src = Image.open(BytesIO(bytes(resvg_py.svg_to_bytes(
        svg_string=mark, width=256)))).convert("RGBA")
    src.save(OUT / "favicon.ico", format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])
    _verify()
    for p in sorted(OUT.iterdir()):
        print(f"  {p.name:38s} {p.stat().st_size:>9,} B")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
