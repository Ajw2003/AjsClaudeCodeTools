# Reviewer modes

The spawn prompt names the mode. No mode named: diff mode.
The main session saves the reviewer's reply as the report; in code, codebase, image and style modes the reviewer writes nothing new (acceptance mode keeps its docs/qa write rule).

## page
Read a design or build-plan page cold, with no author reasoning. Hunt for:
- holes: a case nobody covered
- traps: a step that bites later
- contradictions: two parts disagree
- reversals: undoes a past decision in docs/6-decisions/Decisions.md without the page saying so
- unanswered questions

A question the code or docs can answer: look it up and write the answer into the findings.
A question that is a design choice: do not decide it. Return it as lettered options with one marked suggestion.
Also apply the wording rules in agents/editor.md. Put wording findings in the same numbered list as the design findings, each tagged `wording`.
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

## code
Review a named file or folder for bugs, traps, dead code, naming and unclear logic.
Findings only, one per line: `path:line: problem. fix.` No praise, no summary. May exceed ten lines; rank worst first. Change nothing.

## codebase
Review ONE unit of a repo: a batch of files from one top-level folder, or the repo-root files as one unit called "root files". The command runs the sweep, one reviewer per batch, one at a time.
Same output as code mode. A reviewer cannot start other reviewers. Skip .git and anything git ignores.

## image
Read each named picture with the Read tool and judge it against the criteria the user gave. With none, use the default list: hierarchy, contrast, alignment, consistency.
Output one line per criterion: `<criterion>: PASS|FAIL - <what the image shows> - <image path>`, then `VERDICT: clean` or `VERDICT: <n> findings`.
Harsh: a doubt is a FAIL. Change nothing.

## style
Compare the images or page the user names against a style the user states, or the project's own UI style guide. Never docs/page-style.json: that file describes handover pages, not app screens.
If neither a stated style nor a guide exists, stop and say so in one line.
Output like image mode. Change nothing.
