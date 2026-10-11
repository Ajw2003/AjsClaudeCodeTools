# Handoff: agents stop putting polling in Unity `Update` (2026-10-11)

For a fresh session started in this repo (`C:\Users\aj\Desktop\GameDev\AjsClaudeCodeTools`). Every change below was
**approved word for word by aj on 2026-10-11**. Do exactly this; anything beyond it needs aj's say-so first.

Issues: parent #218, children #219 (standard), #220 (hook), #221 (builder and reviewer), #222 (briefs).

## Why

In Ajw2003/PlunderSpell on 2026-10-11 an agent saved the Lair's loot pile from a polling check in `Update`. The poll
read a torn-down pile as empty and wiped the save (PlunderSpell #378). aj called it a habit across sessions. The
root causes found:
1. `csharp-unity-standards.md` and `csharp-unity-detail.md` only say "don't allocate or `Find` in `Update`", which
   treats `Update` as the normal home for logic; the events rule is soft.
2. "Match the style already in the file" lets agents copy polling from existing scripts.
3. The orchestrator's builder brief prescribed "a check every ~2 s"; nothing checks a brief against the project's
   architecture.
4. Builders are never told to read the project's architecture docs before coding.
5. No hook or reviewer flags a new per-frame method.

Evidence of scale: PlunderSpell's audit (PlunderSpell PR #388, `docs/plans/update-audit-2026-10-11.md` there) found
103 per-frame methods or parts, of which 67 should be events, timers or removed.

## How to work here

- Branch: `AjsAgent/no-update-polling`, cut from `origin/main`. Agent-owned: commit and push freely. Pull request into
  `main` with `Refs #218`; never merge it, aj does.
- One `@house-rules:builder` at a time, one per issue (#219, #220, #221, #222). Each brief quotes the text below
  verbatim and names the files. Work in this repo's folder; no worktree isolation and no `cd` (the guard refuses
  commands whose repo it cannot follow).
- Read `CLAUDE.md` and `docs/architecture.md` first. `verify.py` proves the hooks match the docs; a new hook needs its
  `verify.py` cases in the same change.

## 1. The Unity standard (#219)

**`claude-house-rules/plugins/house-rules/rules/standards/csharp-unity-standards.md`**: add this section right after
"## C# style":

```markdown
## Per-frame code is the exception, not the default

- `Update`, `LateUpdate` and `FixedUpdate` are only for work that genuinely changes every frame:
  movement, physics, camera follow, a value that visibly changes every frame. Every new one carries
  `// per-frame: <reason>` on the line above it; a hook refuses one without it.
- Never use a per-frame method to notice that something changed (a count, a state, a flag, an object
  appearing) or to save. The thing that changes publishes an event through the project's event bus,
  and only the code that needs to know listens.
- Time-based work (later, every N seconds, a fade that runs only sometimes) is a coroutine or a
  scheduled call started when it begins, never a timer counted in `Update`.
- Input comes through the project's input actions as callbacks (`performed`, `canceled`), never
  `Keyboard.current` / `Mouse.current` reads and never a hard-coded key.
- Several booleans that describe one thing (dragging, in hand, frozen) are one state: an enum or a
  small state class, so they cannot contradict each other.
- Follow the project's own architecture (its systems docs and decisions; e.g. MVC with views fed by
  events, singletons, factories, SOLID). Read them before writing, and name in your report which
  event or pattern carries each change.
- "Match the existing file style" never extends to these. An existing poll is a bug to report, not a
  pattern to copy.
