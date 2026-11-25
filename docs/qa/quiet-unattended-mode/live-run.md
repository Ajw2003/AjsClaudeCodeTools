# Live headless runs of quiet unattended mode (#644)

Four real runs of `tools/overnight.sh` driving a real headless `claude -p`, each on a throwaway git repo in the Build stage with a guarded step list filed under a fixed session id. A thin `claude` wrapper added this branch's plugin and a model flag; a `uuidgen` stub gave the fixed session id. The two real steps were "create a.txt" and "create b.txt"; the four finish steps were stand-ins (a file must exist), because the real finish checks need a docs tier, pictures and a QA stamp. Saved output is in `evidence/`.

| Run | Model | What it showed |
|---|---|---|
| 1 | haiku | Found two bugs (below), stopped on purpose after the fixes. |
| 2 | haiku | 42 step-list stop blocks held the agent; the hook recorded steps 1, 2 and 5 done; three steps the task never mentioned were marked stuck after three blocks each, so the loop ended "all steps done" and ran its final QA pass. |
| 3 | haiku | The first `claude` was killed 45 seconds in; `overnight.sh` saw `OPEN 4`, resumed the same session by id (one resume prompt, never `--continue`), 24 more stop blocks held it after the resume, all six steps ended done, then the final QA pass built a QA page. |
| 4 | sonnet | The agent decided the header colour itself and logged it as K1 with its assumption, why and how to undo. Haiku logged zero `decide` calls in runs 1 to 3 and recorded its choice in a commit message instead. |

## Bugs the live runs found, now fixed

1. **Step results were never recorded.** The hook matched the command text `ledger_note.py check`, but the agent called the script through a shell variable. Now it matches the words of the call and verifies a pass against the run file the poll leaves behind, so a typed `RESULT` line alone is refused.
2. **A looping agent was never marked stuck.** The stuck rule counted a changed `HEAD` as progress, and the autosave commit changes `HEAD` at every stop. It now compares the tree fingerprint, which ignores autosave and notes.
3. **The agent could not find `ledger_note.py decide`.** The unattended note and the stop block now carry the full command with its path.

## Verified live

Stop hooks block in a resumed headless run; resume by session id works with hooks still active; the stuck rule ends a run that cannot finish; the final QA pass runs; a stronger model logs a look choice to the ledger.

## Not verified live

- **Self-approval by a hook.** It needs a reviewer helper to finish inside a headless run; the suites cover it, a live run does not.
- **A ninth consecutive stop block with the cap at 1000.** Run 2's transcript shows nine block records without a tool call between them, but one block can appear in more than one record, so this is not proof.
- **The real stop-failure payload and a rate-limit wait.** No run hit a usage limit.
- **Whether the web app has `/goal`**, and the pause-goal tool's real name.
- **Haiku does not log choices.** The rule and the messages say so; compliance depends on the model.
- **The finish steps were stand-ins**, not the real docs, pictures, tests and QA checks.

## Run 5 (sonnet, neutral prompt) and the fix it forced

The prompt only said "a header in a colour of your choice", with no mention of deciding or logging. The agent made every file, chose a teal header (`evidence/live-run5-page.html`) and logged no choice, although the unattended note naming `ledger_note.py decide` was in its context and eight step-list blocks reached it. So the rules alone do not make a model log. The fix is a hook: when every step is closed and nobody is present, the stop is blocked once if the ledger holds no logged choice, asking the agent to log what it decided or reply "No choices made." (`_choices_check` in `design_loop.py`; tested in the #640 stop-step case). The run was cut at the 60-second background limit after all files existed, so it did not reach the new hook.

## Run 6 (sonnet, neutral prompt, with the choices check)

Same neutral prompt as run 5 ("a header in a colour of your choice"). This time the ledger holds K1 (header colour teal, with its assumption, why and how to undo) and K2 (title and header wording): the agent logged them after the stop was sent back once. Evidence: `evidence/live-run6-ledger.md`, `evidence/live-run6-overnight.log`, `evidence/live-run6-page.html`. The loop ended "all steps done", as before.

Two things the round 3 reviewer found in run 6, both now stated here:

1. **The run was started twice.** The first launch's `claude` was still running when the second `overnight.sh` started, so the second launch's `--session-id` call failed ("Session ID ... already in use"), and K1 and K2 were logged in the `--resume` leg. The choices check still fired once and the agent logged K1 and K2 after it.
2. **The final pass reopened the steps.** The final pass wrote `docs/page-style.json` and logged a third choice (K3). That file was not in the tree fingerprint's ignore list, so all six steps went back to open and the step-list blocks held the pass for about five minutes. Fixed: `acceptance.py tree` now ignores `docs/page-style.json`, with a case in the delegation suite. The final pass also ended with a "NEEDS YOU" question, because the fixture repo has no `origin/main` so the real docs and pictures finish checks could not pass; that is a fixture limit, not a rule change. The evidence copies above are now the finished ones (the ledger holds K1 to K3).
