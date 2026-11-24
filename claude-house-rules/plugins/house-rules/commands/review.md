---
description: Review code, a page, an image, a screen's style, the uncommitted diff or a whole repo with the reviewer agent
argument-hint: <path|.> [style] [criteria text]
---

`house-rules:reviewer` (the agent) reviews in eight modes. This command picks the mode from the
path, runs the reviewer, and has the main session save the report. Reviewers write nothing new.

First pick the mode with the plugin's own script, never a path you construct by hand. Pass the
path as TARGET; if the word `style` follows it, pass `--style`; the rest of the text is criteria
(or the style to compare against) and is not given to the script:

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/review_plan.py" mode $ARGUMENTS
```

If the path in the command you are about to run does not begin with a real absolute plugin
directory (it is empty, still shows `${CLAUDE_PLUGIN_ROOT}`, or begins with `/scripts`), STOP and
tell the user the plugin root did not resolve. Do not search `~/.claude/plugins` for a copy or
guess a path - the cache holds several versions. If the script prints `error:` (exit 2), report
that line and stop.

It prints `mode:`, `report:` (the folder for the saved report), `criteria:` (the text to pass on, or `none`) and, in plan mode, `design:`. Put criteria or style text that contains punctuation in quotes.

## Every mode except a whole-repo sweep

Spawn ONE `house-rules:reviewer` with the Agent tool. Tell it the mode and the target. For plan
mode also give the design page from `design:` (or say there is none). For image and style modes
give the text after the path as the criteria or the style. In style mode with no stated style
and no project UI guide the reviewer stops and says so; pass that on, do not invent a style.

## Codebase mode (target `.`)

1. Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/review_plan.py" units`. If it printed a `notice:`
   line, show that line to the user BEFORE starting anything else.
2. Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/review_plan.py" batches`. Each line is
   `<unit>`, a batch number and a comma-separated file list.
3. Spawn one `house-rules:reviewer` in codebase mode per batch, ONE AT A TIME, naming its files
   and telling it to start every finding with `[high]`, `[medium]` or `[low]`. There is no
   folder cap.
4. Check each reviewer's wait every minute with `python "${CLAUDE_PLUGIN_ROOT}/scripts/waitfor.py"`
   with a 60-second deadline per reviewer (the agent deadline in `rules/waits.json`). A batch
   that does not finish is listed as not reviewed, never dropped.
5. Merge the findings ordered high, medium, low, then by file path, and list every not-reviewed
   batch by unit and number.

If the script prints `error:` for `units` or `batches` (exit 3, not a git repo), report that line and stop.

## Saving and reporting

The main session (not the reviewer) saves the full report as `report.md` in the `report:`
folder. Chat gets only a short verdict: finding counts, the top three findings, the report path,
and any not-reviewed batches. Never claim a mode ran that did not.
