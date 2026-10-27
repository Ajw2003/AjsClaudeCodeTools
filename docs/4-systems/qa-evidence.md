# QA evidence by change type

Status: **planned, not built.** Design approved 2026-10-27 ("Design approved: QA evidence by change type 1A 2A 3A").
Design page: `docs/plans/qa-evidence-by-type-design.html`. Build plan: `docs/plans/qa-evidence-by-type-plan.html`.
Build spec: `docs/plans/qa-evidence-by-type-build-spec.md`. Parent issue: #411 (QA pages must prove each change
with evidence for its type).

## What it owns

Every QA page proves each change with the evidence its type needs, and a QA handover is blocked until that evidence
is attached. It started from PlunderSpell pull request #445 (the Ophan in the sky): the QA page covered animation,
enemy behaviour and a model change but showed no clip, no picture and no before and after, and its change list read
"0 files, +0 −0", although the pull request committed at least 48 screenshots and a clip.

## How it will work

| Type | Needs |
|---|---|
| animation | a clip, plus a before clip and an after clip |
| gameplay, ai | a recording, plus a before clip and an after clip |
| model | a picture, plus a before picture and an after picture |
| visual | a picture, plus a before picture and an after picture |
| none | a reason why nothing is visible |

| Piece | Where | What it does |
|---|---|---|
| Evidence list | `qa.evidence` in a QA page's content file | One entry per change: its type and its files. |
| Evidence check | `scripts/make_page.py`, QA mode | Refuses a missing or wrong file for a type, a type the changed files imply with no entry (1A), a picture or clip path named in the text but not shown, and a git count of 0 files. No way to skip it (3A). |
| Type detection | `DEFAULT_EVIDENCE_PATHS` in `make_page.py`; `evidence_paths` in `docs/page-style.json` overrides | Maps changed paths to types: animation files and controllers, model files, enemy and AI scripts, runtime scripts and scenes, interface and shader files. |
| Clips | `templates/handover-page.html` | MP4 and WebM clips; a before and after pair plays side by side and in sync (2A). A file over 15 MB is refused. |
| Handover check | `scripts/house_rules/design_loop.py`, the end-of-reply "qa page" row | Counts a QA page only when `make_page.py` recorded that its evidence passed (`qa_evidence` in the stage file). |

## Invariants

- The evidence check runs on every QA page in every project; the style file's `pictures` setting does not turn it off.
- A type implied by a changed file can be added to, never dropped.

## Traps that have already cost time

- **The lock missed both approvals for this feature** because they arrived while the session sat in the folder above
  the repo. Fixed in 2.73.1 (pull request #401); see `design-loop.md`, Traps.
- **Issues made before the lock records the design approval don't count** toward "Build plan approved", so #389 to
  #395 (made while the lock had missed the approval) were not counted once it recorded it on resend.
