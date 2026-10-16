# After every pull request

**Owns:** making sure every pull request says how to test it in a new session and what's next, and
the configurable agent name that credits it. Status: **planned**, under issue #297 ("After every pull
request, a check makes sure it says how to test it and what's next"). Design approved 2026-10-16
("Design approved: after-PR answers 1A 2A") on `docs/plans/after-pr-295-test-and-next.html`. The rule
itself is in `rules/house-rules.md`, with its detail in `rules/detail/after-pr.md`.

## How it will work

| Piece | Where | What it does |
|---|---|---|
| Pull request body check (#298) | `hook.py`, `event_guardgithub` and the `gh pr create` path of `guard` | Refuses a body with no "How to test it in a new session" heading or no "What's next" heading, naming each one missing. |
| QA page fields (#299) | `make_page.py`, `apply_qa` | Requires the lists `qa.test` and `qa.next`, and shows them as two Changes items. |
| "after pr" checkpoint (#300) | `hook.py`, `CHECKPOINTS` | When the turn opened a pull request, or the reply says one merged, the reply must link a page or answer both questions. Blocks once. |
| Agent name (#287) | `hook.py`, one `agent_name()` function; `tools/install.py` | Every credit line, branch prefix and identity notice reads the name from one place. Setup writes `HOUSE_RULES_AGENT_NAME=AJ` into `settings.json`'s `env`. |

## Invariants

- The two section names are defined once in `hook.py` and reused by `make_page.py`, not copied.
- Each refusal names its fix, like every other enforced check (#293).

## Traps already found

- A cloud container's git name is `Claude`, and cloud sessions never run the setup scripts (checked
  2026-10-16: `git config --global user.name` printed `Claude`). The git-name default would credit
  "Claude's agent" there. The build plan's choice on cloud sessions settles it.
- Once the identity fix has run, the git name is `AJ's agent`, so the name must drop a trailing
  "'s agent" before it is used.
