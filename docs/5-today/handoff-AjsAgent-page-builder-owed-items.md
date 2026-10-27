# Handoff: page builder owed items (2026-10-27)

**For.** The page builder (`claude-house-rules/plugins/house-rules/scripts/make_page.py`) refuses a
page until everything that page kind owes is filled in. The refusal lists every missing item at once
and names each one by its place on the page. This applies to proposal pages ("Design approved: …"),
build plan pages ("Build plan approved: …") and QA pages ("QA passed: …"). aj asked for it on
2026-10-27.

**Why.** The usage limit handoff build plan page (branch `AjsAgent/project-thread-bklzel`, issue #406)
went out with three change rows that showed "null" and no rows naming files. The builder refuses a
page for only four reasons today: a reserved colour (`check_reserved`), a visual change with no
picture (`check_pictures`), a wrong approval phrase (`check_approval`), and missing QA fields (QA
mode). The template (`templates/handover-page.html`, the `PAGE.changes` renderer) prints an empty
detail as "null". The builder's after-build visual check looks only for script errors and overflow.

**Where it stands.** Issues are open: parent #419, steps #420 (no empty field on any page), #421
(proposal page), #422 (build plan page), #423 (QA page) and #424 (tests, docs, version and a real
run), all labelled `in progress`. No design page yet, and no code changed. This branch is cut from
`main` at 2.73.2.

**Next step.** Write the design proposal page with `make_page.py build` and the approval phrase
"Design approved: page builder owed items". The open questions it should put to aj as choices:
whether the owed lists live in `make_page.py` or in a data file beside the template; whether an
older page in `docs/plans/` that now fails is rebuilt or left; and whether the after-build visual
check also searches the rendered text for "null" and "undefined". After that, a build plan page
("Build plan approved: page builder owed items"), then build #420 to #424 in order, writing each
step's cases in `scripts/checks/make_page.py` before its code.

**Test case.** `git show b7a1c13:docs/plans/2026-10-27-usage-limit-handoff-build-plan.page.json`
is the broken content. It must be refused, naming its three empty change rows and each row that
lists no files. The fixed content at a5c22c6 on `AjsAgent/project-thread-bklzel` must build.

**Watch out.** Don't touch the QA pages work in #389 to #395 (QA evidence by change type, branch
`AjsAgent/qa-evidence-by-type`). #423 waits for #389 to merge. No Claude credit and no public links
in commits, issues or this note.
