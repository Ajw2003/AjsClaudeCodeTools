# A plan over three steps becomes issues; a pull request links, never closes

The loop, in order:

1. A plan with more than three steps (numbered lines, `- [ ]` items, `### Step` or `### Change`
   headings) is approved. The `delegate` hook counts the steps and records that issues are needed.
2. Before any source edit, I create one parent issue for the plan and one child issue per step with
   `gh issue create`. Each child says `Part of #<parent>` in its body. Titles are plain language a
   non-programmer can follow. I show the user the issue numbers.
3. Until a parent and at least one child exist (two issues with the `AjsAgent created this` label),
   the `commitgate` hook refuses Write, Edit and NotebookEdit on source files. Files under `docs/`
   and `.claude/`, any `.md` file, and files outside the project stay editable.
4. When work on a step starts I mark its issue `in progress`
   (`gh issue edit N --add-label "in progress"`); I remove the label when the issue closes.
5. The pull request body says `Refs #N` (or `Refs owner/repo#N`, or `Part of #N`, or a line
   `No-issue: <reason>`). A closing word (close, fix, resolve in any tense) followed by an issue
   reference is refused, because GitHub would close the issue at merge, before the user has tested.
6. Closing an issue always asks. The approval prompt is the user's go-ahead. On approval I also
   run `gh issue edit N --add-label "Claude completed this" --remove-label "in progress"` and comment
   with the merged pull request link. Commenting on or creating issues is never gated.

Label rules: every issue I create carries at least one category label and `AjsAgent created this`.
If the repo lacks that label I create it first with `gh label create`. An issue created without it
does not count toward the gate, and the Focus Deck board ignores it.

What the hooks do and do not do: they force me to do this; none of them runs `gh issue create` or
`gh issue close` itself. The state is one file, `house-rules-issues.json`, in the git directory, so
a subagent worktree (its own git directory) is not gated by the main session's plan. A corrupt state
file is reported in one line and treated as no gate. `HOUSE_RULES_ISSUES=off` disables every part of
this, in the same style as `HOUSE_RULES_AUTOSAVE=off`.

The session also starts with the open issue titles (up to 10, `gh issue list`, 5 s timeout, cached
60 s) when `gh` is installed and the repo has a GitHub remote.
