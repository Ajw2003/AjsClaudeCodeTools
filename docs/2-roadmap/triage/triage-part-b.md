# Triage, part B (issues #304 to #491), 2026-11-09

Made by a read-only scout from `open-issues-part-b.json`. It read the bodies for #304 to #390; #391 to #491 were
judged from titles plus a search of the code, so most KEEP verdicts there mean "no code found", not a full body
read. Format: `#N | theme | verdict | reason`. The themes and verdicts are listed in `README.md` beside this file.

**Corrections after checking:** the scout marked #486, #487 and #408 KEEP or UNSURE, but the code is on the
branch `AjsAgent/session-handoff`: `event_autosave_final` (delegation.py:1492), `_autosave_facts` (:1295) and
`event_pickup` (:2139). They are corrected to DONE on branch below.

#304 | T6 | KEEP | No transcript cleaner or two-helper code found.
#313 | T4 | KEEP | make_page.py:137 enforces pictures only when the style file says "required".
#321 | T5 | UNSURE | QA test for #315's read-back; settle by checking #315.
#334 | T13 Unity docs layer | KEEP | No reader for prefabs and scenes.
#335 | T4 | DONE | handover-page.html:416-421 falls back to execCommand("copy"). Code read, not run.
#336 | T10 | KEEP | No research or sources tier.
#350 | T7 | KEEP | Parent; children #351-#355 unbuilt.
#351 | T7 | KEEP | rules/attribution-patterns.json does not exist.
#352 | T7 | KEEP | .github/workflows/attribution-guard.yml does not exist.
#353 | T7 | KEEP | No merge gate on the check result.
#354 | T7 | KEEP | tools/attribution_guard_install.py does not exist.
#355 | T7 | KEEP | Rollout depends on #352-#354.
#377 | T4 | KEEP | No refusal for a proposal page with empty choices.
#378 | T4 | KEEP | No lang on html; #b35f00 on #fdeed9 contrast still at line 9.
#379 | T1 | DUP #429 | Same system-reminder relay bug (core.py:1919-1928).
#382 | T9 | UNSURE | Parent of restructure steps; children not checked.
#383 | T8 | DONE | event_rclink at delegation.py:1773, hooks.json:263.
#384 | T10 | KEEP | Parent; no changelog code.
#385 | T10 | KEEP | templates/changelog.page.json does not exist.
#386 | T10 | KEEP | No changelog check in the docs checks.
#387 | T10 | KEEP | No changelog check on pull requests.
#388 | T10 | KEEP | Rule text has no changelog sentence.
#389 | T4 | DUP #411 | Same title and scope.
#390 | T4 | DUP #412 | Same title and scope.
#391 | T4 | DUP #413 | Same title and scope.
#392 | T4 | DUP #414 | Same title and scope.
#393 | T4 | DUP #415 | Same title and scope.
#394 | T4 | DUP #416 | Same title and scope.
#395 | T4 | DUP #417 | Same title and scope.
#396 | T8 | KEEP | Parent; children mixed.
#397 | T8 | DONE | delegation.py:656-688 _worktrail_note.
#398 | T8 | DONE | hook.py:165-172 handover_links_owed.
#399 | T10 | UNSURE | Docs, version 2.73.1 and QA page; not checked.
#400 | T8 | UNSURE | Session-start transcript link not located.
#403 | T8 | UNSURE | Ledger code exists (delegation.py:623); fixes not verified.
#404 | T10 | KEEP | Docs and QA page for gap fixes.
#405 | T7 | UNSURE | Credit guard exists in safe_git.py; claude.ai link refusal not confirmed.
#406 | T6 | DONE on branch | Parent; children built on AjsAgent/session-handoff, QA open.
#407 | T6 | DONE on branch | safe_git.py:2049-2092 handover_handoff_check.
#408 | T6 | DONE on branch | event_pickup, delegation.py:2139 (corrected).
#409 | T1 | UNSURE | Quoted-approval change is on the branch (design_loop.py _LOOP_QUOTED_RE); feature recording not checked.
#410 | T6 | DONE on branch | Rule text, docs and version 2.77.0 on the branch.
#411 | T4 | KEEP | No evidence-by-type check.
#412 | T4 | KEEP | No evidence-by-type check.
#413 | T4 | KEEP | No per-type evidence requirement.
#414 | T4 | UNSURE | Video clip support not searched.
#415 | T4 | KEEP | No refusal for a 0-changed-file count.
#416 | T4 | KEEP | No evidence-gated handover reply.
#417 | T4 | KEEP | Rule text, docs, version and clip QA page not built.
#419 | T4 | KEEP | Parent; no owed-items gate.
#420 | T4 | KEEP | No empty-field refusal.
#421 | T4 | KEEP | No proposal owed list.
#422 | T4 | KEEP | No build-plan owed list.
#423 | T4 | KEEP | No QA owed list.
#424 | T4 | KEEP | Tests, docs and run follow unbuilt children.
#429 | T1 | KEEP | core.py:1919-1920 still treats a system-reminder as relayed, so approvals are skipped.
#430 | T8 | KEEP | Parent; no visibility changes.
#431 | T8 | UNSURE | First-reply link in cloud sessions not searched.
#432 | T8 | UNSURE | delegation.py:691 _write_subagent_ledger may cover it.
#433 | T8 | UNSURE | Ask-first for long calls not searched.
#434 | T8 | KEEP | No 2-minute progress line.
#435 | T8 | UNSURE | Hook traces exist (hook.py:143-186); default-on not verified.
#436 | T10 | KEEP | Docs, version and QA page follow children.
#437 | T9 | KEEP | Nine-plugin split not present.
#438 | T9 | KEEP | Split not built.
#439 | T9 | KEEP | No shared library plugin.
#440 | T9 | KEEP | Not split out.
#441 | T9 | KEEP | Not split out.
#442 | T9 | KEEP | Not split out.
#443 | T9 | KEEP | Not split out.
#444 | T9 | KEEP | Not split out.
#445 | T9 | KEEP | Not split out.
#446 | T9 | KEEP | Not split out.
#447 | T9 | KEEP | Not split out.
#448 | T9 | KEEP | Not split out.
#449 | T9 | KEEP | delegation.py still in house-rules.
#450 | T9 | KEEP | Multi-plugin install tooling not built.
#453 | T12 | DONE | builder.md:16 rule; enforced by safe_git.py:533-610.
#454 | T3 | DONE | safe_git.py:533 RERUN_LIMIT = 2; _rerun_check at :603.
#455 | T12 | UNSURE | Docs, version and real builder session not checked.
#457 | T2 | UNSURE | Parent; children mixed.
#458 | T2 | UNSURE | delegation.py:67 still has judgement-call wording.
#459 | T2 | KEEP | No held-state code.
#460 | T2 | KEEP | No decided-for-aj check.
#461 | T4 | UNSURE | Page check for choices not confirmed.
#462 | T4 | UNSURE | Pictures inside the page not searched (copy_pictures still writes a folder, make_page.py:149).
#463 | T10 | KEEP | Docs, version and QA page follow children.
#464 | T4 | UNSURE | Second copy method exists; one-tap text box not found.
#465 | T3 | DONE | safe_git.py:564-587 counts only a statement's script, not a read.
#466 | T4 | UNSURE | No icon-name validation seen (make_page.py:227).
#467 | T3 | DONE | safe_git.py:564-587 counts only the script actually run.
#468 | T2 | KEEP | No code-preview step.
#469 | T4 | KEEP | No editable planned-code block.
#470 | T2 | KEEP | Approval-waits-for-code rule not found.
#471 | T2 | KEEP | No departure list on QA pages.
#472 | T10 | KEEP | Rule text, docs and run for code preview not built.
#473 | T2 | KEEP | No readability check.
#474 | T12 | UNSURE | Readable-code skill not searched.
#475 | T1 | UNSURE | Issue counting during Plan not checked.
#476 | T3 | UNSURE | Parent of #477-#482.
#477 | T3 | UNSURE | Not checked.
#478 | T3 | UNSURE | safe_git.py:566 cites #478; other refusals not checked.
#479 | T6 | UNSURE | Not checked.
#480 | T2 | UNSURE | Not checked.
#481 | T1 | UNSURE | Not checked.
#482 | T9 | UNSURE | Not checked.
#484 | T3 | DONE | design_loop.py:250-323 gates sed -i, tee and redirect writes. Search evidence only.
#486 | T6 | DONE on branch | Autosave on every branch (corrected).
#487 | T6 | DONE on branch | event_autosave_final, delegation.py:1492 (corrected).
#488 | T6 | KEEP | Parent for #489-#491, opened today.
#489 | T6 | KEEP | Per-folder saves not built.
#490 | T4 | KEEP | Pictures inside the page not built.
#491 | T1 | KEEP | Approval-line registration not built.

Clusters: #379 duplicates #429; #389-#395 duplicate #411-#417; #468, #470 and #473 overlap on build-plan code
preview; #406 overlaps #486-#491; #335 is done, so #464's copy part is partly superseded.
