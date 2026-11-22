#!/bin/sh
# Start Claude Code for a run with nobody present (overnight).
#   HOUSE_RULES_UNATTENDED=on  house-rules plugin: every optional rule is off except autosave, guard
#                              prompts are refused instead of asked (and listed under "Waiting on you"),
#                              and AskUserQuestion / ExitPlanMode are denied so the agent decides itself.
#   ART_PIPELINE=unattended    art-pipeline plugin: the same idea, nothing waits on a person.
# --dangerously-skip-permissions means NOTHING asks before it runs. Use a throwaway branch or clone.
set -eu
HOUSE_RULES_UNATTENDED=on
ART_PIPELINE=unattended
export HOUSE_RULES_UNATTENDED ART_PIPELINE
exec claude --dangerously-skip-permissions "$@"
