# Review command, acceptance round 2 (tests 5, 6, 7)

Run 2026-11-24 on the branch build (plugin 2.94.1). Each reviewer was a real `house-rules:reviewer` run; the main session saved this file.

| Test | Result | Evidence |
|---|---|---|
| 5a. `style` with no style stops and says so | PASS | The reviewer stopped in one line, citing `rules/detail/review-modes.md:50-53`, and reviewed nothing. |
| 5b. `image` with no criteria uses hierarchy, contrast, alignment, consistency | PASS (second run) | The first run read the installed 2.93.0 rules, which have no image section, so it made up its own criteria and does not count. The second run was told to read the repo's `review-modes.md` and quoted its default list (`review-modes.md:46`). It gave one verdict each: hierarchy FAIL, contrast FAIL, alignment FAIL, consistency PASS, `VERDICT: 3 findings`. Findings on a plain gradient with no elements are the expected result of the harsh rule. Caveat: the two runs described the gradient's corner colours differently, and neither matched the file (top-left is blue, top-right pink, bottom-left green, bottom-right yellow), so a reviewer's colour words are not evidence. |
| 5c. No argument reviews the diff | PASS (mode only) | The docs-part check "review_plan.py mode picks diff, code, image, codebase, page, plan, style" passes. |
| 6. Visual loop unchanged | PASS | Full run of all seven parts on plugin 2.94.1: core 272, safe_git 282, design_loop 529, writing 24, delegation 204, docs 175, make_page 116; 1,602 checks, all passed. |
| 7. Ranking high, medium, low | PASS | `fixture/seeded-bug.py.txt` has three planted bugs. The reviewer returned [high] SQL injection (line 6), [medium] divide by zero (line 11), [low] comment/code mismatch (line 15-16), in that order. It read the code and ran nothing. |

Note: the sandbox's installed plugin is 2.93.0, older than the repo, so a reviewer run here must be told to read the repo's rules file to exercise 2.94.1 rules. The installed plugin was not switched.
