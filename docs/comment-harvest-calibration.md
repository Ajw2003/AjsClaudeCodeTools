# Comment-harvest calibration

What the `harvest` hook's thresholds actually catch, measured against this repository's own
source. `verify.py` proves the handler behaves as written; this is the separate question of
whether the *numbers* in it are the right numbers, which no unit test can answer.

Re-run it any time — the script is nine lines and reads the installed handler directly. Pass
`full_file=True` because this reads a whole file off disk, the same as a `Write`'s `content` —
never omit it for an `Edit`'s `new_string` fragment, whose own line 1 is not the file's (see
"The two exemptions" below):

```python
import json, sys
sys.path.insert(0, "claude-house-rules/plugins/house-rules/scripts")
import hook
src = open("claude-house-rules/plugins/house-rules/scripts/hook.py", encoding="utf-8").read()
blocks, misses, _ = hook._harvest_blocks(src, 3, 150, 1e18, False, full_file=True)
for start, end, n_lines, n_chars in blocks:
    print("%4d-%-4d %2dL/%4dc  %s" % (start, end, n_lines, n_chars, src.split("\n")[start-1].strip()[:70]))
```

Or run it over an entire project rather than one file at a time:
`python "$CLAUDE_PLUGIN_ROOT/scripts/harvest_scan.py" <path>` — the hook only ever sees text
written in the current turn, so this manual, project-wide sweep is the only way to ask "does
this codebase already have any" rather than "did this edit just add one."

## The measurement

Original pass taken 2026-09-09, against the tree at the commit that added the handler, at the
then-default of 5 lines / 300 chars. Re-measured 2026-09-20 against the current tree, with the
`full_file`-aware detector (see "The Edit/Write bug" below) and the current default of 3 lines /
150 chars:

| File | Blocks at **3 / 150** (current default) | Blocks at 5 / 300 (previous default) | Blocks at 10 / 600 |
|---|---|---|---|
| `scripts/hook.py` | 64 | 29 | 5 |
| `scripts/verify.py` | 42 | 25 | 2 |
| `tools/install.py` | 10 | 6 | 1 |
| `tools/measure_footprint.py` | 7 | 5 | 0 |

## What that says

**10 / 600 was too high to be useful.** At the original 2026-09-09 measurement it found two
blocks in the entire repository and nothing at all in `verify.py`, `install.py` or
`measure_footprint.py` — files that are visibly full of long-form rationale. A detector that
fires twice across four files of essay-dense Python is not calibrated conservatively; it is
switched off with extra steps. It still finds only a handful today.

**3 / 150 was chosen by direct request, not by re-running this measurement's original
reasoning.** The previous default (5 / 300) was already missing shorter blocks that are still
essays by inspection — a six-line, ~350-character rationale reads the same whether it is 250 or
350 characters — and it was specifically missing C# XML doc-comment blocks (`/// <summary>`)
short enough to clear a human's "this is prose" bar but not the old character floor. The lower
default roughly doubles what qualifies in this repo (29 → 64 in `hook.py` alone), which is the
same trade the original 5/300 vs. 10/600 comparison already named: **more of this repo's own
comments now qualify, and that is the tool working, not a miscalibration.**

**5 / 300 found the blocks the repo had already independently identified**, at the time it was
the default. Every one of these was named in [`architecture-backlog.md`](architecture-backlog.md)
§6 as a comment that should shrink to a pointer:

| Site (as of 2026-09-09) | What it is |
|---|---|
| `hook.py:645-649` | why `_ARTIFACT_EXT_RE` widened past `md\|txt` |
| `hook.py:430-434` | the `scope` long-form cost argument |
| `hook.py:1307-1312` | why `main()`'s last-resort net exists |
| `verify.py:1260-1263` | the `force-for-plugin` reversal, argued at three sites |
| `verify.py:461-464` | why the drift checks must run in both directions |

The backlog reached that list by reading; the detector reaches it by measuring. They agree,
which is the evidence that the threshold is set somewhere real. Line numbers have since moved as
the files grew — the sites are historical, not a live index.

## The Edit/Write bug (fixed 2026-09-20)

The file-header exemption below only makes sense against a whole file, where line 1 really is
the file's first line. It was being applied unconditionally, including to an `Edit`'s
`new_string` — a replacement fragment whose own line 1 is wherever the edit happens to start.
A comment block placed at the top of an edited fragment was silently exempted as a "file
header" it was never anywhere near. See `docs/Decisions.md`, "Fix the harvest handler treating
an Edit fragment's line 1 as the file's header", for the fix and the trace-wording bug that
shipped alongside it (the trace used to say "none met the threshold" even when a run met it and
was excluded for a different reason).

## The two exemptions, and why they are not special-pleading

Both were added because the measurement surfaced them as false positives, not to protect
anything:

- **File headers.** A run starting at line 1 — or at line 2 under a shebang or encoding line —
  is a module docstring. That is documentation already in the right place;
  `rules/standards/coding-philosophy.md` asks for it. The rule targets essays buried in the
  *body* of a file. Only applies when the text really is the whole file (`full_file=True`): a
  `Write`'s `content`, or a standalone scan of a file on disk — never an `Edit`'s `new_string`
  fragment, whose own line 1 is not the file's. See "The Edit/Write bug" above.
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

`tools/measure_footprint.py` section 4 now prices this, alongside every other per-tool-call
handler, so these figures no longer have to be taken by hand. It reports the reminder and the
trace **separately** — collapsing them into one number is exactly how the harvest trace went
unmeasured through 2.13.0.
