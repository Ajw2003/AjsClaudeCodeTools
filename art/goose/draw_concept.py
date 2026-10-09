#!/usr/bin/env python3
"""Draw the eldritch goose concept sheet from the design data, with Pillow.

  python3 art/goose/draw_concept.py

Writes art/goose/concept.png: front and side orthographic views at one scale, a 1.80 m reference
human beside each, a metre ladder, callouts, and the palette strip with hex codes. Every shape comes
from goose_design.build_parts(), the same parts the 3D build meshes, so sheet and model share numbers.
"""
import math, os, sys
from PIL import Image, ImageDraw, ImageFont

import goose_design as g

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "concept.png")
W, H = 3300, 1190
PX_PER_M = 118
BG, INK, DIM, GRID = "#EDE6D6", "#1B1712", "#6E6556", "#D9D0BC"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
GROUND_Y = 920


def font(size, bold=False):
    try:
        return ImageFont.truetype(FONT_BOLD if bold else FONT, size)
    except OSError:
        sys.exit(f"draw_concept.py: font not found ({FONT}); install fonts-dejavu")


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def shade(rgb, f):
    return tuple(max(0, min(255, int(c * f))) for c in rgb)


class View:
    """An orthographic view: which world axis is screen-right, which is depth (toward the viewer)."""

    def __init__(self, name, origin_x, right, toward):
        self.name, self.origin_x, self.right, self.toward = name, origin_x, right, toward

    def xy(self, p):
        return (self.origin_x + g.dot(p, self.right) * PX_PER_M, GROUND_Y - p[2] * PX_PER_M)

    def depth(self, p):
        return g.dot(p, self.toward)


def facing_angle(frame, view):
    """The tube angle (degrees) whose surface faces the viewer, for picking the visible paint."""
    _, nrm, bin_ = frame
    return math.degrees(math.atan2(g.dot(view.toward, bin_), g.dot(view.toward, nrm))) % 360


def draw_items(parts, view, colours):
    """Break parts into depth-sortable draw items: tube chunks, ellipses and outlines."""
    items = []
    for part in parts:
        if part["kind"] == "ellipsoid":
            items.append((view.depth(part["centre"]), "ellipse", part))
            continue
        d = part["draw"]
        if d["type"] == "outline":
            pts = d["points"]
            items.append((sum(view.depth(p) for p in pts) / len(pts), "outline", part))
            continue
        path = d["path"]
        chunk = 8
        for start in range(0, len(path), chunk):
            idx = list(range(max(0, start - 1), min(len(path), start + chunk)))
            items.append((sum(view.depth(path[i]) for i in idx) / len(idx), "tube", (part, idx)))
    items.sort(key=lambda it: it[0])
    return items


def draw_view(img, parts, view, colours):
    dr = ImageDraw.Draw(img)
    outline = hex_rgb(INK)
    for _, kind, item in draw_items(parts, view, colours):
        if kind == "ellipse":
            c, axes, radii = item["centre"], item["axes"], item["radii"]
            # 2D projection of an ellipsoid: sum of outer products of its projected semi-axes
            m = [[0.0, 0.0], [0.0, 0.0]]
            for a, r in zip(axes, radii):
                v = (g.dot(a, view.right) * r * PX_PER_M, -a[2] * r * PX_PER_M)
                m[0][0] += v[0] * v[0]; m[0][1] += v[0] * v[1]; m[1][1] += v[1] * v[1]
            tr, det = m[0][0] + m[1][1], m[0][0] * m[1][1] - m[0][1] ** 2
            disc = math.sqrt(max(0.0, tr * tr / 4 - det))
            l1, l2 = tr / 2 + disc, max(0.0, tr / 2 - disc)
            ang = 0.5 * math.atan2(2 * m[0][1], m[0][0] - m[1][1])
            cx, cy = view.xy(c)
            a1, a2 = math.sqrt(l1), math.sqrt(l2)
            poly = [(cx + a1 * math.cos(t) * math.cos(ang) - a2 * math.sin(t) * math.sin(ang),
                     cy + a1 * math.cos(t) * math.sin(ang) + a2 * math.sin(t) * math.cos(ang))
                    for t in [2 * math.pi * k / 24 for k in range(24)]]
            col = colours[item["material"]]
            if a1 >= 1.5:
                dr.polygon(poly, fill=col, outline=outline if a1 > 4 else None)
        elif kind == "outline":
            pts = [view.xy(p) for p in item["draw"]["points"]]
            col = colours[item["material"]]
            dr.polygon(pts, fill=col, outline=outline)
            mid = len(pts) // 2
            dr.line([pts[0], ((pts[mid - 1][0] + pts[mid][0]) / 2, (pts[mid - 1][1] + pts[mid][1]) / 2)],
                    fill=shade(col, 0.6), width=1)
        else:
            part, idx = item
            d = part["draw"]
            circles = []
            for i in idx:
                cx, cy = view.xy(d["path"][i])
                r = d["radii"][i] * PX_PER_M
                mat = part["material"]
                if d["paint"]:
                    t = i / max(1, len(d["path"]) - 1)
                    mat = d["paint"](t, facing_angle(d["frames"][i], view), d["path"][i]) or mat
                circles.append((cx, cy, r, colours[mat]))
            for cx, cy, r, _ in circles:
                dr.ellipse([cx - r - 1.5, cy - r - 1.5, cx + r + 1.5, cy + r + 1.5], fill=outline)
            for cx, cy, r, col in circles:
                dr.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)


