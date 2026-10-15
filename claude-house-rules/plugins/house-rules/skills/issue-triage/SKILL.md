---
name: issue-triage
description: Triage a repo's open GitHub issues - find the ones already done on the default branch
  or duplicated, group the rest into bursts that each become one branch and one pull request, and
  write it all up as a proposal for the user to approve. Use when asked to triage, tidy, group or
  sprint-plan a repo's issues, or when the open list has grown past what the roadmap tracks. Not
  for planning a single new feature - that is the issue-workflow rule.
---

# Issue triage

The output is one page, `docs/plans/issue-triage-<YYYY-MM-DD>.md`, and nothing else until the
user approves it. Closing, relabelling and creating issues all wait for that approval: closing
an issue always asks, and the user tests first (house rule "A plan over three steps becomes
issues").

The proposal must be a page built with `scripts/make_page.py` (house rule "Show, don't tell"),
not a chat message. Write every issue number as "plain name (#N)" so `scripts/clarity.py` passes.

First worked example: `Ajw2003/focus-deck-app` issue #162, whose page is
`docs/plans/issue-triage-2026-10-15.md` in that repo.

## 1. Gather - the record, not memory

1. Every open issue: number, title, labels, body. Reach GitHub with the `gh` CLI where it is
   installed and logged in, otherwise with the GitHub MCP tools; say which one you used. Limit
   the fields (`--json`, or `fields` on the MCP tools) so the bodies of 50 issues do not flood the
   context. The MCP read tools do not return an issue's internal id, which sub-issue linking
   needs; an `issue_write` update that changes nothing does return it.
2. Every closed issue's title, to spot repeats.
3. Every commit on the default branch that mentions an open issue:

   ```bash
   git fetch origin main
   for n in <open issue numbers>; do
     git log origin/main --format='%h %s' -E --grep="#$n\b"
   done
   ```

4. Every merged pull request into the default branch, with each `#N` in its title or body
   matched against the open list. A large listing goes to a file; parse it with a short script
   rather than reading it whole.
5. The roadmap (`docs/2-roadmap/Roadmap.md`) and any parent issues with written plans: they may
   already set an order.

## 2. Sort each open issue into exactly one bucket

| Bucket | Evidence that puts it there |
|---|---|
| **Done** | A merged pull request says `Refs #N` (or `Part of #N`) and the commits match. A parent whose every child is done is done too. |
| **Duplicate** | Another open issue covers it, or a plan says it was folded in. Name the survivor. |
| **Overtaken** | A later redesign changed the thing it is about. Read the current code and cite `file:line`; if still unsure, it goes to "needs the user". |
| **Needs the user** | No body and a title too vague to build from, or a judgement only they can make. Write the exact question. |
| **Burst** | Real, open work. |
| **Later** | Research, reviews, big ideas with no near plan. |

A title match alone is never proof of "done": the pull request must reference the issue, or the
code must visibly do the thing. When an old title repeats, check which copy is open; usually the
older one was already closed and the open one is the survivor.

## 3. Group the bursts

- One burst = one branch = one pull request (say so when it needs two, and why).
- Group by the code they touch and the fix shape they share, not by label. Labels on a
  user-filed issue are often a scatter of every category.
- Order: data loss first, then broken sync or silent failures, then wrong looks or feel on a
  phone, then polish, then new features.
- An existing ordered plan (a parent issue with numbered children) stays one burst in its own
  order; do not re-split it. That existing parent is reused as the burst's parent, not
  duplicated.
- Each burst names its issues, one line on the shared fix, and the files it touches.

## 4. Write the page

Sections, in order: what was checked (with the commands), done-close-after-test (a table with the
pull request, commit, and the one thing to test), duplicates, the bursts, later, docs that are now
out of date, and what happens on approval. Plain titles; every issue number is written as
"plain name (#N)".

## 5. On approval

1. Close each done issue with a comment linking its merged pull request, `state_reason`
   `completed`, and the `Claude completed this` label. Duplicates close with `state_reason`
   `duplicate` and `duplicate_of`.
2. One parent issue per burst (or the existing ordered parent), labelled `AjsAgent created this`
   plus a category; attach its issues as sub-issues, using the internal ids from step 1. Burst
   issues need "Depends on", "Depended on by" and "Done when" sections
   (`clarity.ISSUE_SECTIONS`).
3. Update the roadmap tier to match, and leave a dated `docs/6-decisions/Decisions.md` entry if
   the grouping replaces an earlier one.
4. Start the first burst.