```

**`rules/standards/csharp-unity-detail.md`**, "## Performance": replace the first bullet (beginning "Avoid
allocations in per-frame code") with:

```markdown
- Per-frame code is the exception (see the standard's "Per-frame code is the exception"). Where it is
  genuinely needed, avoid allocations in it: no `new` on lists/arrays, no LINQ, no string
  concatenation in a hot loop. Reuse buffers instead. A per-frame method that returns early most
  frames is a sign it should be an event handler or a coroutine instead.
```

**`rules/standards/coding-philosophy.md`**: replace lines 63-64 (the "Match the style already present in a file"
bullet) with:

```markdown
- Match the style already present in a file over the rules in this doc, if they conflict —
  consistency within a file beats a global rule. The exception: never copy a pattern a standard
  names as a defect (polling for change, a poll used to save, per-frame timers). Report it instead.
- Don't poll for change. Whatever changes announces it (an event, a callback, an observable), and
  only what needs to know listens. This holds in every language: no `setInterval` checking a value,
  no loop re-reading state to spot a difference.
```

**`rules/house-rules.md`**, line 129: replace "Standards injected at session start bind; existing file style wins."
with:

```
Standards injected at session start bind; existing file style wins, except where a standard names the existing pattern as a defect.
```

## 2. The hook (#220)

**`scripts/hook.py`**: a new handler `event_perframe`, registered in `hooks/hooks.json` under `PreToolUse` with
matcher `Write|Edit`.
- Looks only at `.cs` files.
- Counts per-frame declarations (`void Update(`, `void LateUpdate(`, `void FixedUpdate(`, `InvokeRepeating(`,
  `EditorApplication.update +=`) in what the write would leave versus what is there now: for an Edit, `new_string`
  against `old_string`; for a Write, the new content against the file on disk.
- If the count goes up and a new declaration lacks `// per-frame:` on the line directly above it, **refuse** the
  write with:

```
house-rules: this adds a per-frame method (<name>) to <file> without a reason.
Per-frame code is only for work that genuinely changes every frame (movement, physics, camera,
a visible animation). Changes go through the project's events, time through coroutines.
If this one really must run every frame, put `// per-frame: <reason>` on the line above it and write again.
```

- Edits that only change the body of an existing per-frame method are not refused.
- `HOUSE_RULES_PERFRAME=off` turns it off, like the plugin's other switches.

**`scripts/verify.py`**: four cases: a new `Update` without the comment is refused; the same with the comment passes;
an edit inside an existing `Update` passes; a non-`.cs` file is ignored.

**`docs/architecture.md`**: a row for `perframe` in the hook-by-hook table.

## 3. Builder and reviewer agents (#221)

**`agents/builder.md`**: add after the bullet "Do the steps as written, in order...":

```markdown
- Before writing code, read the project's architecture: its systems docs and decisions (in a repo
  with the house-rules docs tiers, `docs/4-systems/` and `docs/6-decisions/Decisions.md`). Use the
  events and patterns already there.
- Never add polling, a per-frame check for a change, or a timer counted in `Update`; if the steps
  seem to need one, stop and ask. Your report names the event or pattern that carries each change.
```

**`agents/reviewer.md`**: add the bullet:

```markdown
- Always check: new per-frame methods without a `// per-frame:` reason, polling for change or saving
  from a poll, timers counted per frame, direct device input reads, several booleans standing in for
  one state, and views reaching into models instead of listening for events.
```

## 4. The orchestrator's briefs (#222)

**`rules/house-rules.md`**, section "## Once the approach is decided, delegate the execution": add at the end of
that paragraph:

```
A brief names the event or pattern that carries each change, checked against the project's architecture docs, and never prescribes polling or a timed check.
```

**`rules/detail/delegate-execution.md`**: a short paragraph, "What a brief must say", giving the why, with the
PlunderSpell #378 example (the brief said "a check every ~2 s"; the result wiped a save).

## 5. Housekeeping

- Bump the plugin version in its `plugin.json` (minor: a new hook).
- Update this repo's `docs/5-today/Today.md` and `docs/3-state/ProjectState.md`; add a dated entry to
  `docs/6-decisions/Decisions.md`.
- Run `python claude-house-rules/plugins/house-rules/scripts/verify.py` and `python tools/verify_tools.py`. Both must
  pass; quote their result lines in the pull request.
- Commit on `AjsAgent/no-update-polling`, push, and open the pull request into `main` with `Refs #218`. Never
  Closes/Fixes; aj closes issues after testing.

## Done when

All four children's changes are on the branch, both verify scripts pass, the pull request is open, and the final
reply tells aj in plain words what changes once the new plugin version is installed.
