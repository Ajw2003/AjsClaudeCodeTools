# Setting up a cloud environment for house-rules

From house-rules 2.74.0, every tool is refused until the plugin knows the agent's name. Cloud sessions
start fresh each time, so the name is set once per cloud environment, as environment variables. Repeat
these steps once in each Claude account's cloud environments.

## The two values

- `HOUSE_RULES_AGENT_NAME`: that account's GitHub login in lowercase, followed by `sAgent`. For the
  account Ajw2003 it is `ajw2003sAgent`. Each account gets its own name.
- `HOUSE_RULES_OWNED_BRANCHES`: extra branch-name prefixes that count as the agent's own, separated by
  commas. For Ajw2003 it is `AjsAgent/,claude/`, so the existing branches keep working. A new account with
  no old branches can leave it empty.

## Steps (once per account and environment)

1. In the Claude app, open a cloud session in that account.
2. Open the cloud environment menu in the session's title bar, then choose **Edit**.
3. In the environment variables box, paste these two lines, with the agent name changed for this account:

   ```
   HOUSE_RULES_AGENT_NAME=ajw2003sAgent
   HOUSE_RULES_OWNED_BRANCHES=AjsAgent/,claude/
   ```

4. Save. The next new session picks the values up; a session that is already open does not.
5. To check, start a new session and ask the agent to run
   `python3 <plugin>/scripts/settings.py show`. It should list both values as coming from the environment.

## Repeating it across Claude accounts

The values come from the GitHub account the agent works as, not from the Claude account. So every Claude
account that works on Ajw2003's repos pastes the same two lines, unchanged:

```
HOUSE_RULES_AGENT_NAME=ajw2003sAgent
HOUSE_RULES_OWNED_BRANCHES=AjsAgent/,claude/
```

Each Claude account has its own cloud environments, so repeat steps 1 to 4 in each one. A tick list:

| Claude account | Environment | Done |
|---|---|---|
| | | |

Not yet tested: step 5's command exists only once step 3 of the restructure (#341) ships in 2.74.0, and
the menu wording in steps 2 and 3 is taken from Claude Code's own environment help on 2026-10-24, not
checked in each app.
