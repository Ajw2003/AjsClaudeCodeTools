<!-- plain copy of: castle.md (uploaded sample, not in this repo, so no source hash) -->

# Castle, in plain English

**What it is.** The part of the game that builds the castle each raid happens in. It builds the
whole castle from one number, called the seed. The same seed always gives the same castle, on
every player's machine.

**Why it matters.** If two machines build different castles, players see different buildings and
the game falls apart. If the castle has no way out, players get trapped inside.

**How it works.**

1. The server picks a seed and sends only that number to each player. Every machine then builds
   the castle for itself.
2. The castle is a square outer wall with corner towers and one gatehouse. Inside are about 44
   rooms in rings: the crypt in the middle, then the keep, then the outer yards.
3. Some spaces are left open as courtyards. Each one is only opened up if every room can still be
   reached.
4. Every room has a doorway on all four sides, so rooms next to each other always connect.
   Doorways that lead nowhere get bricked up.
5. The game checks that a player can walk from the crypt to the gatehouse, which is the exit. If
   not, it tries the next seed along and checks again.
6. Loot goes on furniture like tables, chests and shelves. Never on the floor, never in the
   gatehouse.
7. When the alarm goes up, the doors lock, then bar.

**Risks and safeguards.**

- **Players trapped with no way out.** Every castle is walk-tested before a raid. A failing one is
  rebuilt from the next seed.
- **Machines build different castles.** Only the seed is sent, and building uses nothing else.
  *Still open:* nothing catches it if this slips, so a mistake shows up as silent drift.
- **Rooms that don't connect.** Every room opens on all four sides, and dead-end doorways are
  bricked up. A test checks it.
- **A gap in the outer wall.** A test checks every seed gives a closed wall with one gate.
- **Too few or too many rooms.** A test keeps it between 40 and 60.
- **A piece spilling into the next square.** The art build fails if any piece is too big.
- **Old walls blocking the new castle.** The old castle is switched off before the new one is
  built.
- **Furniture blocking paths or loot.** A separate tool walks real routes on five seeds.
- **Stairs nobody can climb.** Every staircase starts facing open floor.
- **Doors reopening mid-raid.** Doors can only lock, never unlock.
- **Same seed, different castle.** Happens when room designs aren't loaded. *Still open:* only
  compare castles set up the same way.

**Left out**, see the full doc: exact sizes and settings, how wall pieces are turned to face
outward, furniture and colour rules for rooms, how loot spots come across from the art tool, and
the names of the tests.
