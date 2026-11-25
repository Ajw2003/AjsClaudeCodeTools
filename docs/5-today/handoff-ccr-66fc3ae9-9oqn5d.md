# Handoff: quiet unattended mode

## What the work is for
aj wants unattended mode to make its own decisions, keep working until its goal is met, and show the decisions only on the QA page after everything is built and tested. aj's questions should be kept for choices that change how something looks or what it does.

## Where it stands
Plan stage. Five causes were found by reading the code and are written on `docs/plans/2026-11-25-quiet-unattended-mode.html` (content file beside it). No source file was changed. A page-mode review of the page was started.

## The next step
Wait for aj's approval line "Design approved: quiet unattended mode". Then write the systems doc, create the issues, and build in small steps with `verify.py` after each.

## What is unverified
Everything is read from the code, not run. A live bypass-permission session was not tried, so the claim that bypass mode keeps the source-edit lock is unconfirmed. The 8-block limit on end-of-reply hooks is taken from `docs/4-systems/roadblocks.md`.

## The issue numbers
None yet; the plan has not been approved. Related earlier work: #587 to #591.
