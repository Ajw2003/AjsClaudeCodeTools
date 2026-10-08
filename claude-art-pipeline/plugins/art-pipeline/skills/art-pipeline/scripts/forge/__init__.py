"""forge: an engine-free model forge for Blender-as-a-module (bpy + Pillow, stdlib otherwise).

A project writes a spec JSON and a blueprints.py; `python3.13 forge/build.py --spec ...
--blueprints ... --out ...` builds, validates and exports each asset. See README.md.
"""


from .blueprint import Blueprint
from .figure import UNITY_HUMANOID, Human
from .kit import KINDS, Part, arc_path, gable_outline, ring_of, rounded_rect, section, spline
from .spec import Entry, load_spec

__all__ = ["Blueprint", "Human", "UNITY_HUMANOID", "Part", "KINDS", "Entry", "load_spec",
           "arc_path", "gable_outline", "ring_of", "rounded_rect", "section", "spline"]
