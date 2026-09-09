# Comment-harvest calibration

What the `harvest` hook's thresholds actually catch, measured against this repository's own
source. `verify.py` proves the handler behaves as written; this is the separate question of
whether the *numbers* in it are the right numbers, which no unit test can answer.

Re-run it any time — the script is nine lines and reads the installed handler directly:

```python
import json, sys
sys.path.insert(0, "claude-house-rules/plugins/house-rules/scripts")
import hook
src = open("claude-house-rules/plugins/house-rules/scripts/hook.py", encoding="utf-8").read()
blocks, misses, _ = hook._harvest_blocks(src, 5, 300, 1e18, False)
for start, end, n_lines, n_chars in blocks:
    print("%4d-%-4d %2dL/%4dc  %s" % (start, end, n_lines, n_chars, src.split("\n")[start-1].strip()[:70]))
```

## The measurement

Taken 2026-09-09, against the tree at the commit that added the handler.

| File | Blocks at **5 lines / 300 chars** (default) | Blocks at 10 / 600 |
|---|---|---|
| `scripts/hook.py` | 10 | 2 |
| `scripts/verify.py` | 9 | 0 |
| `tools/install.py` | 1 | 0 |
| `tools/measure_footprint.py` | 3 | 0 |

## What that says

**10 / 600 was too high to be useful.** It found two blocks in the entire repository and
nothing at all in `verify.py`, `install.py` or `measure_footprint.py` — files that are visibly
full of long-form rationale. A detector that fires twice across four files of essay-dense
Python is not calibrated conservatively; it is switched off with extra steps.

**5 / 300 finds the blocks the repo had already independently identified.** Every one of these
is named in [`architecture-backlog.md`](architecture-backlog.md) §6 as a comment that should
shrink to a pointer, and each is found only at the lower threshold:

| Site | What it is |
|---|---|
| `hook.py:645-649` | why `_ARTIFACT_EXT_RE` widened past `md\|txt` |
| `hook.py:430-434` | the `scope` long-form cost argument |
| `hook.py:1307-1312` | why `main()`'s last-resort net exists |
| `verify.py:1260-1263` | the `force-for-plugin` reversal, argued at three sites |
| `verify.py:461-464` | why the drift checks must run in both directions |

The backlog reached that list by reading; the detector reaches it by measuring. They agree,
which is the evidence that the threshold is set somewhere real.

## The two exemptions, and why they are not special-pleading

Both were added because the measurement surfaced them as false positives, not to protect
anything:

- **File headers.** A run starting at line 1 — or at line 2 under a shebang or encoding line —
  is a module docstring. That is documentation already in the right place;
  `rules/standards/coding-philosophy.md` asks for it. The rule targets essays buried in the
  *body* of a file.
- **Section dividers.** A `# -----------------------` banner measured 432 characters and pushed
  a five-line run over the character threshold on punctuation alone. Divider lines still belong
  to their run — they do not break it — but they contribute no characters.

## What this measurement cannot show

It is four Python files in one repository, all written in one voice. It says nothing about how
the thresholds behave on C#, TypeScript or shell, on a codebase with a different comment
culture, or on generated code. The extension gate and prose tests are exercised by `verify.py`
against synthetic fixtures in those languages; their *thresholds* have only been calibrated
here. If the defaults turn out wrong elsewhere, the levers are
`HOUSE_RULES_HARVEST_MIN_LINES` and `HOUSE_RULES_HARVEST_MIN_CHARS` — and a second table in
this document, rather than a quiet change to the constants.

## What the trace costs

The trace is on by default and fires on every source-file write, so its size is the number that
decides whether that default survives. Measured 2026-09-09:

| Outcome | Trace | Reminder |
|---|---|---|
| Source file, nothing qualifies | 107 chars (~26 tokens) | — |
| Source file, one block found | 30 chars (~7 tokens) | 1,195 chars (~298 tokens) |
| Not a source file | nothing emitted | — |

~26 tokens is well under `scope`'s short form (~65 tokens per *prompt*), and it is paid only on
source writes rather than on every turn. The reminder is in line with `artifact`, `runnable` and
`delegate`.

`tools/measure_footprint.py` does not cover this: it measures `scope` and the two `SessionStart`
handlers, and has no `PostToolUse` coverage at all. The figures above were taken by running the
handler directly. Extending the tool to cover `PostToolUse` is worth doing and has not been done.
