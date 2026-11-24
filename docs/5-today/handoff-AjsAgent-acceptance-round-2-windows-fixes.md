# Handoff: acceptance round 2 passed, waiting on QA

## What the work is for
Finish the design review loop (parent issue #592) by recording acceptance round 2 from real output on aj's Windows PC, stamping it, and handing it over for QA.

## Where it stands
aj failed QA: fix every pre-existing failure before the pull request to main. All are fixed on this branch: `waitfor.py` (runs checks under `sh`, `taskkill` on Windows), the guard (`core.py` path patterns, `safe_git.py` `posixpath` and `/tmp` mapping), `_extract_file_path` (JSON-unescaped), the fake `node` and `claude` stand-ins, and `tools/force_update.py` (runs the path `which` finds). A full `verify.py` passed 1574 of 1581 (7 skipped), `tools/verify_tools.py` 55 of 55, `docref.py check` OK, `docs_drift.py` 0. The source changed after round 2, so the acceptance stamp is stale; `run_acceptance.py` was started again in the background and writes `docs/qa/design-review-loop/round-2/`.

## The next step
When the rerun ends, read `round-2/round-2-draft.md`. If STATUS is pass: copy it over `round-2.md`, run `scripts/acceptance.py stamp docs/qa/design-review-loop`, update the QA page content (`docs/plans/2026-11-24-design-review-loop-qa.page.json`: the unverified lines now say the suite is clean), rebuild it with `--reviewed clean --rounds 1`, commit, push, send the page. If a criterion fails, read its `cN-M.txt`.

## What is unverified
The rerun result. No plugin version bump was made for the hook fixes. Check 172 (prompttimer concurrency) failed once in one full run and passed in the next two; it may be timing-sensitive.

## The issue numbers
Parent #592; pull request #604 (`Refs #592`).
