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

These steps come from Claude Code's cloud environments page
(https://code.claude.com/docs/en/cloud-environments.md, "Set environment variables"), checked 2026-10-25. The
page gives them for the browser and the desktop app. The mobile app's page has no steps for environment
variables, so on a phone, open claude.ai/code in the phone's web browser instead of the app.

1. Go to claude.ai/code in a browser and start a new session.
2. Under the message box, select the first control to open the environment selector.
3. Under **Cloud**, find the environment, select its settings icon, then select **Environment variables**.
4. Paste these two lines, one per line:

   ```
   HOUSE_RULES_AGENT_NAME=ajw2003sAgent
   HOUSE_RULES_OWNED_BRANCHES=AjsAgent/,claude/
   ```

5. Select **Save changes**. The next new session picks the values up; a session already open does not.
6. To check, start a new session and ask the agent to run
   `python3 <plugin>/scripts/settings.py show`. It should list both values as coming from the environment.

In a session that is already running, the same settings open from the caret after the session title, then
**Edit cloud environment**.

## Repeating it across Claude accounts

The values come from the GitHub account the agent works as, not from the Claude account. So every Claude
account that works on Ajw2003's repos pastes the same two lines, unchanged:

```
HOUSE_RULES_AGENT_NAME=ajw2003sAgent
HOUSE_RULES_OWNED_BRANCHES=AjsAgent/,claude/
```

Each Claude account has its own cloud environments, so repeat steps 1 to 5 in each one. A tick list:

| Claude account | Environment | Done |
|---|---|---|
| | | |

Not yet tested: step 6's command exists only once 2.74.0 ships, and the docs don't say whether the Claude
mobile app itself can edit environment variables, so that is not confirmed either way.