def draw_human(dr, x):
    """A 1.80 m reference figure standing at screen x."""
    s = PX_PER_M
    ink = hex_rgb(DIM)
    dr.ellipse([x - 0.11 * s, GROUND_Y - 1.80 * s, x + 0.11 * s, GROUND_Y - 1.56 * s], outline=ink, width=3)
    dr.line([(x, GROUND_Y - 1.56 * s), (x, GROUND_Y - 0.90 * s)], fill=ink, width=3)
    dr.line([(x - 0.25 * s, GROUND_Y - 0.80 * s), (x, GROUND_Y - 1.42 * s), (x + 0.25 * s, GROUND_Y - 0.80 * s)],
            fill=ink, width=3)
    dr.line([(x - 0.17 * s, GROUND_Y), (x, GROUND_Y - 0.90 * s), (x + 0.17 * s, GROUND_Y)], fill=ink, width=3)
    dr.text((x, GROUND_Y + 14), "1.80 m", fill=ink, font=font(20), anchor="mt")


def draw_ladder(dr, x, top_m):
    for m in range(0, top_m + 1):
        y = GROUND_Y - m * PX_PER_M
        dr.line([(x, y), (x + 14, y)], fill=INK, width=2)
        dr.text((x - 8, y), f"{m} m", fill=INK, font=font(18), anchor="rm")
    dr.line([(x, GROUND_Y), (x, GROUND_Y - top_m * PX_PER_M)], fill=INK, width=2)


def anchor(parts, name, view):
    for p in parts:
        if p["name"] == name:
            pt = p["centre"] if p["kind"] == "ellipsoid" else (
                p["draw"]["path"][len(p["draw"]["path"]) // 2] if p["draw"]["type"] == "tube"
                else p["draw"]["points"][len(p["draw"]["points"]) // 2])
            return view.xy(pt)
    raise KeyError(f"draw_concept.py: no part named {name} to point a callout at")


def callouts(dr, parts, view, notes, label_x, align):
    """Labels in a margin column, spread out so none overlap, each with a leader line to its part."""
    f = font(21)
    placed = []
    for text, part_name in notes:
        ax, ay = anchor(parts, part_name, view)
        placed.append([ay, ay, ax, text])
    placed.sort()
    last = 120
    for row in placed:
        row[0] = max(row[0] - 12, last + 54)  # label row, pushed down clear of the one above
        last = row[0]
    for ly, ay, ax, text in placed:
        lines = text.split("\n")
        tx = label_x
        dr.multiline_text((tx, ly), text, fill=INK, font=f, anchor="ra" if align == "right" else "la", spacing=2)
        edge = tx + (8 if align == "right" else -8)
        dr.line([(edge, ly + 12), (ax, ay)], fill=DIM, width=2)
        dr.ellipse([ax - 4, ay - 4, ax + 4, ay + 4], fill=INK)


def main():
    spec = g.load_spec()
    parts = g.build_parts(spec)
    colours = {m["name"]: hex_rgb(m["hex"]) for m in spec["materials"]}

    img = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(img)
    for m in range(0, 7):
        y = GROUND_Y - m * PX_PER_M
        dr.line([(60, y), (W - 60, y)], fill=GRID, width=1)
    dr.line([(60, GROUND_Y), (W - 60, GROUND_Y)], fill=INK, width=3)

    front = View("FRONT", 900, (1.0, 0.0, 0.0), (0.0, -1.0, 0.0))
    side = View("SIDE (left)", 2450, (0.0, 1.0, 0.0), (1.0, 0.0, 0.0))
    draw_view(img, parts, front, colours)
    draw_view(img, parts, side, colours)
    draw_human(dr, 1520)
    draw_human(dr, 2800)
    draw_ladder(dr, 110, 6)

    dr.text((60, 30), spec["name"].upper(), fill=INK, font=font(40, True))
    dr.text((60, 80), f"Concept sheet  |  boss, hero tier  |  {spec['height_m']:.2f} m to the crown, faces -Y  |  "
                      f"budget {spec['triangle_budget']:,} tris  |  orthographic, 1 m = {PX_PER_M} px",
            fill=DIM, font=font(22))
    for view, x in ((front, 900), (side, 2450)):
        dr.text((x, 120), view.name, fill=INK, font=font(26, True), anchor="mt")

    callouts(dr, parts, front, [
        ("Crown of dead maple branches", "main_branch0_1"),
        ("Main head: jaw 42 deg,\ntooth rows, spiked tongue", "main_tongue"),
        ("Side heads x2 at 0.74 scale", "side_R_head"),
        ("Bare finger bones, claws", "finger_bone0_R"),
        ("Ragged primaries", "primary3_R"),
        ("Blood-soaked breast feathers", "breast_feather1_4"),
        ("Maple leaf branded into the breast", "breast_brand"),
        ("Bare ribs through the flanks", "rib3_R"),
    ], 1620, "left")
    callouts(dr, parts, side, [
        ("Bone ridge down the neck", "neck_spine6"),
        ("Rotting maple leaves in the plumage", "leaf_back5"),
        ("One sunken eye a side per head", "main_eye_R"),
        ("Chinstrap: ChinWhite", "main_head"),
        ("Webbed feet, bone claws", "web1_R"),
        ("Undertail: ChinWhite", "tail4"),
    ], 2900, "left")

    x, y = 60, H - 150
    dr.text((x, y - 36), "PALETTE", fill=INK, font=font(22, True))
    sw = (W - 120) // len(spec["materials"])
    for k, m in enumerate(spec["materials"]):
        x0 = x + k * sw
        dr.rectangle([x0, y, x0 + sw - 10, y + 56], fill=hex_rgb(m["hex"]), outline=INK)
        dr.text((x0, y + 64), m["name"], fill=INK, font=font(17))
        dr.text((x0, y + 86), m["hex"], fill=DIM, font=font(16))
    img.save(OUT)
    print(f"draw_concept: wrote {OUT} ({W}x{H}) from {len(parts)} parts")


if __name__ == "__main__":
    main()
