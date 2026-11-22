# Wait clocks, visual checks, page sending and working pictures

**Owns:** four workflow fixes that stop the agent waiting without a clock, looking at visual work
without really looking, finishing a page without sending it, and shipping pages whose pictures
break. Status: **built on `ajsagent/eloquent-mayer-0ayp82` (plugin 2.88.0), waiting on aj's QA.** Design approved 2026-11-22 as "Design approved: wait
clocks, visual checks, page sending and pictures 1A 2A 3B 4B 5A 6A" (`docs/6-decisions/Decisions.md`).
Page: `docs/plans/2026-11-22-wait-and-visual-checks.html`. Parent issue #555; steps #556 to #568.
Line numbers below are as of 2026-11-22, after the build.

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

## How it works, as built

All code is under `claude-house-rules/plugins/house-rules/`. Where the build differs from the design
above, it says so.

**Wait clocks.** `rules/waits.json` holds the numbers; `load_waits()` (`scripts/house_rules/waits.py:44`)
reads it, lets `HOUSE_RULES_WAIT_*` override each, and reports a missing file or a bad value in words
before using the built-in default. `scripts/waitfor.py` (`main`, line 48) runs a check command at the
first-check and interval times, prints a line per check, and exits 0 done, 1 failed, 2 stalled
(reusing `stallcheck.check`), 3 timed out, 4 bad usage. A check command is cut off at the time left
before the deadline, so a hung check cannot overrun it. `_wait_check` (`scripts/house_rules/safe_git.py:685`)
still refuses a foreground sleep loop or a `timeout` over the foreground limit, and now also refuses a
background command with no `timeout` or one over 1,200,000 ms, naming the fix. `handover_unchecked_waits`
(`safe_git.py:2233`) lists, once and never blocking, a background launch nobody checked afterwards; a
check is a later Bash/PowerShell command that runs `waitfor.py` or `stallcheck.py`, or a read of the
task's output file or of a file the launch command itself wrote to. A later helper prompt that merely
mentions `waitfor.py` does not count (found on this session's real transcript). The rule text sits in
"Nothing fails silently" in `rules/house-rules.md` (not a section of its own: the injected rules were
over the per-hook size limit), with the detail in `rules/detail/waits.md`. A switch group `waits`
(`HOUSE_RULES_WAITS`) turns the obstructing parts off.

**Working pictures.** `embed_pictures` (`scripts/make_page.py:163`) stores each local picture as a
`data:` address (svg, png, jpg, jpeg, gif, webp; at most `MAX_PIC` = 1,000,000 bytes, line 158), refuses a
web-linked picture, and writes no `-pics` folder. `static_broken_pictures` (line 650) scans a page for any
picture source that is not built in, and `visual_check` (line 666) also opens a copy of the page alone in
an empty folder. The static scan exists because builder pages only create their `<img>` tags when a row is
tapped: the lone-copy check alone reported "0 broken" for a page whose pictures were in a folder, found
by running it on a real old page.

**Page sending.** `_pages_unsent` and `_check_send` (`scripts/house_rules/design_loop.py:2488`, `2516`)
block the end of a turn once when a page under `docs/` was written or rebuilt this turn (a Write or Edit,
or a `make_page.py build` that prints `wrote <page>`) with no `SendUserFile` or Artifact publish after
its last change; where no send tool exists, a link in the reply counts. `make_page.py` ends a build with
`SEND THIS PAGE NOW`, and a note follows a page write. `event_sendcheck` (line 2748, a `PreToolUse` hook on
`SendUserFile`, `sendcheck`) opens the page alone before it is sent and never blocks. **Differs from the
design:** the design said an old page with folder pictures would be rebuilt from its `.page.json`. That is
wrong for a QA-mode page, whose builder asks git for the changed files, so a rebuild regenerates its
content, and it fails outside a git repo. `_embed_in_place` (line 2707) instead embeds each folder picture
into the existing page and changes nothing else; it also works for a page with no source file. Proven on
a copy of the real `docs/plans/2026-10-19-restructure-step-1-qa.html`: 2 broken pictures, then 0, the page
still 791 lines, embedded pictures 2 to 4.

**Visual loop.** `scripts/visualcheck.py` (`main`, line 355) has `doctor` (never installs anything; prints
the install command for what is missing), `shots` (phone 375 and desktop 1280, light and dark, with a
per-image `report.json` of console errors, failed requests, sideways scroll at 375 px and blank images),
`video` and `frames` (a timestamped `sheet.png`, motion measures: frozen runs, jumps, static). It uses
Python Playwright and Pillow, pointed at an installed Chromium; `video` needs Playwright's own ffmpeg
(`python3 -m playwright install ffmpeg`). `scripts/ledger.py` (`cmd_check` 126, `cmd_status` 142, `cmd_new_round`
164) checks `docs/qa/<feature>/criteria.md` and `round-N.md`; `rules/visual.json` sets the 4-round cap;
`skills/visual-loop/SKILL.md` runs the loop. **Differs from the design:** the reviewer helper has no write
tool, so it returns its verdict lines and the caller saves them as `round-N.md`. `_visual_missing`
(`scripts/house_rules/writing.py:228`) replaces the keyword match: after its last visual write a turn must
run a `visualcheck.py` capture, then `ledger.py check` or `status`, and read an image, else a non-blocking
note names what is missing. `.svg`, `.anim` and `.controller` joined the visual list; `.png`/`.jpg` did not,
because they are what captures produce.

**Proven live.** `docs/qa/loop-proof/`: a planted-defect page (a 600 px banner and a console error). Round 1
failed all three written criteria, a builder fixed the causes, round 2 passed with a fresh reviewer;
`ledger.py status` said `NEXT: done`, and nobody asked aj anything.

**Build method.** Worktrees start from `main`, which lacks the finished steps, and the guard refuses a merge
from inside one, so most builders worked directly in the main checkout, each told to commit only its own
paths. Two builders running tests at once made each other's runs fail (once 59 false failures in one part);
run alone, the parts pass.

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

- **Not run on aj's machine.** The cloud container could not attach to it (his computer lists none of its folders to cloud sessions), so every command handed to him is labelled untested there; his OS and shell are unconfirmed.
- **Live on Linux, 2026-11-22** (`docs/plans/2026-11-22-wait-and-visual-checks-live-tests/live-qa-results.txt`): two real headless sessions with the branch build loaded exercised the send reminder, the send hook (the real `SendUserFile` payload names its file field `files`: confirmed) and the in-place repair of a real old page. The block-once-if-never-sent path has only run on recorded transcripts and made-up payloads, because the test agent always sent its pages.
- **Found live and fixed after aj's QA failed:** the end-of-turn visual check fired after ordinary pages (1 and 2 times in the two live runs) asking for a capture, a ledger check and an image read. `_is_visual` (`scripts/house_rules/writing.py`, near line 228) now exempts an `.html` or `.htm` file whose first 4096 characters contain `house-rules make_page` (a built page) or `house-rules-page` (a hand-written handover page that passed the page hook): those already go through the page pipeline. A plain HTML file with neither marker, such as `docs/qa/loop-proof/fixture/index.html`, is still checked, and an unreadable or missing file is not exempted. Replaying the two real live transcripts: step 4, 1 firing before and 0 after; step 5, 1 before and 0 after (it saw 1, not the 2 seen live; the replay does not model a Stop-hook retry).
- **The injected rules are at 9,694 of 9,700 characters.** The next rule added has to make room first.
- **The visual gate's false-alarm rate on other kinds of visual change is unmeasured.** On page-writing turns it was 2 of 2 before the fix and 0 after, on replay.
- **Video and frames** were proven for one viewport and theme (phone, light); Unity and game capture is only written down.
- A hook cannot stop a tool that has already hung; only the launch can carry a limit.
- A reviewer helper checks the images with fresh eyes but is still a model; it can miss things, so
  every pass must cite what the image shows.
- Contact sheets sample frames; they do not show every frame.
- aj's own machine, Unity and game capture, and the side panel's rendering of pages are untested.
- The false-alarm rate of a widened visual-file list is unmeasured until step #567 measures it.
