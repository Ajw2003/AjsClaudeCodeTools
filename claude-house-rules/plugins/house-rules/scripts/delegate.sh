#!/bin/sh
# delegate.sh — PostToolUse hook for ExitPlanMode.
#
# Rule: once the approach is decided, the implementation is delegated to @house-rules:executor
# rather than run on the planning model. This fires at the moment that becomes true — the plan
# has just been approved — and says so in context.
#
# WHY THIS EXISTS AT ALL. The Opus-plans/Sonnet-executes split used to rest entirely on the
# `"model": "opusplan"` setting install.ps1 writes into ~/.claude/settings.json. That setting is
# read by the CLI and the IDE extensions. It is NOT what decides the model in the desktop app's
# Code tab: there the model comes from the picker next to the send button, which is a
# session-level selection and outranks the `model` field in any settings file — the desktop docs
# map both `--model` and ANTHROPIC_MODEL to that dropdown. `opusplan` is not even offered in it,
# being an alias rather than a model. Cloud sessions are worse still: they run on managed VMs
# that never receive a settings file deployed to the device, so install.ps1 writes to a path
# that does not exist there. On all three surfaces the split silently did not happen.
#
# What DOES work everywhere is the subagent: agent frontmatter travels with the plugin, so
# @house-rules:executor runs on Sonnet wherever the plugin is installed. The subagent was always
# in the repo; nothing ever asked for it. This hook is the ask.
#
# DEPENDENCIES: NONE. Not even grep. The matcher in hooks.json already selects the event, so
# there is no field to extract and no payload to read — one printf of a fixed string, the same
# construction as scope.sh. A hook with no dependencies has no offline path to report.
#
# IT NEVER PROMPTS THE USER. PostToolUse cannot block, and this is a note to Claude about how
# to run the work, not a decision for the user. Always exits 0.
#
# STATELESS. Nothing under $TEMP. It fires once per plan approval because that is how often the
# event fires, not because anything is remembered.
#
# The text is hardcoded rather than read from rules/house-rules.md, for the reason scope.sh's is:
# a file read is a failure path. verify.sh pins the phrases against the rules file instead, so
# drift fails a test rather than going unnoticed.

NOTE='House rules, execution model: the plan is settled, so the implementation is delegated work now. Hand it to the @house-rules:executor subagent (Task tool, subagent_type house-rules:executor) with the plan steps written out, rather than implementing it here. That agent is pinned to Sonnet at low effort, which is the whole point: deliberation is done, and re-deliberating it on the planning model costs the user for nothing. Do not re-plan inside the delegation - give it the decided steps. The exception is genuinely trivial work, where handing over the context costs more than doing it; say so in one line and just do it. This is a reminder to you; the user was not prompted and does not need to do anything.'

printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"%s"}}' "$NOTE"

exit 0
