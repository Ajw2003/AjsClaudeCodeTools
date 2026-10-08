"""What a builder returns: the parts, and (for a rigged asset) the rig."""

from __future__ import annotations

from dataclasses import dataclass, field

from .kit import Part, families_used
from .spec import Entry


@dataclass
class Blueprint:
    parts: list[Part]
    # Rig: bone dicts {name, head, tail, parent, mirror?}. Setting `bones` selects the
    # rigged path. `**figure.rig()` fills bones, forward_bones and pose for you.
    bones: list[dict] | None = None
    # Bones whose head->tail must point toward -Y (feet): how the validator proves the front.
    forward_bones: list[str] = field(default_factory=list)
    tri_budget: int | None = None      # None -> the spec's budget
    grounded: bool = True              # lowest point must sit on z = 0
    # Set by build.py:
    slug: str = ""
    entry: Entry | None = None

    @property
    def rigged(self) -> bool:
        return self.bones is not None

    @property
    def budget(self) -> int:
        return self.tri_budget if self.tri_budget is not None else self.entry.tri_budget

    def ordered_families(self) -> list[str]:
        """Families the parts use, in spec order; unknown ones are an error."""
        used = set(families_used(self.parts))
        unknown = used - set(self.entry.families)
        if unknown:
            raise ValueError(f"{self.slug}: parts use families not in the spec: {sorted(unknown)}; "
                             f"spec families are {sorted(self.entry.families)}")
        return [k for k in self.entry.families if k in used]
