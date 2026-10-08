"""A parametric humanoid: skeleton plus body parts already bound to it.

    fig = Human(height=entry.height_m)
    parts = fig.body(skin="skin", torso="cloth", legs="cloth", feet="boots")
    hat = Part("cone", loc=fig.joint("Head") + Vector((0, 0, 0.12)), ..., bone="Head", rigid=True)
    return Blueprint(parts=parts + [hat], **fig.rig())

The figure stands on z = 0, centred on x = y = 0, faces -Y; ".L" is +X (the viewer's
right in a front view). Proportions are fractions of the height. Bone names follow Unity
Humanoid (Mecanim) with Blender side suffixes:

    Root > Hips > Spine > Chest > Neck > Head
                          Chest > UpperArm.X > LowerArm.X > Hand.X
                  Hips > UpperLeg.X > LowerLeg.X > Foot.X

`UNITY_HUMANOID` maps Unity's HumanBodyBones to these names, for building an Avatar by
hand if the importer's auto-mapping misreads the suffixes. Extra bones (a hat, a lantern
chain) hang off these with `add_bone`. The arms rest in an A-pose, `arm_angle` degrees
off vertical.
"""

from __future__ import annotations

import math

from mathutils import Vector

from .kit import Part

UNITY_HUMANOID = {
    "Hips": "Hips", "Spine": "Spine", "Chest": "Chest", "Neck": "Neck", "Head": "Head",
    "LeftUpperArm": "UpperArm.L", "LeftLowerArm": "LowerArm.L", "LeftHand": "Hand.L",
    "RightUpperArm": "UpperArm.R", "RightLowerArm": "LowerArm.R", "RightHand": "Hand.R",
    "LeftUpperLeg": "UpperLeg.L", "LeftLowerLeg": "LowerLeg.L", "LeftFoot": "Foot.L",
    "RightUpperLeg": "UpperLeg.R", "RightLowerLeg": "LowerLeg.R", "RightFoot": "Foot.R",
}


def _t(v) -> tuple:
    return (round(v[0], 6), round(v[1], 6), round(v[2], 6))


