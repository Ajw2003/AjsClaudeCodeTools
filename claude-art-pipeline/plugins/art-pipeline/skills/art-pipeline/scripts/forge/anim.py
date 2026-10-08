"""Poses and in-place clips for a Humanoid rig, solved on the model's own rig.

A pose is {bone: (rx, ry, rz)}: degrees about WORLD axes, about the bone's own (posed)
head, applied parents-first so a turned chest carries the arm. X tips a limb forward or
back (negative X swings a hanging arm toward -Y, the front), Y rolls it sideways, Z
turns it about the vertical. Two special keys: "_hips" = (x, y, z) offset as a fraction
of height, and "_pin_feet" = True to hold both ankles at their rest position with leg IK.

Clips are authored in place (the engine moves the agent). The walk matches a speed in
m/s: stride = speed * cycle, a planted ankle slides backward at exactly `speed`, so in the
world it stands still; the legs reach the ankle targets by two-bone IK and the hips drop
just far enough that no leg is asked to over-extend. `bake_clips` keys every bone every
frame and reports foot slide (mm) and lowest foot point.
"""

from __future__ import annotations

import math

import bpy
from mathutils import Euler, Matrix, Vector

FPS = 30

# ---- poses -----------------------------------------------------------------------

POSES: dict[str, dict] = {
    "a_pose": {},    # the bind pose
    "t_pose": {"UpperArm.L": (0.0, -65.0, 0.0), "UpperArm.R": (0.0, 65.0, 0.0)},
    "arms_up": {"UpperArm.L": (0.0, 140.0, 0.0), "UpperArm.R": (0.0, -140.0, 0.0)},
    "reach": {"UpperArm.L": (-85.0, 0.0, 0.0), "UpperArm.R": (-85.0, 0.0, 0.0),
              "Spine": (6.0, 0.0, 0.0)},
    "crouch": {"_hips": (0.0, 0.0, -0.17), "_pin_feet": True, "Spine": (-22.0, 0.0, 0.0),
               "Chest": (-10.0, 0.0, 0.0), "Head": (14.0, 0.0, 0.0),
               "UpperArm.L": (-30.0, 0.0, 0.0), "UpperArm.R": (-30.0, 0.0, 0.0)},
}


def _depth(rig, name: str) -> int:
    d, b = 0, rig.pose.bones[name]
    while b.parent:
        d, b = d + 1, b.parent
    return d


def _rotate_about_head(pb, q) -> None:
    head = pb.head.copy()
    pb.matrix = Matrix.Translation(head) @ q.to_matrix().to_4x4() @ Matrix.Translation(-head) @ pb.matrix
    bpy.context.view_layer.update()


def reset_pose(rig) -> None:
    for pb in rig.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)
    bpy.context.view_layer.update()


def apply_pose(rig, pose: dict, height: float | None = None) -> list[str]:
    """Pose the rig from a dict as described in the module docstring (no ankle IK targets)."""
    return solve_frame(rig, pose, None, height)


# ---- solving -----------------------------------------------------------------------

def _leg_ik(rig, side: str, ankle: Vector, pole=Vector((0.0, -1.0, 0.0)), pitch: float = 0.0) -> None:
    """Two-bone IK: thigh and shin reach `ankle`, knee toward `pole`, foot kept at rest
    orientation (plus `pitch` degrees, + = toe up)."""
    bones = rig.pose.bones
    up, lo, foot = bones[f"UpperLeg.{side}"], bones[f"LowerLeg.{side}"], bones[f"Foot.{side}"]
    l1 = (rig.data.bones[up.name].tail_local - rig.data.bones[up.name].head_local).length
    l2 = (rig.data.bones[lo.name].tail_local - rig.data.bones[lo.name].head_local).length
    hip = up.head.copy()
    to = ankle - hip
    d = max(1e-4, min(to.length, (l1 + l2) * 0.9999))
    axis = to.normalized()
    a = (l1 * l1 - l2 * l2 + d * d) / (2.0 * d)
    h = math.sqrt(max(0.0, l1 * l1 - a * a))
    perp = pole - axis * pole.dot(axis)
    perp = perp.normalized() if perp.length > 1e-6 else Vector((0.0, -1.0, 0.0))
    knee = hip + axis * a + perp * h
    _rotate_about_head(up, (up.tail - up.head).rotation_difference(knee - hip))
    _rotate_about_head(lo, (lo.tail - lo.head).rotation_difference(ankle - lo.head))
    # The foot takes its REST world orientation (no roll picked up from the leg), pitched
    # about world X; +X rotation tips a -Y toe DOWN, hence the minus.
    rest3 = rig.data.bones[foot.name].matrix_local.to_3x3()
    foot.matrix = Matrix.Translation(foot.head) @ (Euler((-math.radians(pitch), 0.0, 0.0)).to_matrix() @ rest3).to_4x4()
    bpy.context.view_layer.update()


