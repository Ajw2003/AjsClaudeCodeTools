# Reply check timing (2026-11-25)

Measured in the cloud sandbox with `tools/time_hooks.py` helpers: the Stop event `roadblocks` run through `run.sh` in a throwaway git repo, payload with `last_assistant_message` "Done. All checks passed." and a one-line transcript.

| Run | Judge on | Judge off (`HOUSE_RULES_JUDGE=off`) |
|---|---|---|
| Median of 3 (all-events sweep) | 5,188 ms | not run |
| One repeat | 5,519 ms | 63 ms |

Every other hook event measured 64 to 89 ms, except SessionStart `profile` at 338 ms (once per session). The call is `claude -p --model haiku` (core.py `_goal_argv`); its timeout is 22 s (`GOALCHECK_TIMEOUT`). Four runs in total, so treat the figure as "about 5 seconds", not an exact value.
