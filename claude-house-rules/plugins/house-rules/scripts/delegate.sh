#!/bin/sh
# delegate.sh — PostToolUse hook, matcher "ExitPlanMode".
#
# Rule: once the approach is decided, delegate the implementation to @house-rules:executor
# rather than executing on the planning model. The `opusplan` setting (tools/install.ps1)
# covers this for CLI/IDE sessions that cross the plan-mode boundary, but three things defeat
# it: the Desktop Code tab's model dropdown outranks the settings file and does not even offer
# opusplan as a choice, cloud sessions never read a device's local settings.json at all, and
# Auto/Accept-edits sessions never enter plan mode in the first place so the boundary the
# setting switches on never occurs. Agent frontmatter is honoured wherever the plugin is
# installed, so routing through the subagent is the one mechanism that actually reaches all of
# those surfaces.
#
# NEEDS NO FIELD FROM THE PAYLOAD. The hooks.json matcher already selects ExitPlanMode, so
# there is nothing to extract here and therefore nothing to fall back on if extraction fails.
# That means no grep dependency and so no offline path — this is a single printf of a
# hardcoded string, exactly like scope.sh, for exactly the same reason: a second copy of the
# wording is worth it in exchange for zero dependencies. verify.sh pins these phrases against
# rules/house-rules.md so the copies cannot drift apart unnoticed.
#
# IT NEVER PROMPTS THE USER. PostToolUse cannot block anyway (the plan was already exited by
# the time this fires). The nudge goes to Claude; the user sees nothing. Always exits 0.
#
# STATELESS. Nothing under $TEMP, nothing carried between invocations.

set -u

NOTE='House rules, model split: the plan is settled. Delegate the implementation to @house-rules:executor so it runs on Sonnet instead of re-deliberating here on the planning model - unless this is a one-liner where delegating costs more than it saves. This is the mechanism on every surface, including the Desktop Code tab and Auto/Accept-edits sessions, none of which get the opusplan switch. This is a reminder to you; the user was not prompted and does not need to do anything.'

printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"%s"}}' "$NOTE"

exit 0
