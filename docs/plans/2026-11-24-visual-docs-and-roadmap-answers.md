# aj's answers to the visual skills proposal (recovered 2026-11-24)

Source: five screenshots of the first published page and the text aj typed for choice 8. Choices 1 to 3
were not in the screenshots, and choices 9 and 10 were lost when the browser tab was closed. This file
and the `answers/current` document in the artifact database (`THgBL8SamiG6HzkfbYpJz2`) hold the same answers.

| Choice | Question | Answer |
|---|---|---|
| 1 | How fresh should the views be? | Not recovered |
| 2 | Which two views? | Not recovered |
| 3 | Where do the views live by default? | Not recovered |
| 4 | How is the visual-docs page laid out? | A, a new page template for the six sections |
| 5 | Do the roadmap views group by the repo's roadmap milestones? | A, yes, group by the milestones in that repo's `docs/2-roadmap/Roadmap.md` |
| 6 | How is the visual-docs page checked for wording? | B, the editor helper plus image review of screenshots |
| 7 | When does visual-docs run the review? | Own answer: "A + B" (A, once per build automatically, plus B, when asked with `/house-rules:visual-docs review`) |
| 8 | Where does an issue closed as completed, with no merge naming it, go? | Own answer, verbatim below |
| 9 | How are the branch names set? | Lost, to be asked again |
| 10 | What does visual-docs produce? | Lost, to be asked again |

## Choice 8, aj's own answer, verbatim

"Two different roadmaps exist one tracking only main with merged commits, and another tracking the latest
branch with commit history above 1 commit, label them as such so we can tell in dev from shipped both on the
same page."

## What choice 8 changes in the design (not yet applied to the page)

- The page shows two labelled roadmaps: one for main (merged commits, called Shipped) and one for the
  latest branch with more than one commit of history (called In dev), both on the same page.
- It answers choice 8 only indirectly: it says how to tell In dev from Shipped, not where a closed-without-merge
  issue lands. That still needs a clear answer.
- It also implies the dev branch could be found automatically (the latest branch with more than one commit),
  which touches choice 9, so choice 9 should be asked again with this in mind.
