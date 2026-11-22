# Wait clocks, visual checks, page sending and working pictures

**Owns:** four workflow fixes that stop the agent waiting without a clock, looking at visual work
without really looking, finishing a page without sending it, and shipping pages whose pictures
break. Status: **planned, nothing built.** Design approved 2026-11-22 as "Design approved: wait
clocks, visual checks, page sending and pictures 1A 2A 3B 4B 5A 6A" (`docs/6-decisions/Decisions.md`).
Page: `docs/plans/2026-11-22-wait-and-visual-checks.html`. Parent issue #555; steps #556 to #568.
Line numbers below are as of 2026-11-22.

## What exists today, and the gap in each

| Fix | Exists today | The gap |
|---|---|---|
| Wait clocks | `_wait_check` in `scripts/house_rules/safe_git.py:678` refuses a foreground sleep loop, or a `timeout` over `WAIT_LIMIT_SECONDS = 60` (line 669). `scripts/stallcheck.py` reports a stalled subagent transcript or output file. | A background command, a helper agent or a scheduled wake-up has no limit. No rule says when to check. `stallcheck.py` only runs if remembered. The 60 is written into code. |
| Visual checks | `rules/detail/visual-check.md` asks for before and after screenshots. `handover_visual_check` in `scripts/house_rules/writing.py:364` reminds a turn that wrote a visual file. | `_looked_at_result` (`writing.py:227`) counts any command containing "screenshot", "playwright", "capture", "browser" or "computer" as a look. No video, no frame sheet, no phone-and-desktop flow, no critique loop. |
| Page sending | `_reply_links_page` (`scripts/house_rules/core.py:3261`) and `_check_page` (`scripts/house_rules/design_loop.py:2461`) pass a reply that mentions a page's path. | Nothing checks that the page was sent, or sent again after a change. Seen in this repo's session record: the page was linked by path and aj had to type "show me the page". |
| Working pictures | `copy_pictures` (`scripts/make_page.py:156`) copies each picture to `<page>-pics/` and links it by relative path. | A page delivered on its own has no folder beside it. Measured 2026-11-22: a copy of the proposal page opened alone had 5 of 5 pictures broken, against 0 of 5 in the repo. Six other pages in `docs/plans/` use the same folder. |

## The design that was approved

**Wait clocks (choices 1A, 2A).** Every wait states what it waits for, how to check it, a
done-test and a deadline. First check at 60 seconds, then every 60 seconds. `rules/waits.json`
holds the numbers: stalled after 3 quiet checks, and a deadline per kind (command or test 10
minutes, helper agent 15, build 20, CI run 15); `HOUSE_RULES_WAIT_*` overrides them. `scripts/waitfor.py`
polls, prints a line per check, and exits as done, failed, stalled or timed out. At a deadline the
agent stops waiting, says what is still unknown, and carries on. The guard refuses a background
launch with no timeout, or over its deadline, and names the fix. A hook cannot interrupt a tool
that is already hung, so the launch is the only point where a limit holds. A background task or
helper agent started and never checked is reported once at turn end, not blocked.

**Visual loop (choices 3B, 4B).** Criteria first: `docs/qa/<feature>/criteria.md`, each criterion
naming its capture. `scripts/visualcheck.py` uses Python Playwright and Pillow (plus ffmpeg for
frames). `doctor` says what is missing and prints install commands; it never installs. `shots`
writes phone (375 px) and desktop (1280 px) screenshots in light and dark, plus `report.json`
(console errors, failed requests, sideways scroll at 375 px, blank images). `video` and `frames`
record a feature and tile frames into a timestamped sheet, with motion measured between frames.
A `visual-loop` skill runs the rounds: capture, a separate reviewer helper critiques the images,
the builder fixes, `docs/qa/<feature>/round-N.md` records each criterion as pass or fail citing the
image. It stops when all pass or after 4 rounds and writes what still fails; it never asks aj
mid-loop. The end-of-turn check requires a `report.json` written this turn and a ledger.

**Page sending (choice 5A).** A page made, rebuilt or edited in a turn is sent with the file-send
tool as the last action, and sent again after any later change; a published artifact link counts.
`make_page.py` ends a build with a line saying to send it. A new end-of-turn check reads the turn
and blocks once, naming the page, if no send or publish followed its last change. Where no
file-send tool exists, a link in the reply counts.

**Working pictures (choice 6A).** The builder stores each picture inside the page file; a picture
over 1 MB is refused; web-linked pictures are refused. After each build a copy of the page is opened
alone and a broken picture refuses the page. The send step runs the same check and, if a picture is
broken, rebuilds the page from its `.page.json` source; a hand-written page with no source is
reported, not guessed at. The six old folder-picture pages are repaired when next sent.

## Build order and why

Page sending and pictures first (smallest, and the most repeated complaints), then the wait clock
(the visual loop runs under its deadlines), then the visual loop, then docs and tests. Step issues,
with what each depends on, are on #555.

## Checked before approval

- **Python Playwright and Pillow work in the cloud container** (2026-11-22): installed into a scratch
  virtual environment, launched with `executable_path` set to the browser already installed under
  `/opt/pw-browsers`, and wrote a 375 by 812 screenshot. A different Playwright version needs the
  same trick or its own browser download.
- **Choice 3B differs from the suggestion** (Node Playwright, already installed). 3B was chosen by aj;
  it adds a pip install on any machine that lacks it, which `doctor` reports and never runs.

## What this design cannot show

- A hook cannot stop a tool that has already hung; only the launch can carry a limit.
- A reviewer helper checks the images with fresh eyes but is still a model; it can miss things, so
  every pass must cite what the image shows.
- Contact sheets sample frames; they do not show every frame.
- aj's own machine, Unity and game capture, and the side panel's rendering of pages are untested.
- The false-alarm rate of a widened visual-file list is unmeasured until step #567 measures it.
