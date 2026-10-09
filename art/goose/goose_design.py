#!/usr/bin/env python3
"""The eldritch goose as data: spec.json in, a list of parts out, and each part as mesh faces.

Pure Python, no bpy, so the concept sheet (draw_concept.py) and the model (build_goose.py) are drawn
from the same numbers and cannot disagree. Metres; +Z up; the goose faces -Y.

A part is a dict with a "kind":
  "loft"      rings of vertices skinned into a closed shell (tubes, the body, cones, feathers, webs),
              with per-face materials;
  "ellipsoid" a UV sphere stretched along three axes (eyes, knuckles, the maw's throat).
Every loft also carries "draw": how the concept sheet should draw it (a "tube" of circles, or a
flat "outline" polygon).
"""
import json, math, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
UP = (0.0, 0.0, 1.0)


def load_spec():
    with open(os.path.join(HERE, "spec.json")) as f:
        return json.load(f)


# ---------------------------------------------------------------- vectors

def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def mul(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def length(a): return math.sqrt(dot(a, a))
def lerp(a, b, t): return tuple(x + (y - x) * t for x, y in zip(a, b))
def mirror(p): return (-p[0], p[1], p[2])


def norm(a):
    n = length(a)
    if n < 1e-12:
        raise ValueError(f"cannot normalise a zero vector {a}")
    return mul(a, 1.0 / n)


def combine(*terms):
    """Sum of (vector, weight) pairs."""
    out = (0.0, 0.0, 0.0)
    for v, w in terms:
        out = add(out, mul(v, w))
    return out


def rotate(v, axis, degrees):
    """Rodrigues rotation of v about a unit axis."""
    k, t = norm(axis), math.radians(degrees)
    c, s = math.cos(t), math.sin(t)
    return combine((v, c), (cross(k, v), s), (k, dot(k, v) * (1 - c)))


def perpendicular(v, hint):
    """hint with its v component removed, normalised; falls back to another axis if they are parallel."""
    for h in (hint, (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)):
        p = sub(h, mul(v, dot(h, v)))
        if length(p) > 1e-6:
            return norm(p)
    raise ValueError("no perpendicular found")


# ---------------------------------------------------------------- paths

def _catmull(p0, p1, p2, p3, t):
    t2, t3 = t * t, t * t * t
    return tuple(0.5 * (2 * b + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (-a + 3 * b - 3 * c + d) * t3)
                 for a, b, c, d in zip(p0, p1, p2, p3))


def smooth_path(points, values, step):
    """Catmull-Rom through the control points, resampled every `step` metres along its length.
    values: one tuple per control point (radii and the like), interpolated alongside."""
    pts = [points[0]] + [tuple(p) for p in points] + [points[-1]]
    fine, fine_vals = [], []
    for i in range(1, len(pts) - 2):
        for k in range(32):
            t = k / 32
            fine.append(_catmull(pts[i - 1], pts[i], pts[i + 1], pts[i + 2], t))
            fine_vals.append(lerp(values[i - 1], values[i], t))
    fine.append(tuple(points[-1]))
    fine_vals.append(tuple(values[-1]))

    cumulative = [0.0]
    for a, b in zip(fine, fine[1:]):
        cumulative.append(cumulative[-1] + length(sub(b, a)))
    total = cumulative[-1]
    count = max(3, int(round(total / step)) + 1)
    out, out_vals, j = [], [], 0
    for i in range(count):
        s = total * i / (count - 1)
        while j < len(cumulative) - 2 and cumulative[j + 1] < s:
            j += 1
        span = cumulative[j + 1] - cumulative[j]
        f = 0.0 if span < 1e-12 else (s - cumulative[j]) / span
        out.append(lerp(fine[j], fine[j + 1], min(1.0, max(0.0, f))))
        out_vals.append(lerp(fine_vals[j], fine_vals[j + 1], min(1.0, max(0.0, f))))
    return out, out_vals


def frames(path, ref):
    """Parallel-transport frames (tangent, normal, binormal) along a path; the first normal leans toward ref."""
    n = len(path)
    tangents = []
    for i in range(n):
        a, b = path[max(0, i - 1)], path[min(n - 1, i + 1)]
        tangents.append(norm(sub(b, a)))
    normal = perpendicular(tangents[0], ref)
    out = []
    for t in tangents:
        normal = perpendicular(t, normal)
        out.append((t, normal, cross(t, normal)))
    return out


# ---------------------------------------------------------------- parts

def loft(name, rings, material, paint=None, draw=None, closed_path=False, cap=True):
    """rings: lists of equal length. paint(i, j) -> material name or None for the default."""
    return {"kind": "loft", "name": name, "rings": rings, "material": material, "paint": paint,
            "draw": draw, "closed_path": closed_path, "cap": cap}


def tube(name, control, radii, material, step=0.03, segments=24, ref=UP, flat=(1.0, 1.0), paint=None,
         closed=False):
    """A swept tube. radii: one number per control point, or (rx, ry) pairs for an elliptic section
    (rx along the frame normal, which leans toward ref; ry along the binormal).
    paint(t, a_degrees, centre) -> material or None; a = 0 on the ref side, 90 toward the binormal."""
    values = [(r * flat[0], r * flat[1]) if isinstance(r, (int, float)) else tuple(r) for r in radii]
    if closed:
        control = list(control) + [control[0]]
        values = values + [values[0]]
    path, vals = smooth_path(control, values, step)
    if closed:
        path, vals = path[:-1], vals[:-1]
    fr = frames(path, ref)
    rings = []
    for c, (rx, ry), (_, nrm, bin_) in zip(path, vals, fr):
        rings.append([combine((c, 1), (nrm, rx * math.cos(2 * math.pi * j / segments)),
                              (bin_, ry * math.sin(2 * math.pi * j / segments))) for j in range(segments)])
    last = max(1, len(path) - 1)
    face_paint = None
    if paint:
        face_paint = lambda i, j: paint((i + 0.5) / last, 360.0 * (j + 0.5) / segments, path[i])
    part = loft(name, rings, material, face_paint, closed_path=closed,
                draw={"type": "tube", "path": path, "radii": [max(v) for v in vals], "paint": paint, "frames": fr})
    part["sweep"] = {"path": path, "radii": vals, "frames": fr}
    return part


def surface(part, t, a):
    """Point and outward normal on a tube at fraction t along it and angle a (degrees)."""
    sw = part["sweep"]
    i = min(len(sw["path"]) - 1, max(0, int(round(t * (len(sw["path"]) - 1)))))
    c, (rx, ry), (_, nrm, bin_) = sw["path"][i], sw["radii"][i], sw["frames"][i]
    ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
    point = combine((c, 1), (nrm, rx * ca), (bin_, ry * sa))
    normal = norm(combine((nrm, ca / max(rx, 1e-6)), (bin_, sa / max(ry, 1e-6))))
    return point, normal, max(rx, ry)


def cone(name, base, tip, radius, material, bend=None, segments=8):
    """A tapering spike from base to tip; bend pushes the middle sideways so it hooks."""
    mid = lerp(base, tip, 0.5)
    if bend:
        mid = add(mid, bend)
    ref = perpendicular(norm(sub(tip, base)), UP)
    return tube(name, [base, mid, tip], [radius, radius * 0.55, radius * 0.06], material,
                step=max(0.004, length(sub(tip, base)) / 6), segments=segments, ref=ref)


def ellipsoid(name, centre, axes, radii, material, segments=(16, 10)):
    return {"kind": "ellipsoid", "name": name, "centre": centre, "axes": axes, "radii": radii,
            "material": material, "segments": segments}


def eye(name, point, normal, radius, up_hint=UP):
    """A small wet dark eye sunk deep in its socket: it should catch a highlight, never glow."""
    up = perpendicular(normal, up_hint)
    side = cross(normal, up)
    return [ellipsoid(name, add(point, mul(normal, -radius * 0.35)), (normal, up, side),
                      (radius * 0.8, radius, radius * 1.1), "EyeDark", (12, 8))]


def feather(name, root, direction, plane_normal, length_m, width, material, rng, curl=0.08,
            ragged=0.0, lead=0.6, stations=10):
    """A flight feather: a vane in the plane, a raised shaft, curling out of the plane toward plane_normal."""
    d = norm(direction)
    side = norm(cross(plane_normal, d))
    rings, left_edge, right_edge = [], [], []
    for k in range(stations + 1):
        s = k / stations
        half = 0.5 * width * (0.45 + 0.55 * math.sin(math.pi * s * 0.9)) * (1 - s ** 3)
        half = max(half, width * 0.02)
        if ragged and 0 < k < stations and rng.random() < ragged:
            half *= rng.uniform(0.55, 0.85)
        centre = combine((root, 1), (d, s * length_m), (plane_normal, curl * length_m * s * s))
        thick = 0.012 * (1 - 0.7 * s) + 0.002
        lw, rw = half * lead * 2 / (1 + lead), half * 2 / (1 + lead)
        L, R = add(centre, mul(side, -lw)), add(centre, mul(side, rw))
        rings.append([L,
                      combine((centre, 1), (side, -lw * 0.5), (plane_normal, thick * 0.5)),
                      add(centre, mul(plane_normal, thick)),
                      combine((centre, 1), (side, rw * 0.5), (plane_normal, thick * 0.5)),
                      R,
                      combine((centre, 1), (side, rw * 0.5), (plane_normal, -thick * 0.4)),
                      add(centre, mul(plane_normal, -thick * 0.8)),
                      combine((centre, 1), (side, -lw * 0.5), (plane_normal, -thick * 0.4))])
        left_edge.append(L)
        right_edge.append(R)
    return loft(name, rings, material, draw={"type": "outline", "points": left_edge + right_edge[::-1]})


def slab(name, outline, normal, thickness, material):
    """A flat polygon given thickness along normal (foot webs)."""
    top = [add(p, mul(normal, thickness / 2)) for p in outline]
    bottom = [add(p, mul(normal, -thickness / 2)) for p in outline]
    return loft(name, [bottom, top], material, draw={"type": "outline", "points": outline})


# ---------------------------------------------------------------- the goose

def body_paint(t, a, centre):
    y = centre[1]
    around = a if a <= 180 else 360 - a  # 0 on top, 180 underneath
    if around > 128 and y > -0.35:
        return "ChinWhite"
    if around > 62 and y < -0.42:  # straight seam: a curved one stair-steps on the face grid
        # a dried-blood stain spreading round the maw (y -1.3, underneath), with a ragged wobbling edge
        spread = math.hypot((y + 1.30) / 0.32, (around - 180) / 38)
        edge = 1.0 + 0.30 * math.sin(math.radians(a) * 7) * math.cos(y * 11) + 0.15 * math.sin(math.radians(a) * 17)
        if spread < edge:
            return "MawRed"
        return "BreastPale"
    phase = ((y + 3.0) / 0.14) % 1.0
    if 40 < around < 118 and phase < 0.28:  # narrow pale feather-edge bars on the flanks
        return "PlumageEdge"
    return None


def build_body(D):
    rings = D["body_rings"]["rings"]
    return tube("body", [(0.0, y, z) for y, z, _, _ in rings], [(h, w) for _, _, w, h in rings],
                "PlumageBrown", step=0.035, segments=48, ref=UP, paint=body_paint)


def build_head(prefix, spec_head, rng, sign=1):
    """A goose head on a neck end: crown, chinstrap, one sunken eye a side, a gaping toothed beak, a spiked tongue."""
    s = spec_head["scale"]
    base, f = tuple(spec_head["base"]), norm(spec_head["dir"])
    u = perpendicular(f, UP)
    side = cross(f, u)
    jaw = spec_head["jaw_open_deg"]
    parts = []

    stations = [-0.10, 0.0, 0.10, 0.22, 0.32, 0.40]
    crown = [0.0, 0.02, 0.04, 0.03, 0.0, -0.02]
    radii = [0.17, 0.20, 0.22, 0.20, 0.16, 0.12]
    control = [combine((base, 1), (f, k * s), (u, c * s)) for k, c in zip(stations, crown)]

    def chinstrap(t, a, _):
        along = -0.10 + 0.50 * t
        return "ChinWhite" if 0.0 < along < 0.24 - 0.05 * math.cos(math.radians(a)) and 100 < a < 260 else None

    head = tube(prefix + "_head", control, [(r * s, r * s * 0.82) for r in radii], "GooseBlack",
                step=0.022 * s, segments=36, ref=u, paint=chinstrap)
    parts.append(head)

    for a_side, tag in ((60, "R"), (300, "L")):
        p, n, _ = surface(head, (0.27 + 0.10) / 0.50, a_side)
        parts += eye(f"{prefix}_eye_{tag}", p, n, 0.034 * s, u)

    for k in range(5):  # crest of quills behind the head
        a = -40 + 20 * k
        p, n, _ = surface(head, 0.12, a)
        tip = combine((p, 1), (n, 0.10 * s), (f, -0.20 * s), (u, 0.05 * s))
        parts.append(cone(f"{prefix}_quill{k}", add(p, mul(n, -0.02 * s)), tip, 0.022 * s, "ToothBone",
                          bend=mul(u, 0.02 * s)))

    beak_base = combine((base, 1), (f, 0.36 * s))
    jaws = []
    for label, angle, offset, length_m, rr, flat_v in (("upper", jaw * 0.3, 0.03, 0.42, [0.11, 0.09, 0.06, 0.02], 0.5),
                                                       ("lower", -jaw * 0.7, -0.04, 0.37, [0.09, 0.075, 0.05, 0.018], 0.45)):
        d = rotate(f, side, angle)
        du = perpendicular(d, u)
        start = add(beak_base, mul(u, offset * s))
        hook = -0.04 if label == "upper" else 0.02
        ctrl = [combine((start, 1), (d, k * length_m * s), (du, (hook * s if k == 1.0 else 0.0)))
                for k in (0.0, 0.35, 0.7, 1.0)]
        mandible = tube(f"{prefix}_{label}_beak", ctrl, [(r * s * flat_v, r * s) for r in rr], "GooseBlack",
                        step=0.015 * s, segments=24, ref=du)
        parts.append(mandible)
        jaws.append((label, mandible, du, d))

    for label, mandible, du, d in jaws:  # teeth on the inner edges, pointing at the other jaw
        inward = mul(du, -1) if label == "upper" else du
        edge = 180 if label == "upper" else 0
        for k in range(9):
            t = 0.12 + 0.72 * k / 8
            for a_side in (edge - 62, edge + 62):
                p, _, _ = surface(mandible, t, a_side)
                size = (0.055 if k in (1, 2) else 0.036) * s * rng.uniform(0.85, 1.15)
                tip = combine((p, 1), (inward, size), (d, -size * 0.35))
                parts.append(cone(f"{prefix}_{label}_tooth{k}_{a_side}", p, tip, 0.011 * s, "ToothBone"))

    mouth_dir = rotate(f, side, -jaw * 0.2)
    mu = perpendicular(mouth_dir, u)
    mouth_ctrl = [combine((beak_base, 1), (mouth_dir, k * s)) for k in (-0.06, 0.08, 0.20)]
    parts.append(tube(f"{prefix}_mouth", mouth_ctrl, [(0.05 * s, 0.08 * s), (0.09 * s, 0.07 * s), (0.10 * s, 0.05 * s)],
                      "MawRed", step=0.02 * s, segments=20, ref=mu))

    if spec_head.get("tongue"):
        tctrl = [combine((beak_base, 1), (mouth_dir, 0.02 * s)),
                 combine((beak_base, 1), (mouth_dir, 0.26 * s), (mu, 0.01 * s)),
                 combine((beak_base, 1), (mouth_dir, 0.46 * s), (mu, 0.09 * s), (side, 0.04 * s * sign)),
                 combine((beak_base, 1), (mouth_dir, 0.56 * s), (mu, 0.20 * s), (side, 0.02 * s * sign))]
        tongue = tube(f"{prefix}_tongue", tctrl, [0.045 * s, 0.04 * s, 0.028 * s, 0.01 * s], "MawRed",
                      step=0.012 * s, segments=16, ref=mu)
        parts.append(tongue)
        for k in range(6):
            for a_side in (70, 290):
                p, n, _ = surface(tongue, 0.15 + 0.12 * k, a_side)
                back = mul(tongue["sweep"]["frames"][0][0], -1)
                parts.append(cone(f"{prefix}_tongue_spike{k}_{a_side}", p,
                                  combine((p, 1), (n, 0.025 * s), (back, 0.02 * s)), 0.007 * s, "ToothBone",
                                  segments=6))
    return parts


def build_necks(D, rng):
    parts = []
    main = tube("main_neck", D["main_neck"]["path"], D["main_neck"]["radii"], "GooseBlack",
                step=0.03, segments=36, ref=(0.0, 1.0, 0.0))
    parts.append(main)
    for k in range(13):  # bone ridge down the back of the neck
        t = 0.10 + 0.78 * k / 12
        p, n, r = surface(main, t, 0)
        tangent = main["sweep"]["frames"][int(t * (len(main["sweep"]["path"]) - 1))][0]
        size = 0.14 + 0.08 * math.sin(math.pi * k / 12)
        parts.append(cone(f"neck_spine{k}", add(p, mul(n, -0.03)), combine((p, 1), (n, size), (tangent, -size * 0.6)),
                          0.04, "ToothBone", bend=mul(tangent, -0.02)))
    parts += build_head("main", D["main_head"], rng)

    for sign in (1, -1):
        tag = "R" if sign > 0 else "L"
        ctrl = [p if sign > 0 else mirror(p) for p in D["side_neck"]["path"]]
        neck = tube(f"side_neck_{tag}", ctrl, D["side_neck"]["radii"], "GooseBlack", step=0.03, segments=30,
                    ref=(0.0, 1.0, 0.0))
        parts.append(neck)
        head = dict(D["side_head"])
        if sign < 0:
            head["base"] = mirror(head["base"])
            head["dir"] = mirror(head["dir"])
        parts += build_head(f"side_{tag}", head, rng, sign)
    return parts


def build_wing(W, sign, rng):
    pick = (lambda p: tuple(p)) if sign > 0 else (lambda p: mirror(p))
    shoulder, elbow, wrist, tip = (pick(W[k]) for k in ("shoulder", "elbow", "wrist", "tip"))
    tag = "R" if sign > 0 else "L"
    parts = []
    arm = tube(f"wing_arm_{tag}", [shoulder, elbow, wrist, tip], W["radii"], "PlumageBrown", step=0.03,
               segments=20, ref=(0.0, -1.0, 0.0))
    parts.append(arm)

    span = norm(sub(tip, shoulder))
    plane_normal = norm(cross(span, (0.0, 0.0, -1.0)))  # points back (+Y) on both wings
    if plane_normal[1] < 0:
        plane_normal = mul(plane_normal, -1)
    front = mul(plane_normal, -1)

    def fan(name, a, b, count, angles, lengths, width, material, layer, ragged, lead=1.0, curl=0.08):
        seg = norm(sub(b, a))
        down = perpendicular(seg, (0.0, 0.0, -1.0))
        down = perpendicular(plane_normal, down)  # keep the fan in the wing plane
        out = []
        for k in range(count):
            f = k / max(1, count - 1)
            root = combine((lerp(a, b, f), 1), (front, layer + 0.006 * k))
            theta = math.radians(angles[0] + (angles[1] - angles[0]) * f)
            d = norm(combine((seg, math.cos(theta)), (down, math.sin(theta))))
            length_m = lengths[0] + (lengths[1] - lengths[0]) * f
            out.append(feather(f"{name}{k}_{tag}", root, d, plane_normal, length_m, width, material, rng,
                               curl=curl, ragged=ragged, lead=lead))
        return out

    p_len, s_len = W["primary_length"], W["secondary_length"]
    # primaries: from the tip (pointing out along the hand) back to the wrist (pointing down)
    parts += fan("primary", tip, wrist, W["primaries"], (12, 72), (p_len[0], p_len[1]), 0.17, "PrimaryDark",
                 0.0, 0.6, lead=0.55)
    parts += fan("secondary", wrist, elbow, W["secondaries"], (82, 100), (s_len[0], s_len[1]), 0.20,
                 "PlumageBrown", 0.0, 0.5)
    parts += fan("tertial", elbow, lerp(elbow, shoulder, 0.85), W["tertials"], (100, 115), (0.85, 0.70), 0.20,
                 "PlumageBrown", 0.0, 0.35)
    parts += fan("covert", lerp(wrist, tip, 0.6), lerp(elbow, shoulder, 0.3), 16, (60, 100), (0.55, 0.50), 0.16,
                 "PlumageEdge", 0.06, 0.0, curl=0.05)
    parts += fan("lesser_covert", lerp(wrist, tip, 0.3), elbow, 11, (70, 100), (0.32, 0.30), 0.14,
                 "PlumageBrown", 0.12, 0.0, curl=0.04)

    hand = norm(sub(tip, wrist))
    down = perpendicular(hand, (0.0, 0.0, -1.0))
    for k in range(W["finger_bones"]):  # bare finger bones breaking out past the primaries
        angle = 8 + 24 * k
        d = norm(combine((hand, math.cos(math.radians(angle))), (down, math.sin(math.radians(angle))),
                         (front, 0.12)))
        L = W["finger_bone_length"] * (1 - 0.15 * k)
        start = lerp(wrist, tip, 0.75)
        joint = combine((start, 1), (d, L * 0.55), (mul(down, -1), 0.10))
        end = combine((start, 1), (d, L))
        parts.append(tube(f"finger_bone{k}_{tag}", [start, joint, end], [0.045, 0.032, 0.022], "ToothBone",
                          step=0.03, segments=12))
        knuckle = ellipsoid(f"knuckle{k}_{tag}", joint, (d, down, plane_normal), (0.06, 0.05, 0.05), "ToothBone")
        parts.append(knuckle)
        parts.append(cone(f"finger_claw{k}_{tag}", end, combine((end, 1), (d, 0.12), (down, 0.10)), 0.026,
                          "ToothBone", bend=mul(down, 0.03)))

    return parts


def build_leg(L, sign):
    pick = (lambda p: tuple(p)) if sign > 0 else (lambda p: mirror(p))
    tag = "R" if sign > 0 else "L"
    hip, knee, ankle, foot = (pick(L[k]) for k in ("hip", "knee", "ankle", "foot"))
    parts = [tube(f"leg_{tag}", [hip, knee, ankle, foot], L["radii"], "LegDark", step=0.025, segments=24,
                  ref=(0.0, -1.0, 0.0))]
    for k in range(5):  # scutes: raised scale rings on the shank
        c = lerp(ankle, foot, 0.1 + 0.18 * k)
        r = L["radii"][2] * 1.04
        axis = norm(sub(foot, ankle))
        u = perpendicular(axis, (0.0, -1.0, 0.0))
        v = cross(axis, u)
        ring = [combine((c, 1), (u, r * math.cos(2 * math.pi * j / 16)), (v, r * math.sin(2 * math.pi * j / 16)))
                for j in range(16)]
        parts.append(tube(f"scute{k}_{tag}", ring, [0.012] * 16, "LegDark", step=0.02, segments=6, ref=axis,
                          closed=True))

    toes = []
    spread = L["toe_spread_deg"]
    ground = 0.045
    for k, angle in enumerate((-spread, 0.0, spread)):
        d = rotate((0.0, -1.0, 0.0), UP, angle * sign)
        tl = L["toe_length"] * (0.85 if k != 1 else 1.0)
        ctrl = [foot, combine((foot, 1), (d, tl * 0.35), (UP, ground + 0.03 - foot[2])),
                combine((foot, 1), (d, tl * 0.7), (UP, ground + 0.005 - foot[2])),
                combine((foot, 1), (d, tl), (UP, ground - foot[2]))]
        toe = tube(f"toe{k}_{tag}", ctrl, [0.05, 0.04, 0.032, 0.026], "LegDark", step=0.02, segments=14)
        parts.append(toe)
        toes.append((toe, d))
        end = ctrl[-1]
        parts.append(cone(f"claw{k}_{tag}", end, combine((end, 1), (d, 0.11), (UP, -0.04)), 0.024, "ToothBone",
                          bend=(0.0, 0.0, 0.02)))
    for k in range(2):  # webs between neighbouring toes, scalloped at the front edge
        (ta, da), (tb, db) = toes[k], toes[k + 1]
        pa = ta["sweep"]["path"]
        pb = tb["sweep"]["path"]
        edge_a = [pa[int(f * (len(pa) - 1))] for f in (0.15, 0.4, 0.65, 0.88)]
        edge_b = [pb[int(f * (len(pb) - 1))] for f in (0.88, 0.65, 0.4, 0.15)]
        scallop = lerp(edge_a[-1], edge_b[0], 0.5)
        scallop = add(scallop, mul(norm(sub(foot, scallop)), 0.07))
        outline = [(foot[0], foot[1], ground + 0.02)] + edge_a + [scallop] + edge_b
        outline = [(p[0], p[1], ground + 0.01) for p in outline]
        parts.append(slab(f"web{k}_{tag}", outline, UP, 0.016, "LegDark"))
    back_toe_end = combine((foot, 1), ((0.0, 1.0, 0.0), 0.14), (UP, 0.06 - foot[2]))
    parts.append(tube(f"hallux_{tag}", [foot, back_toe_end], [0.035, 0.02], "LegDark", step=0.02, segments=10))
    return parts


def build_breast_maw(M, body):
    """A vertical mouth on the breast: raw lips, a ring of teeth, a dark throat."""
    sw = body["sweep"]
    i = min(range(len(sw["path"])), key=lambda k: abs(sw["path"][k][1] - M["body_y"]))
    t = i / (len(sw["path"]) - 1)
    point, normal, _ = surface(body, t, 180)
    # tip the mouth to face forward-down regardless of how steep the breast is there
    normal = norm(combine((normal, 1), ((0.0, -1.0, 0.0), 1.2)))
    up = perpendicular(normal, UP)
    side = cross(normal, up)
    centre = add(point, mul(normal, -0.05))
    hw, hh = M["half_width"], M["half_height"]
    parts = []
    rim = []
    for k in range(28):
        ang = 2 * math.pi * k / 28
        rim.append(combine((centre, 1), (side, hw * math.cos(ang)), (up, hh * math.sin(ang))))
    lip_r = [M["lip_radius"] * (0.75 + 0.45 * abs(math.cos(2 * math.pi * k / 28))) for k in range(28)]
    parts.append(tube("maw_lips", rim, lip_r, "RawFlesh", step=0.03, segments=14, ref=normal, closed=True))
    parts.append(ellipsoid("maw_throat", add(centre, mul(normal, -0.06)), (side, up, normal),
                           (hw * 0.95, hh * 0.95, 0.16), "MawDark", (20, 12)))
    parts.append(ellipsoid("maw_gums", add(centre, mul(normal, -0.015)), (side, up, normal),
                           (hw * 1.02, hh * 1.0, 0.06), "MawRed", (24, 12)))
    for k in range(M["teeth"]):
        ang = 2 * math.pi * (k + 0.5) / M["teeth"]
        edge = combine((centre, 1), (side, hw * 0.9 * math.cos(ang)), (up, hh * 0.9 * math.sin(ang)))
        inward = norm(sub(centre, edge))
        size = 0.10 + 0.05 * abs(math.sin(ang))
        tip = combine((edge, 1), (inward, size * 0.75), (normal, size * 0.55))
        parts.append(cone(f"maw_tooth{k}", add(edge, mul(normal, 0.02)), tip, 0.022, "ToothBone",
                          bend=mul(normal, 0.015)))
    return parts


def build_tail(T, rng):
    parts = []
    root = tuple(T["root"])
    base_dir = norm((0.0, 1.0, 0.55))
    plane_normal = norm(cross((1.0, 0.0, 0.0), base_dir))
    for k in range(T["feathers"]):
        angle = -T["spread_deg"] / 2 + T["spread_deg"] * k / (T["feathers"] - 1)
        d = rotate(base_dir, plane_normal, angle)
        spread = angle / (T["spread_deg"] / 2)  # -1 .. 1 across the fan
        d = norm(combine((d, 1), (plane_normal, -0.35 * abs(spread))))  # outer feathers droop: a cupped fan
        own_normal = perpendicular(d, rotate(plane_normal, d, 50 * spread))  # bank like fanned cards
        length_m = T["length"] * (1.0 - 0.15 * abs(spread))
        r = add(root, mul(plane_normal, 0.012 * (T["feathers"] // 2 - abs(k - T["feathers"] // 2))))
        parts.append(feather(f"tail{k}", r, d, own_normal, length_m, 0.22, "GooseBlack", rng, curl=-0.05,
                             ragged=0.45))
    return parts


def build_back_spines(body, rng):
    parts = []
    for k in range(12):
        t = 0.18 + 0.55 * k / 11
        for a, scale in ((0, 1.0), (24, 0.6), (336, 0.6)):
            p, n, _ = surface(body, t, a)
            size = scale * (0.20 + 0.12 * math.sin(math.pi * k / 11)) * rng.uniform(0.85, 1.15)
            tip = combine((p, 1), (n, size), ((0.0, 1.0, 0.0), size * 0.5))
            parts.append(cone(f"back_spine{k}_{a}", add(p, mul(n, -0.03)), tip, 0.05 * scale, "ToothBone",
                              bend=(0.0, 0.03, 0.0)))
    return parts


def body_ribs(body):
    """Bare ribs breaking through the matted flanks: the starved-beast look, where the eyes used to be."""
    parts = []
    for side_sign, tag in ((1, "R"), (-1, "L")):
        for k in range(5):
            t = 0.28 + 0.32 * k / 4
            arc = [a if side_sign > 0 else 360 - a for a in (52, 66, 80, 94, 108, 120)]
            ctrl = []
            for m, a in enumerate(arc):
                p, n, _ = surface(body, t + 0.012 * m, a)  # each rib sweeps slightly back as it goes down
                ctrl.append(add(p, mul(n, 0.035 * math.sin(math.pi * (m + 0.5) / len(arc)))))
            size = 0.030 + 0.012 * math.sin(math.pi * k / 4)
            parts.append(tube(f"rib{k}_{tag}", ctrl, [size * 0.7, size, size, size * 0.9, size * 0.7, size * 0.45],
                              "ToothBone", step=0.04, segments=10))
    return parts


def build_parts(spec=None):
    spec = spec or load_spec()
    D = spec["design"]
    rng = random.Random(D["eye_seed"])
    body = build_body(D)
    parts = [body]
    parts += body_ribs(body)
    parts += build_back_spines(body, rng)
    parts += build_breast_maw(D["breast_maw"], body)
    parts += build_necks(D, rng)
    for sign in (1, -1):
        parts += build_wing(D["wing"], sign, rng)
        parts += build_leg(D["legs"], sign)
    parts += build_tail(D["tail"], rng)
    return parts


# ---------------------------------------------------------------- meshing

def mesh_parts(parts):
    """All parts as one vertex list, polygon list and per-polygon material name. Each part is a closed shell."""
    verts, faces, mats = [], [], []
    for part in parts:
        if part["kind"] == "ellipsoid":
            _mesh_ellipsoid(part, verts, faces, mats)
        else:
            _mesh_loft(part, verts, faces, mats)
    return verts, faces, mats


def _mesh_loft(part, verts, faces, mats):
    rings = part["rings"]
    base = len(verts)
    width = len(rings[0])
    for ring in rings:
        if len(ring) != width:
            raise ValueError(f"{part['name']}: rings differ in length")
        verts.extend(ring)
    n = len(rings)
    spans = n if part["closed_path"] else n - 1
    for i in range(spans):
        i2 = (i + 1) % n
        for j in range(width):
            j2 = (j + 1) % width
            faces.append((base + i * width + j, base + i * width + j2, base + i2 * width + j2, base + i2 * width + j))
            m = part["paint"](i, j) if part["paint"] else None
            mats.append(m or part["material"])
    if part["cap"] and not part["closed_path"]:
        faces.append(tuple(base + j for j in reversed(range(width))))
        mats.append(part["material"])
        faces.append(tuple(base + (n - 1) * width + j for j in range(width)))
        mats.append(part["material"])


def _mesh_ellipsoid(part, verts, faces, mats):
    us, vs = part["segments"]
    c, (ax, ay, az), (rx, ry, rz) = part["centre"], part["axes"], part["radii"]
    base = len(verts)
    verts.append(combine((c, 1), (ax, -rx)))  # pole along the first axis
    for i in range(1, vs):
        phi = math.pi * i / vs
        for j in range(us):
            th = 2 * math.pi * j / us
            verts.append(combine((c, 1), (ax, -rx * math.cos(phi)), (ay, ry * math.sin(phi) * math.cos(th)),
                                 (az, rz * math.sin(phi) * math.sin(th))))
    verts.append(combine((c, 1), (ax, rx)))
    top, bottom = base, len(verts) - 1
    ring = lambda i, j: base + 1 + (i - 1) * us + (j % us)
    for j in range(us):
        faces.append((top, ring(1, j + 1), ring(1, j)))
        mats.append(part["material"])
    for i in range(1, vs - 1):
        for j in range(us):
            faces.append((ring(i, j), ring(i, j + 1), ring(i + 1, j + 1), ring(i + 1, j)))
            mats.append(part["material"])
    for j in range(us):
        faces.append((bottom, ring(vs - 1, j), ring(vs - 1, j + 1)))
        mats.append(part["material"])


def triangle_count(faces):
    return sum(len(f) - 2 for f in faces)


if __name__ == "__main__":
    ps = build_parts()
    v, f, m = mesh_parts(ps)
    zs = [p[2] for p in v]
    xs = [p[0] for p in v]
    print(f"{len(ps)} parts, {len(v)} verts, {triangle_count(f)} tris, "
          f"z {min(zs):.3f}..{max(zs):.3f}, x {min(xs):.3f}..{max(xs):.3f}")
