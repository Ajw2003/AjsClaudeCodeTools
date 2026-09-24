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
7. When the alarm goes up, the doors lock, then bar. They never unlock again.

**What can go wrong.**

- Any randomness that doesn't come from the seed, such as the clock, makes machines build
  different castles. Nothing warns you. Players just quietly see different things.
- The old castle must be switched off before the new one is built. Otherwise the game's walking
  map sees both, and old walls block new doorways.
- The same seed builds a different castle depending on whether the room designs are loaded. Only
  compare two castles set up the same way.
- The walk check can't see furniture, so a separate tool tests real walking routes.
- Stairs need open floor at the bottom. A staircase that starts against a wall can't be climbed.

**Left out**, see the full doc: exact sizes and settings, how wall pieces are turned to face
outward, furniture and colour rules for rooms, how loot spots come across from the art tool, and
the names of the tests that hold each promise.
