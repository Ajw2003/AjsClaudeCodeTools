"""One material slot: a palette texture.

Every family gets a 16 px cell in an 8x8 grid (128x128 PNG, written with Pillow);
kit.build_bmesh points each face's UVs at its family's cell centre. No bake, no
unwrap, nothing that can fail on thin geometry: the single baked-material
contract (one slot, UVs in 0..1, one texture) holds by construction.
"""

from __future__ import annotations

import os

import bpy
from PIL import Image

GRID, CELL = 8, 16
ROUGHNESS = 0.7


def cell_centres(families: list[str]) -> dict[str, tuple[float, float]]:
    if len(families) > GRID * GRID:
        raise ValueError(f"{len(families)} families; the palette holds {GRID * GRID}")
    return {key: (((i % GRID) + 0.5) / GRID, ((i // GRID) + 0.5) / GRID)
            for i, key in enumerate(families)}


def write_palette(path: str, families: list[str], spec_families: dict) -> None:
    img = Image.new("RGB", (GRID * CELL, GRID * CELL), (255, 0, 255))   # unused cells: magenta
    for i, key in enumerate(families):
        col, row = i % GRID, i // GRID
        rgb = tuple(int(spec_families[key]["base"][j:j + 2], 16) for j in (1, 3, 5))
        # PNG rows run top-down, Blender's v runs bottom-up.
        img.paste(rgb, (col * CELL, (GRID - 1 - row) * CELL, (col + 1) * CELL, (GRID - row) * CELL))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)


def build_material(name: str, texture_path: str) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = ROUGHNESS
    bsdf.inputs["Metallic"].default_value = 0.0
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(texture_path)
    tex.image.colorspace_settings.name = "sRGB"
    tex.interpolation = "Closest"    # no bleeding between palette cells
    links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return mat
