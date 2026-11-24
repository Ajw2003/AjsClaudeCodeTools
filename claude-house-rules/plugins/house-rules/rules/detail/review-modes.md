# Reviewer modes

The spawn prompt names the mode. No mode named: diff mode.

## page
Read a design or build-plan page cold, with no author reasoning. Hunt for:
- holes: a case nobody covered
- traps: a step that bites later
- contradictions: two parts disagree
- reversals: undoes a past decision in docs/6-decisions/Decisions.md without the page saying so
- unanswered questions

A question the code or docs can answer: look it up and write the answer into the findings.
A question that is a design choice: do not decide it. Return it as lettered options with one marked suggestion.
Also apply the wording rules in agents/editor.md.
Output: `before` -> `after` lines, a few words of why each, then `VERDICT: clean` or `VERDICT: <n> findings`. Not limited to 10 lines.

## plan
Read a build plan against its approved design. Check that:
- every design item has a step
- no step lacks a design
- the order works
- each issue has done-criteria
- the plan lists one acceptance test per design item

Same output as page mode.

## acceptance
Run the finished feature and screenshot each flow. Compare with the approved design page.
Report PASS or FAIL per acceptance item, with evidence paths.
Write the report and screenshots only under docs/qa/<feature>/ (conventions: skills/visual-loop/SKILL.md). Never edit source code.

## diff (default)
Findings only, one per line: `path:line: problem. fix.` Ten lines or fewer. No praise, no summary. Change nothing.
