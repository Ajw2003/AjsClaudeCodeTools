"""Example blueprints: a prop (static) and a rigged humanoid. BLUEPRINTS = {slug: builder}."""

from mathutils import Vector

from forge import Blueprint, Human, Part, arc_path, ring_of, spline


def lantern(entry):
    """A caged candle lantern, ~0.40 m with its bail handle up: base, four posts, two rings,
    candle and flame, a conical roof and an arched handle."""
    parts = [
        Part("lathe", mat="iron", segments=16,                       # base plate
             extras={"profile": [(0.0, 0.0), (0.075, 0.0), (0.075, 0.02), (0.055, 0.04), (0.0, 0.04)]}),
        Part("tube", mat="brass", segments=8, smooth=True,             # lower and upper cage rings
             extras={"path": arc_path((0, 0, 0.045), 0.055, 0, 360, 15, (1, 0, 0), (0, 1, 0)),
                     "section": (0.007, 0.007), "closed": True}),
        Part("tube", mat="brass", segments=8, smooth=True,
             extras={"path": arc_path((0, 0, 0.25), 0.055, 0, 360, 15, (1, 0, 0), (0, 1, 0)),
                     "section": (0.007, 0.007), "closed": True}),
        Part("lathe", mat="iron", segments=16,                       # roof
             extras={"profile": [(0.08, 0.25), (0.08, 0.262), (0.045, 0.29), (0.0, 0.305)]}),
        Part("tube", mat="brass", segments=8, smooth=True,             # bail handle
             extras={"path": spline([(-0.06, 0, 0.262), (-0.06, 0, 0.30), (-0.03, 0, 0.375),
                                     (0, 0, 0.392), (0.03, 0, 0.375), (0.06, 0, 0.30), (0.06, 0, 0.262)], 3),
                     "section": (0.007, 0.007)}),
        Part("cyl", loc=(0, 0, 0.087), size=(0.04, 0.04, 0.095), mat="wax", segments=12, smooth=True),
        Part("sphere", loc=(0, 0, 0.158), size=(0.034, 0.034, 0.05), mat="flame", segments=10, rings=6, smooth=True),
        Part("cone", loc=(0, 0, 0.2), size=(0.032, 0.032, 0.05), mat="flame", segments=10, smooth=True),
    ]
    parts += ring_of(4, 0.055, 0.1475, start_deg=45, kind="cyl", size=(0.014, 0.014, 0.205),
                     mat="iron", segments=8, smooth=True)
    return Blueprint(parts=parts)


def dummy(entry):
    """A crash-test dummy: yellow body, dark joints and hands, a red nose to show the front."""
    fig = Human(height=entry.height_m)
    parts = fig.body(skin="paint", feet="joint", joints="joint")
    parts.append(Part("box", loc=(0, -0.068 * fig.height, 0.915 * fig.height),
                      size=(0.02 * fig.height,) * 3, mat="mark", bone="Head", rigid=True))
    return Blueprint(parts=parts, **fig.rig())


BLUEPRINTS = {"lantern": lantern, "dummy": dummy}
