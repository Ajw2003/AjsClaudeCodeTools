---
description: Scan this repo's backlog docs and session ledgers for issue-worthy items, draft scoped GitHub issues, and (only after explicit go-ahead) create the ones named
---

The user asked to run the forge explicitly — either because `suggest` flagged a recent edit or
ledger, or on demand. This is the same scan the `suggest` hook (`PostToolUse`) points at; here
it's on request.

Read `rules/issue-forge.md` in this plugin (loaded into context at session start by the `inject`
hook — reread the file directly if it's no longer visible) before doing anything else. Its hard
rule governs this command: **`--create` is never run without the user first seeing the drafted
list and naming which ones to create, in chat.**

1. **Run Phase A:** `python scripts/forge.py --dry-run --repo <owner/repo>` (default repo is the
   current checkout's `origin` remote; pass `--repo` to override). This only reads from GitHub
   (`gh issue list --search`, for dedup) — no confirmation is needed for this step.
2. **Show the user the full numbered list** Phase A prints — title, proposed labels, and drafted
   body — for every surviving candidate. Do not summarize or truncate a body down to a title only;
   the user is reviewing what would actually be posted.
3. **Ask which candidates (if any) to create**, by number or slug. Do not proceed on a general
   "yes" that does not name which ones — if the answer is ambiguous, ask again naming the specific
   slugs you understood were meant.
4. **Only then run Phase B:** `python scripts/forge.py --create <slug1,slug2,...> --repo <owner/repo>`
   with exactly the slugs the user named — never all surviving candidates, never a superset.
5. **Report back** the created issue URLs (Phase B prints them) so the user can verify what was
   actually posted matches what they approved.

If Phase A finds nothing (every candidate already has a matching issue, or no source files have
open entries), say so plainly rather than running Phase B on an empty or stale list.
