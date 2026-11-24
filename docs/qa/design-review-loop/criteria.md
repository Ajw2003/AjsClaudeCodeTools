C1. The reviewer file has page, plan and acceptance modes, the model pins pass, and a page-mode run left before/after findings | proof: run | page: n/a
C2. A page with a missing, stale or current review stamp is flagged, flagged, quiet at reply end; review and QA pages are exempt | proof: run | page: docs/plans/t-stamp.html
C3. Acceptance fails round 1, passes after a fix, stamps only on NEXT: done, and a later commit makes the stamp stale | proof: run | page: n/a
C4. QA mode refuses a missing or stale stamp, builds with an empty unverified list, and opens with the ledger | proof: still | page: docs/plans/qa-feat.html
C5. The self-judging template prints PASS or FAIL alone and its handover card passes the format check | proof: run | page: n/a
C6. The combined approval moves Design to Build when reviewed plan issues exist, refuses when not, and two-step still works | proof: run | page: n/a
C7. In Build a reversible question is parked with no edit hold, a [HARD STOP] one is asked and holds, a helper's is parked | proof: run | page: n/a
C8. A deviation row holds plan, done, why, undo; an unknown permission mode counts as attended; a missing entry is caught at turn end | proof: run | page: n/a
C9. verify.py and verify_tools.py exit 0, docref and docs_drift pass, four reversals logged, version and changelog at 2.92.0 | proof: run | page: n/a
