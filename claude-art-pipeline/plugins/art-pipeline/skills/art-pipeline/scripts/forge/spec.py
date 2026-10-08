"""The spec file: one JSON, one entry per asset.

    {"assets": {"lantern": {
        "name": "Lantern",               # optional; file/object name, default = slug in PascalCase
        "height_m": 0.40,                # required: the model's height, z = 0 up
        "tolerance": 0.05,               # optional: allowed height error as a fraction (default 0.05)
        "tri_budget": 1500,              # optional (default 2000)
        "dims": [0.2, 0.2, 0.4],         # optional: bbox W (x), D (y), H (z); each axis within dim_tolerance
        "dim_tolerance": 0.10,
        "families": {"iron": {"base": "#2B2B30"}, ...},   # the palette; parts name a family by key
        "clips": {"idle": {}, "walk": {"speed": 1.4}}     # optional; rigged assets only
    }}}
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass
class Entry:
    slug: str
    name: str
    height_m: float
    tolerance: float = 0.05
    tri_budget: int = 2000
    dims: tuple | None = None
    dim_tolerance: float = 0.10
    families: dict = field(default_factory=dict)
    clips: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)


def _pascal(slug: str) -> str:
    return "".join(w.capitalize() for w in re.split(r"[^0-9a-zA-Z]+", slug) if w) or slug


def load_spec(path: str) -> dict[str, Entry]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    assets = data.get("assets")
    if not isinstance(assets, dict) or not assets:
        raise ValueError(f"{path}: needs a non-empty top-level 'assets' object")
    out = {}
    for slug, raw in assets.items():
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", slug):
            raise ValueError(f"{path}: slug {slug!r} must be lowercase letters, digits, - or _")
        if not isinstance(raw.get("height_m"), (int, float)) or raw["height_m"] <= 0:
            raise ValueError(f"{slug}: 'height_m' is required and must be > 0")
        fams = raw.get("families") or {}
        if not fams:
            raise ValueError(f"{slug}: needs at least one entry in 'families'")
        if len(fams) > 64:
            raise ValueError(f"{slug}: at most 64 families (palette is 8x8 cells)")
        for key, fam in fams.items():
            if not _HEX.match(str(fam.get("base", ""))):
                raise ValueError(f"{slug}: family {key!r} needs 'base': '#RRGGBB'")
        dims = raw.get("dims")
        out[slug] = Entry(
            slug=slug, name=raw.get("name") or _pascal(slug), height_m=float(raw["height_m"]),
            tolerance=float(raw.get("tolerance", 0.05)), tri_budget=int(raw.get("tri_budget", 2000)),
            dims=tuple(float(d) for d in dims) if dims else None,
            dim_tolerance=float(raw.get("dim_tolerance", 0.10)),
            families={k: dict(v) for k, v in fams.items()},
            clips=dict(raw.get("clips") or {}), raw=raw)
    return out