class Human:
    def __init__(self, height: float = 1.75, bulk: float = 1.0, arm_angle: float = 25.0):
        self.height = H = height
        self.bulk = bulk                       # scales girth, not length
        self.arm_angle = arm_angle
        self.bones: list[dict] = []
        hip_x, sh_x = 0.05 * H, 0.115 * H
        ankle_z = 0.045 * H
        a = math.radians(arm_angle)
        arm = Vector((math.sin(a), 0.0, -math.cos(a)))
        shoulder = Vector((sh_x, 0.0, 0.775 * H))
        elbow = shoulder + arm * 0.17 * H
        wrist = elbow + arm * 0.15 * H
        hand_tip = wrist + arm * 0.10 * H

        self.add_bone("Root", (0, 0, 0), (0, 0, 0.08 * H), None)
        self.add_bone("Hips", (0, 0, 0.52 * H), (0, 0, 0.57 * H), "Root")
        self.add_bone("Spine", (0, 0, 0.57 * H), (0, 0, 0.65 * H), "Hips")
        self.add_bone("Chest", (0, 0, 0.65 * H), (0, 0, 0.79 * H), "Spine")
        self.add_bone("Neck", (0, 0, 0.79 * H), (0, 0, 0.84 * H), "Chest")
        self.add_bone("Head", (0, 0, 0.84 * H), (0, 0, 0.995 * H), "Neck")
        self.add_bone("UpperArm.L", shoulder, elbow, "Chest", mirror=True)
        self.add_bone("LowerArm.L", elbow, wrist, "UpperArm.L", mirror=True)
        self.add_bone("Hand.L", wrist, hand_tip, "LowerArm.L", mirror=True)
        self.add_bone("UpperLeg.L", (hip_x, 0, 0.52 * H), (hip_x, 0, 0.28 * H), "Hips", mirror=True)
        self.add_bone("LowerLeg.L", (hip_x, 0, 0.28 * H), (hip_x, 0, ankle_z), "UpperLeg.L", mirror=True)
        self.add_bone("Foot.L", (hip_x, 0, ankle_z), (hip_x, -0.11 * H, ankle_z), "LowerLeg.L", mirror=True)

    # ---- skeleton -----------------------------------------------------------------

    def add_bone(self, name: str, head, tail, parent: str | None, mirror: bool = False) -> str:
        """Add a bone (an extra: hat, prop). ".L" names with mirror=True also create ".R"."""
        if any(b["name"] == name for b in self.bones):
            raise ValueError(f"bone {name!r} already exists")
        rec = {"name": name, "head": _t(head), "tail": _t(tail), "parent": parent}
        if mirror:
            rec["mirror"] = True
        self.bones.append(rec)
        return name

    def bone(self, name: str) -> tuple[Vector, Vector]:
        """(head, tail) of a bone; ".R" names are the ".L" bone mirrored."""
        side_r = name.endswith(".R")
        key = name[:-2] + ".L" if side_r else name
        for b in self.bones:
            if b["name"] == key:
                h, t = Vector(b["head"]), Vector(b["tail"])
                if side_r:
                    h.x, t.x = -h.x, -t.x
                return h, t
        raise KeyError(name)

    def joint(self, name: str) -> Vector:
        return self.bone(name)[0]

    def along(self, name: str, t: float) -> Vector:
        h, tl = self.bone(name)
        return h + (tl - h) * t

    def rig(self) -> dict:
        """Keyword arguments for Blueprint(...)."""
        return {"bones": [dict(b) for b in self.bones], "forward_bones": ["Foot.L", "Foot.R"]}

    # ---- body parts ---------------------------------------------------------------

    def _limb(self, bone: str, r0: float, r1: float, mat: str, *, rn_scale=1.0,
              segments: int = 10, joint: bool = False) -> Part:
        """A tapered round limb along a bone, mirrored if the bone is."""
        h, t = self.bone(bone)
        k = self.height * self.bulk
        mid = (h + t) * 0.5
        return Part("sweep", mat=mat, bone=bone, mirror=True, segments=segments, smooth=True,
                    extras={"path": [tuple(h), tuple(mid), tuple(t)],
                            "sections": [(r0 * k * rn_scale, r0 * k), (0.5 * (r0 + r1) * k * rn_scale,
                                         0.5 * (r0 + r1) * k), (r1 * k * rn_scale, r1 * k)]})

    def _torso(self, bone: str, z0: float, z1: float, hw0: float, hw1: float, hd0: float,
               hd1: float, mat: str) -> Part:
        """A rounded-box trunk section: rows from z0 to z1 (fractions of height)."""
        H, k = self.height, self.bulk
        rows = 4
        zs = [(z0 + (z1 - z0) * i / rows) * H for i in range(rows + 1)]
        sec = [((hw0 + (hw1 - hw0) * i / rows) * H * k, (hd0 + (hd1 - hd0) * i / rows) * H * k)
               for i in range(rows + 1)]
        return Part("sweep", mat=mat, bone=bone, segments=16, smooth=True,
                    extras={"path": [(0.0, 0.0, z) for z in zs], "sections": sec,
                            "up": (1.0, 0.0, 0.0), "power": 3.0})

    def body(self, skin: str, torso: str | None = None, sleeves: str | None = None,
             legs: str | None = None, feet: str | None = None,
             joints: str | None = None) -> list[Part]:
        """A mannequin: pelvis, trunk, neck, head, arms, hands, legs, feet.

        Each family defaults to `skin`; `joints` (neck, shoulder caps, knees) defaults to the
        family of the limb it caps. Every part is bound to its own bone and may
        blend with that bone's parent and children (see rig.py). Clothing and props
        go on top, built against `joint()` / `bone()` landmarks.
        """
        torso, sleeves, legs, feet = torso or skin, sleeves or torso or skin, legs or skin, feet or skin
        neck, shoulder, knee = joints or skin, joints or sleeves, joints or legs
        H, k = self.height, self.bulk
        parts = [
            self._torso("Hips", 0.49, 0.605, 0.092, 0.084, 0.058, 0.055, legs),
            self._torso("Spine", 0.585, 0.665, 0.080, 0.078, 0.054, 0.052, torso),
            self._torso("Chest", 0.65, 0.80, 0.082, 0.104, 0.055, 0.050, torso),
            Part("cyl", loc=(0, 0, 0.815 * H), size=(0.06 * H * k, 0.06 * H * k, 0.07 * H), mat=neck,
                 bone="Neck", segments=10, smooth=True),
            Part("sphere", loc=(0, -0.004 * H, 0.915 * H), size=(0.105 * H, 0.125 * H, 0.17 * H),
                 mat=skin, bone="Head", segments=16, rings=10, smooth=True),
            # shoulder caps hide the joint between chest and arm
            Part("sphere", loc=tuple(self.joint("UpperArm.L")), size=(0.075 * H * k,) * 3,
                 mat=shoulder, bone="UpperArm.L", mirror=True, segments=10, rings=6, smooth=True),
            self._limb("UpperArm.L", 0.034, 0.027, sleeves),
            self._limb("LowerArm.L", 0.027, 0.020, sleeves),
            self._limb("Hand.L", 0.019, 0.015, skin, rn_scale=0.55, segments=8),
            self._limb("UpperLeg.L", 0.048, 0.039, legs, segments=12),
            self._limb("LowerLeg.L", 0.041, 0.028, legs, segments=12),
            Part("sphere", loc=tuple(self.joint("LowerLeg.L")), size=(0.095 * H * k,) * 3,
                 mat=knee, bone="LowerLeg.L", mirror=True, segments=10, rings=6, smooth=True),
            Part("box", loc=(0.05 * H, -0.045 * H, 0.0245 * H),
                 size=(0.058 * H * k, 0.165 * H, 0.049 * H), mat=feet, bone="Foot.L", mirror=True, rigid=True),
        ]
        return parts
