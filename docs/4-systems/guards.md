# Guards

**Owns:** deciding which actions the `house-rules` hooks let through, refuse, or ask aj about. The
dispatch itself is described in [hook-engine.md](hook-engine.md); this document owns the policy the
guards apply. Status: built in plugin 2.68.0 under issue #285 (Guards block only unrecoverable
actions): child issues #289 to #293, #286 and #288. #287 (configurable agent name) is not built yet,
so the credit line and branch prefix are still "AJ's agent" and `AjsAgent/`.

## The test

A guard stops an action only when it would lose data with no way back, or change someone else's
work. Inconvenience is not a reason to stop. The approved design is `docs/plans/guards-audit.html`,
and its decisions are logged in `docs/6-decisions/Decisions.md` under "Guards audit: the design aj
approved".

## How it works, in order

1. **Never-blocked list (#289).** This is checked first. These always go through, and no guard, page
   check or prompt timer sees them: a routine commit or push on an agent branch (`AjsAgent/`, or a
   helper's working-copy branch), publishing a `make_page.py` page, and edits to files the agent
   created inside its folder.
2. **Refusals with the safe way named (#291).** Nine destructive actions are refused outright. Each
   refusal names the safe alternative, such as a pull request, a new `AjsAgent/` branch, a
   `_to_delete/` folder or a copy branch. A delete is refused only when it is recursive, or when the
   file has uncommitted changes or was never committed.
3. **Asking aj (#290).** aj is asked only when no safe way exists and the agent cites a source proving
   it: the Bash call's `description` carries `no safe way: <source>` (`_cites_no_safe_way` in
   `hook.py`), and the prompt shows the citation. Each prompt waits on its own timer, and an
   unanswered prompt never causes later refusals.
4. **Enforced workflow checks (#293).** Five checks refuse and name the exact fix: a hand-written page,
   a Claude credit or a `claude/` branch on GitHub, an issue missing its sections, a third helper or a
   helper's own helper, and a whole-file overwrite of a file the agent did not create.
5. **Removed (#292).** The background-work guard and the "Never hide work" rule are gone.

## Invariants

- Every refusal names its fix in the refusal text, and `verify.py` checks that text, not only the
  decision.
- The design-loop lock ([design-loop.md](design-loop.md)) is separate and stays blocking.
