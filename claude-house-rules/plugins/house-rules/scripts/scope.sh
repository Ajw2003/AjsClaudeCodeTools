#!/bin/sh
# scope.sh — UserPromptSubmit hook.
#
# Puts a short standing reminder in front of every prompt: the environment is fixed, the
# request is the scope, deliver something runnable, artifacts live in the project. The full
# rules go in once at SessionStart; this is the part that has to stay true 200 messages later,
# which is exactly when the SessionStart copy has faded.
#
# DEPENDENCIES: NONE. Not sh builtins-plus-grep — none at all. One printf of a fixed string.
# It reads no file, spawns nothing, and tests nothing, so there is no failure path to handle.
#
# That is not fussiness. On UserPromptSubmit a non-zero exit ERASES THE USER'S PROMPT. A hook
# on this event must not be able to fail, so this one is built with nothing in it that can.
# It always exits 0.
#
# The text below is hardcoded rather than read from rules/house-rules.md, which would make it
# another copy that can drift. verify.sh checks that every key phrase here still appears in
# the rules file, so drift fails a test instead of going unnoticed.

REMINDER='Standing house rules (full text was injected at session start):\n- Match response depth to the task - do not reason at length about something simple.\n- Target is Windows 11, Git Bash, PowerShell 5.1. Build for that only - no portability work unless asked.\n- Build only what was asked. Where it is ambiguous, ask instead of assuming.\n- Deliver a whole workflow: exact commands to run, no manual config editing, no step the user has to do by hand.\n- Artifacts go in the project directory as real files, not in chat and not in a temp directory.\n- Never hand over a command you have not run where the user will run it: PowerShell 5.1, where sh is not on PATH. Untested instructions are not instructions.'

printf '{"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":"%s"}}' "$REMINDER"

exit 0
