# Handoff: acceptance round 2 on aj's PC

## What the work is for
Finish the design review loop (parent issue #592) by recording acceptance round 2 from real output on aj's Windows PC, stamping it, and building the QA page.

## Where it stands
aj's PC run failed all nine criteria because the `design_loop` part of `verify.py` crashed on Windows. Two causes are fixed on branch `AjsAgent/acceptance-round-2-windows-fixes` (cut from `pc-acceptance-round-2`): the close-facts tests faked `gh` with a shell script (now a Python stand-in in `checks/design_loop.py`), and `page_criteria._stamp_hash` now hashes CRLF and LF alike. A full `verify.py` run after the first fix left nine Windows-only failures outside this feature (guard cwd, `rm -rf /tmp`, `waitfor`, two page checks, one node check). A rerun of `docs/qa/design-review-loop/run_acceptance.py` was started in the background and writes `round-2/`.

## The next step
Read `docs/qa/design-review-loop/round-2/round-2-draft.md`. If STATUS is pass, record `round-2.md` with `scripts/ledger.py`, run `scripts/acceptance.py stamp docs/qa/design-review-loop`, build the QA page with the page builder and send it. If a criterion fails, read its `cN-M.txt` and fix the cause. The untracked folder `round-2-pc-first-run/` has a draft saying all PASS that contradicts its own output files; do not trust it.

## What is unverified
The rerun result is unread. The full suite was not rerun after the stamp fix. The nine remaining Windows failures were not investigated. Nothing is stamped.

## The issue numbers
Parent #592; pull request #604 is open (`Refs #592`).