def solve_frame(rig, pose: dict, ankles: dict | None, height: float | None = None,
                pitch: dict | None = None) -> list[str]:
    """Pose the whole rig: `pose` rotations, the "_hips" offset, then leg IK to `ankles`
    ({"L": Vector, "R": Vector} in armature space) or to the rest ankles when the pose
    says "_pin_feet". Returns the bones that were rotated."""
    reset_pose(rig)
    bones = rig.pose.bones
    unknown = {k for k in pose if not k.startswith("_")} - {b.name for b in bones}
    if unknown:
        raise KeyError(f"pose names bones the rig lacks: {sorted(unknown)}")
    rest_ankle = {s: rig.data.bones[f"Foot.{s}"].head_local.copy() for s in ("L", "R")}
    if pose.get("_pin_feet") and ankles is None:
        ankles = rest_ankle
    hips = Vector(pose.get("_hips", (0.0, 0.0, 0.0)))
    if "_hips" in pose:
        if height is None:
            raise ValueError("a pose with '_hips' needs the model height")
        hips = hips * height
    if "Hips" in bones:
        h = bones["Hips"]
        h.matrix = Matrix.Translation(hips) @ h.matrix
        bpy.context.view_layer.update()
    done = []
    legs = {f"{p}.{s}" for p in ("UpperLeg", "LowerLeg", "Foot") for s in ("L", "R")}
    for name in sorted((k for k in pose if not k.startswith("_")), key=lambda n: _depth(rig, n)):
        if ankles is not None and name in legs:
            continue
        rx, ry, rz = pose[name]
        q = Euler((math.radians(rx), math.radians(ry), math.radians(rz)), "XYZ").to_quaternion()
        _rotate_about_head(bones[name], q)
        done.append(name)
    if ankles is not None:
        for side in ("L", "R"):
            _leg_ik(rig, side, ankles[side], pitch=(pitch or {}).get(side, 0.0))
    return done


# ---- clips -------------------------------------------------------------------------

def _hermite(p0, p1, m0, m1, u, span):
    return ((2 * u**3 - 3 * u**2 + 1) * p0 + (u**3 - 2 * u**2 + u) * span * m0
            + (-2 * u**3 + 3 * u**2) * p1 + (u**3 - u**2) * span * m1)


