#!/usr/bin/env python3
"""Compose a review sheet: concept left, four renders 2x2 right, caption from stats.json.

  review_sheet.py --views DIR --out SHEET.png [--concept CONCEPT.png] [--title NAME] [--notes "text"]
"""
import argparse, json, os, sys
from PIL import Image, ImageDraw, ImageFont

VIEWS = [("three_quarter", "THREE-QUARTER"), ("front", "FRONT"), ("side", "SIDE"), ("wireframe", "WIREFRAME")]
BG, FG, DIM = "#14120E", "#DCD2BA", "#9A9078"
FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans.ttf"]


def font(size):
    for p in FONTS:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size)  # Pillow >= 10.1 scalable default
    except TypeError:
        print("review_sheet: no TrueType font found; caption uses the tiny bitmap font", file=sys.stderr)
        return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--views", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--concept"); ap.add_argument("--title", default=""); ap.add_argument("--notes", default="")
    a = ap.parse_args()

    missing = [f"{n}.png" for n, _ in VIEWS if not os.path.isfile(os.path.join(a.views, n + ".png"))]
    if missing:
        sys.exit(f"review_sheet.py: missing views in {a.views}: {', '.join(missing)}")
    tiles = [Image.open(os.path.join(a.views, n + ".png")).convert("RGB") for n, _ in VIEWS]
    tile = tiles[0].width
    gap = max(6, tile // 80)
    grid = tile * 2 + gap

    if a.concept:
        if not os.path.isfile(a.concept):
            sys.exit(f"review_sheet.py: concept not found: {a.concept}")
        c = Image.open(a.concept).convert("RGB")
        c = c.resize((int(c.width * grid / c.height), grid), Image.LANCZOS)
    else:
        c = Image.new("RGB", (grid * 3 // 4, grid), "#2A261F")
        d = ImageDraw.Draw(c)
        d.rectangle([0, 0, c.width - 1, c.height - 1], outline="#8A3A2A", width=4)
        d.text((c.width // 2, c.height // 2), "NO CONCEPT", fill="#C8553D", font=font(tile // 12), anchor="mm")

    cap_h = tile * 3 // 10
    sheet = Image.new("RGB", (gap + c.width + gap + grid + gap, gap + grid + gap + cap_h), BG)
    sheet.paste(c, (gap, gap))
    d = ImageDraw.Draw(sheet)
    left = gap + c.width + gap
    for i, ((_, label), t) in enumerate(zip(VIEWS, tiles)):
        r, col = divmod(i, 2)
        x, y = left + col * (tile + gap), gap + r * (tile + gap)
        sheet.paste(t, (x, y))
        d.text((x + 12, y + 10), label, fill=DIM, font=font(max(12, tile // 34)))

    line2 = ""
    sp = os.path.join(a.views, "stats.json")
    if os.path.isfile(sp):
        s = json.load(open(sp))
        bx, by, bz = s["bbox_m"]
        line2 = (f"{s['triangles']} tris  |  bbox {bx:.2f} x {by:.2f} x {bz:.2f} m  |  height {s['height_m']:.2f} m"
                 f"  |  {s['bones']['count']} bones  |  {s['mesh_count']} mesh(es)")
    else:
        line2 = "NO stats.json in views dir"
    y0 = gap + grid + gap + 4
    d.text((gap + 6, y0), a.title, fill=FG, font=font(max(22, tile // 16)))
    d.text((gap + 6, y0 + int(tile * 0.09)), line2, fill=DIM, font=font(max(16, tile // 26)))
    if a.notes:
        d.text((gap + 6, y0 + int(tile * 0.16)), a.notes, fill=DIM, font=font(max(16, tile // 26)))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    sheet.save(a.out)
    print(f"review_sheet: wrote {a.out}")


main()
