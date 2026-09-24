<!-- plain copy of: castle.md (uploaded sample, not in this repo, so no source hash) -->

# Castle, in plain English

**What it is.** Builds the castle each raid happens in, from one number called the seed. The same
seed gives the same castle on every player's machine.

**Why it matters.** If machines build different castles, the game breaks. If the castle has no way
out, players get trapped.

**How it works.**

1. The server picks a seed and sends only that number. Each machine builds the castle itself.
2. An outer wall with one gatehouse surrounds about 44 rooms in rings: crypt in the middle, then
   the keep, then the outer yards. A few spaces are left open as courtyards.
3. Rooms have doorways on every side, so neighbours always connect.
4. Before a raid, the game checks you can walk from the crypt out through the gatehouse.
5. Loot goes on furniture like tables, chests and shelves.
6. When the alarm goes up, the doors lock, then bar.

**Risks and safeguards.**

- **No way out.** Every castle is walk-tested. A failing one is rebuilt from the next seed.
- **Machines build different castles.** Only the seed is sent, and building uses nothing else.
  *Still open:* nothing catches a slip, so it shows up as silent drift.
- **Dead-end doorways.** Bricked up automatically. A test checks it.
- **A gap in the outer wall.** A test checks every seed.
- **Too few or too many rooms.** A test keeps it between 40 and 60.
- **A piece spilling into the next square.** The art build fails if any piece is too big.
- **Old walls blocking the new castle.** The old one is switched off first.
- **Furniture blocking paths or loot.** A separate tool walks real routes on five seeds.
- **Stairs nobody can climb.** Every staircase starts facing open floor.
- **Doors reopening mid-raid.** Doors can only lock, never unlock.
- **Same seed, different castle.** Happens when room designs aren't loaded. *Still open:* only
  compare castles set up the same way.

**Left out**, see the full doc: sizes and settings, how wall pieces are turned, room furniture and
colour rules, how loot spots are imported, and test names.