class Walk:
    """In-place parametric walk matched to `speed` (m/s) for a figure of `height` metres."""

    duty = 0.60          # stance fraction of the cycle per foot
    clearance = 0.06     # extra ankle lift mid-swing, metres
    min_drop = 0.03      # hips never ride higher than this below standing, metres
    reach = 0.985        # a leg is never asked to extend beyond this share of its length
    arm_swing = 20.0     # degrees
    lean = 3.0
    sway = 0.02
    pelvis_yaw = 5.0

    def __init__(self, rig, height: float, speed: float = 1.4, step_ratio: float = 0.43):
        self.rig, self.height, self.speed = rig, height, speed
        step = step_ratio * height                      # one step; stride = two steps
        frames = max(8, round(2.0 * step / speed * FPS))
        self.frames = frames - frames % 2               # even: the right foot is half a cycle behind
        self.cycle = self.frames / FPS
        self.stride = speed * self.cycle
        self.name = "walk"
        b = rig.data.bones
        self.rest = {s: b[f"Foot.{s}"].head_local.copy() for s in "LR"}
        self.hip = {s: b[f"UpperLeg.{s}"].head_local.copy() for s in "LR"}
        self.leg = {s: (b[f"UpperLeg.{s}"].length + b[f"LowerLeg.{s}"].length) for s in "LR"}
        flen = b["Foot.L"].length          # sole: toe 1.16 and heel 0.34 foot-lengths from the ankle
        self.toe, self.heel = 1.16 * flen, 0.34 * flen

    def phase(self, side: str, t: float) -> float:
        return ((t / self.cycle) + (0.0 if side == "L" else 0.5)) % 1.0

    def planted(self, side: str, t: float) -> bool:
        return self.phase(side, t) < self.duty

    def ankle(self, side: str, t: float) -> tuple[Vector, float]:
        """Ankle target in the clip frame (armature space) and foot pitch (deg, + toe up)."""
        v, T, duty = self.speed, self.cycle, self.duty
        half = v * duty * T / 2.0
        psi = self.phase(side, t)
        rest = self.rest[side]
        if psi < duty:
            y = -half + v * psi * T
            lift, pitch = 0.0, 0.0
            s = psi / duty
            if s < 0.12:
                pitch = 14.0 * (1.0 - s / 0.12)
            elif s > 0.6:
                pitch = -24.0 * (s - 0.6) / 0.4
        else:
            u = (psi - duty) / (1.0 - duty)
            y = _hermite(half, -half, v, v, u, (1.0 - duty) * T)
            lift = self.clearance * math.sin(math.pi * u) ** 0.8
            pitch = -24.0 + 38.0 * u - 10.0 * math.sin(math.pi * u)
        # Rotating the sole about the ankle must not dig it into the floor: raise the ankle
        # until the lowest sole corner is at z = 0 (the ankle sits `rest.z` above the sole).
        th = math.radians(pitch)
        need = rest.z * math.cos(th) + (self.heel * math.sin(th) if th > 0 else -self.toe * math.sin(th))
        return Vector((rest.x, y, max(rest.z + lift, need))), pitch

    def upper(self, t: float) -> dict:
        T, duty = self.cycle, self.duty
        c = math.cos(2.0 * math.pi * t / T)
        c2 = math.cos(4.0 * math.pi * (t / T - duty / 2.0))
        r = math.cos(2.0 * math.pi * (t / T - duty / 2.0))
        yaw = -self.pelvis_yaw * c
        pose = {"Hips": (0.0, -3.0 * r, yaw), "Spine": (self.lean * 0.6, 1.8 * r, -yaw * 0.9),
                "Chest": (self.lean * 0.4 + 0.5 * c2, 1.2 * r, -yaw * 0.7),
                "Neck": (-self.lean * 0.5, 0.0, yaw * 0.3), "Head": (-self.lean * 0.4 - 2.0 * c2, 0.0, yaw * 0.3)}
        for side, sgn in (("L", 1.0), ("R", -1.0)):
            swing = sgn * self.arm_swing * c                       # + = back
            fwd = max(0.0, -swing) / self.arm_swing
            pose[f"UpperArm.{side}"] = (swing, 0.0, 0.0)
            pose[f"LowerArm.{side}"] = (-(14.0 + 12.0 * fwd), 0.0, 0.0)
        return pose

    def hips(self, t: float, drop: float) -> Vector:
        x = self.sway * math.cos(2.0 * math.pi * (t / self.cycle - self.duty / 2.0))
        return Vector((x, 0.0, -drop))

    def frame(self, t: float):
        """(pose, ankles, pitch) at time t."""
        rig = self.rig
        ankles, pitch = {}, {}
        for s in "LR":
            ankles[s], pitch[s] = self.ankle(s, t)
        pose = self.upper(t)
        # Smallest hip drop that keeps both legs within reach (at least min_drop).
        drop = self.min_drop
        for s in "LR":
            hip = self.hip[s] + Vector((self.sway, 0.0, 0.0))
            dx = math.hypot(ankles[s].x - hip.x, ankles[s].y - hip.y)
            need = ankles[s].z + math.sqrt(max(0.0, (self.reach * self.leg[s]) ** 2 - dx * dx))
            drop = max(drop, self.hip[s].z - need)
        pose["_hips"] = tuple(c / self.height for c in self.hips(t, drop))
        return pose, ankles, pitch


