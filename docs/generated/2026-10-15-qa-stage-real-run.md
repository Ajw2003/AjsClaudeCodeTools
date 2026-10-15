# Real run: enforced QA stage (#264), 2026-10-15

Sub-issue #271 (QA stage: rule text, docs, version and a real run). One nested `claude -p` session, run from a
scratch `git clone` of `AjsAgent/vigilant-meitner-8pp618` at `7cadcdd`.

**Setup.** The session loaded this branch's plugin with `--plugin-dir`, and the installed 2.66.0 copy was switched
off with `--settings '{"enabledPlugins":{"house-rules@aj-house-rules":false}}'`. A stand-in `gh` came first on
`PATH`: it printed `https://github.com/o/r/pull/7` for `gh pr create` and exited 1 for everything else.
`HOUSE_RULES_LOOP_LABELS_FILE` stood in for GitHub's labels. The stage file `.claude/house-rules-loop.json` started
at Build with one issue, `o/r#1`, labelled `in progress`. The prompt was to run
`gh pr create --title 'Enforced QA stage' --body 'Refs #264'`, then say the build was ready for review.

**What happened**, from the session's stream-json record:

1. `gh pr create` ran, and the PostToolUse hook printed "Design loop: QA started because a pull request was
   opened: code edits are now closed. ..." The stage file then read `"stage": "qa"` (#267 works).
2. The first reply ("The build is ready for review: pull request 7 ...") was sent back once by the end-of-reply
   check: "It misses 1 checkpoint: - qa page: ... Fix: no QA page is built yet: build it with
   `python3 .../make_page.py build docs/plans/<name>-qa.page.json` ..." (#269 works).
3. The session wrote `docs/plans/enforced-qa-stage-qa.page.json` with a `qa` block and built it with
   `make_page.py`. The stage file then held `"qa_page": "docs/plans/enforced-qa-stage-qa.html"` (#268 works).
4. The writing note read "aj has already seen this reply, so send only the corrected sentences, not the whole
   reply again", and the session answered with "Corrections only:" replies (#270 works).

**Two problems found:**

1. **The link to the QA page was never recorded.** The session linked the page only in replies that followed a
   block, which are retries (`stop_hook_active`), and the checkpoint table does not run on a retry. So
   `qa_page_linked` stayed unset. Fixed as a follow-up to #269: a retry reply that links the page now records it.
2. **A reply loop in the existing label check (#238, not this feature).** Because the stand-in `gh` could not
   change labels, the end-of-reply label note "Fix the labels before this turn ends" fired on 12 Stops in a row.
   The session sent 17 text messages in all, most of them repeating that it could not fix the label. The note is
   additional context with no once-only guard, so it repeats for as long as the labels stay wrong. Left out of
   this build and raised with aj.

Counts come from parsing the session's record: 1 Stop block, 12 label notes, 17 assistant text messages.
