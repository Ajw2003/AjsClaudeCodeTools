# Handoff: clear-roadblocks proposal

## What the work is for
aj wants a house rule that stops the agent claiming a roadblock (a missing tool, the wrong machine) without checking, and makes it install tools and take other routes itself, especially in bypass permission mode.

## Where it stands
Design stage. A proposal page, `docs/plans/2026-11-22-clear-roadblocks.html`, offers three enforcement options (A rule only, B rule plus a Stop check, C B plus a bypass-mode line) and one ownership question. aj chose option C: a Stop check that blocks a roadblock claim twice, then lets the reply through with a visible warning line. aj has not yet sent the approval line or picked on what stays aj's. No rule text or hook code is written.

## The next step
Wait for aj's reply, "Design approved: clear roadblocks 1C 2A". Then write a build plan page, and file issues if it has more than three steps.

## What is unverified
How the existing Stop evidence check matches "can't" phrases was not read in hook.py, so option C is untested against it. The page text went through the editor helper.

## Issue numbers
None filed yet.