class Idle:
    """Standing breath: chest and head sway, hips ride a few millimetres, feet pinned."""

    def __init__(self, rig, height: float, cycle: float = 3.0):
        self.rig, self.height = rig, height
        self.frames = round(cycle * FPS)
        self.cycle = self.frames / FPS
        self.name = "idle"
        self.speed = 0.0
        self.rest = {s: rig.data.bones[f"Foot.{s}"].head_local.copy() for s in "LR"}

    def frame(self, t: float):
        w = 2.0 * math.pi * t / self.cycle
        s, s2 = math.sin(w), math.sin(w - 0.8)
        pose = {"_hips": (0.0, 0.0, -0.0015 * (1 - math.cos(w)) / 2.0 - 0.0017 * s2),
                "Spine": (-0.8 * s2, 0.0, 0.0), "Chest": (-1.4 * s, 0.0, 0.8 * math.sin(w / 2.0)),
                "Head": (0.9 * s2, 0.0, -1.2 * math.sin(w / 2.0)),
                "UpperArm.L": (0.0, -1.2 * s, 0.0), "UpperArm.R": (0.0, 1.2 * s, 0.0)}
        return pose, dict(self.rest), {}


class Hold:
    """A named pose held for two frames."""

    def __init__(self, rig, height: float, name: str):
        self.rig, self.height, self.name, self.speed = rig, height, name, 0.0
        self.frames, self.cycle = 2, 2 / FPS
        self.pose = POSES[name]
        self.rest = {s: rig.data.bones[f"Foot.{s}"].head_local.copy() for s in "LR"}

    def frame(self, t: float):
        ankles = dict(self.rest) if self.pose.get("_pin_feet") else None
        return self.pose, ankles, {}


def make_clip(rig, height: float, name: str, opts: dict):
    if name == "walk":
        return Walk(rig, height, speed=float(opts.get("speed", 1.4)))
    if name == "idle":
        return Idle(rig, height, cycle=float(opts.get("cycle", 3.0)))
    if name in POSES:
        return Hold(rig, height, name)
    raise ValueError(f"unknown clip {name!r}; clips are walk, idle or a pose: {sorted(POSES)}")


def bake_clips(rig, height: float, clips: dict) -> tuple[list, dict]:
    """Key every clip on `rig` (one Action each, frames 0..N, N == 0 for loops).
    Returns (actions, metrics) with per-clip foot slide, lowest foot point and loop info."""
    bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
    if rig.animation_data is None:
        rig.animation_data_create()
    actions, metrics = [], {}
    for name, opts in clips.items():
        clip = make_clip(rig, height, name, opts or {})
        action = bpy.data.actions.new(name)
        action.use_fake_user = True
        rig.animation_data.action = action
        previous: dict = {}
        world_y: dict = {"L": [], "R": []}      # planted-ankle world y, per stance run
        low = 1e9
        for i in range(clip.frames + 1):                      # last key == first: seamless loop
            t = i / FPS
            pose, ankles, pitch = clip.frame(t)
            solve_frame(rig, pose, ankles, height, pitch)
            for pb in rig.pose.bones:
                q = pb.rotation_quaternion.copy()
                prev = previous.get(pb.name)
                if prev is not None and prev.dot(q) < 0.0:
                    q = -q
                previous[pb.name] = q.copy()
                pb.rotation_quaternion = q
                pb.keyframe_insert("rotation_quaternion", frame=i, group=pb.name)
                if pb.name == "Hips":
                    pb.keyframe_insert("location", frame=i, group=pb.name)
            if isinstance(clip, Walk) and i < clip.frames:
                for s in "LR":
                    foot = rig.pose.bones[f"Foot.{s}"].head
                    low = min(low, foot.z - clip.rest[s].z)
                    if clip.planted(s, t) and 0.15 < clip.phase(s, t) / clip.duty < 0.55:   # flat-foot part of stance
                        world_y[s].append((i, foot.y - clip.speed * t))
        action.frame_range = (0, clip.frames)
        actions.append(action)
        m = {"frames": clip.frames, "seconds": round(clip.cycle, 3), "fps": FPS}
        if isinstance(clip, Walk):
            slide = 0.0
            for s in "LR":
                ys = [y for _i, y in world_y[s]]
                # a stance run is contiguous frames; frame 0 may wrap, so measure each run
                runs, run = [], []
                for i, y in world_y[s]:
                    if run and i != run[-1][0] + 1:
                        runs.append(run)
                        run = []
                    run.append((i, y))
                runs.append(run)
                for r in runs:
                    if len(r) > 1:
                        slide = max(slide, max(y for _i, y in r) - min(y for _i, y in r))
            m.update(speed_mps=clip.speed, stride_m=round(clip.stride, 3),
                     foot_slide_mm=round(slide * 1000.0, 1), lowest_foot_above_rest_mm=round(low * 1000.0, 1))
        metrics[name] = m
    reset_pose(rig)
    return actions, metrics
