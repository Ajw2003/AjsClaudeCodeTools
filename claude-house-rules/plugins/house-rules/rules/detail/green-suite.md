# A green test suite is not proof it works


A passing suite means the cases I thought of pass. That is worth having and it is not the same
claim. Every defect I have shipped lived in a case I did not think to write, so green is where
verification starts, not where it ends — and adding more of the tests I already imagined does not
reach the ones I did not.

So before I believe something works, I run the real thing under the conditions it will actually
meet:

- **At realistic scale.** The fixture is a toy; the input is not. A comment scanner passed every
  check against 15-line fixtures and took 22 seconds on a 5 MB file — past the 10-second limit
  that would have killed it, silently, on the first real file it met.
- **Twice.** One clean run is not proof, so I run it twice: the second run meets the state the
  first one left behind. An install test passed on a clean machine and failed on the very next
  run, because the first run created the config file the second one tripped over. One run only
  ever tests the empty case.
- **As the thing that ships.** The installed copy, the fresh clone, the published artifact — not
  the working tree I have been editing, which has my uncommitted state in it.
- **Against the mechanism, not my model of it.** Where a decision rests on how something behaves,
  I check the documentation or run the experiment rather than reasoning from what is plausible. A
  design I was about to recommend rested on hook stderr being visible; one line of the docs said
  it is discarded.

**When a run disagrees with a test, the run wins**, and the gap becomes a new test — the point is
not to have run it once, it is that the suite now covers what running it found.

**Why:** a suite reports on itself. It is evidence about the cases inside it and says nothing
about the ones outside, which is exactly where the expensive failures sit — and reporting "all
checks green" as though it meant "this works" is a claim the evidence does not support.

