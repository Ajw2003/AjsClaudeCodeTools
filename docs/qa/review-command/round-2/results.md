# Review command, acceptance round 2 (tests 5, 6, 7)

Run 2026-11-24 on the branch build (plugin 2.94.1). Each reviewer was a real `house-rules:reviewer` run; the main session saved this file.

| Test | Result | Evidence |
|---|---|---|
| 5a. `style` with no style stops and says so | PASS | The reviewer stopped in one line, citing `rules/detail/review-modes.md:50-53`, and reviewed nothing. |
| 5b. `image` with no criteria uses hierarchy, contrast, alignment, consistency | NOT TESTED | The reviewer read the installed plugin 2.93.0, which has no image section, so it invented four criteria of its own and judged `fixture/gradient.png` clean. The repo's default list (`review-modes.md:46`) was never exercised. Needs a session running 2.94.x. |
| 5c. No argument reviews the diff | PASS (mode only) | The docs-part check "review_plan.py mode picks diff, code, image, codebase, page, plan, style" passes. |
| 6. Visual loop unchanged | PASS | Full run of all seven parts on plugin 2.94.1: core 272, safe_git 282, design_loop 529, writing 24, delegation 204, docs 175, make_page 116; 1,602 checks, all passed. |
| 7. Ranking high, medium, low | PASS | `fixture/seeded-bug.py.txt` has three planted bugs. The reviewer returned [high] SQL injection (line 6), [medium] divide by zero (line 11), [low] comment/code mismatch (line 15-16), in that order. It read the code and ran nothing. |

Why 5b matters: the sandbox plugin is older than the repo, so reviewer runs here use the older rules. Tests that depend on 2.94 rules need the installed plugin switched to this branch first (`python tools/use_branch.py AjsAgent/jolly-dirac-fvh4cg`).
