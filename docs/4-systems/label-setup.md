# Label setup

Status: **planned, not built.** Design approved 2026-10-15 in `Ajw2003/Unblocked` ("Design approved:
Label setup: 1A 2A 3*"). Decision: `docs/6-decisions/Decisions.md`, entry "Design approved: Label
setup". Build plan: `docs/plans/label-setup-build-plan.html`. Everything below "How it will work" is
the plan, and changes to "How it works" once built.

## What it owns

Making sure a repo has the three house labels before the plugin depends on them. The issue workflow
asks for `AjsAgent created this` on every issue, and the design loop reads `in progress` and
`needs review` to decide whose move it is. A repo without them stalls the loop.

## The labels

| Name | Colour | Description |
|---|---|---|
| `AjsAgent created this` | `5b6b7a` | Opened by AJ's agent |
| `in progress` | `FBCA04` | AJ's agent is working on it |
| `needs review` | `0E8A16` | Waiting on aj |

## How it will work

| Piece | Where | What it does |
|---|---|---|
| Label setup | `scripts/labels.py` (new) | Lists the repo's labels with `gh api repos/<owner>/<repo>/labels --paginate`, creates each missing house label with `gh label create`, and returns what it created, what already existed and what failed. It never raises: a missing `gh`, no sign-in or a 403 comes back as a one-line note. |
| Hook calls | `scripts/hook.py` | Runs label setup when planning starts ("Design approved"), when the issue workflow asks for issues (`_issues_plan_note`), and before a label refusal (`_loop_label_refusal`). The note names the labels it created. |
| Command | `commands/labels.md` (new) | `/house-rules:labels [owner/repo]` runs label setup on the current repo or the named one, and lists what it created and what was already there. |
| Advice | `scripts/hook.py`, `rules/detail/issue-workflow.md` | Every `gh issue edit --add-label` in the advice becomes the REST form: `gh api repos/<owner>/<repo>/issues/<n>/labels -f "labels[]=in progress"` to add, `gh api -X DELETE repos/<owner>/<repo>/issues/<n>/labels/in%20progress` to remove. |
| Recorder | `_label_changes` in `scripts/hook.py` | Also records label changes made with the REST form, so the fallback record stays right when GitHub can't be read. |

## Invariants

- Creating a label is the only write. An existing label is never changed or deleted, whatever its
  colour or description.
- Label setup never blocks or crashes a hook. A failure becomes a note naming what failed.
- Tests stand in for GitHub with a file, the way `HOUSE_RULES_LOOP_LABELS_FILE` does for issue labels.

## Traps that have already cost time

- The GitHub tool (`issue_write`) cannot create a label; it refuses one the repo lacks with "failed to
  resolve label".
- `gh issue edit --add-label` goes through GraphQL, which answers HTTP 403 in a cloud session. REST
  works.
- A label name with a space must be written `in%20progress` in a REST path.
- In this cloud session `gh auth status` reports the token as invalid, yet `gh api` calls succeed
  through the session's proxy (checked 2026-10-15 by listing this repo's labels). Don't use
  `gh auth status` to decide whether label setup can run; try the call and report its error.
