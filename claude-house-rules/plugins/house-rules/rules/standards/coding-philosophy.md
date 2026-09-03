# Coding Philosophy (Global)

> Scope: applies to every project, every language. Ecosystem-specific rules live in
> `csharp-unity-standards.md` and `web-js-ts-node-standards.md`. Project-specific facts
> (build commands, architecture, folder layout) live in that project's own `CLAUDE.md`.

## Core principles

- **Clarity over cleverness.** If a teammate (or future me, or Claude) needs a comment to
  parse a one-liner, it's not actually clean — rewrite it plainly instead.
- **Explicit over implicit.** Prefer naming things, passing values explicitly, and avoiding
  hidden state/side effects over "magic" that saves a few keystrokes.
- **Small, reversible changes.** Prefer a sequence of small diffs over one large one. Easier
  to review, easier to revert, easier for an AI assistant to reason about.
- **Delete before you add.** Before introducing a new abstraction, dependency, or file, check
  whether an existing one already does the job.

## Naming

- Names describe *what*, not *how* (`GetActiveUsers()` not `LoopThroughUsersAndFilter()`).
- Booleans read as a yes/no question: `isReady`, `hasPermission`, `canRetry`.
- No abbreviations unless they're domain-standard (`id`, `url`, `http` are fine; `usrCfg` is not).
- Avoid noise words: `data`, `info`, `manager`, `helper` in a name are a signal to name the
  actual responsibility instead.

## Comments & documentation

- Comment *why*, not *what* — the code already says what it does.
- A comment that just restates the line above it should be deleted.
- Public-facing functions/classes get a short doc comment describing intent, inputs that
  aren't obvious, and any gotchas (e.g. "must be called after Init()").
- Don't leave commented-out code in commits. Delete it — git remembers it if it's needed.

## Error handling

- Fail loudly during development (throw/assert), fail gracefully in production paths a user
  can hit.
- Never swallow an exception silently. At minimum, log it with enough context to debug later.
- Validate at boundaries (user input, network responses, file reads) — trust internal code
  once past that boundary.

## Testing

- Write a test when: fixing a bug (regression test first), writing logic with more than one
  branch, or writing something that's expensive to manually re-verify.
- Skip tests for: throwaway prototypes, one-off scripts, pure UI layout.
- A failing test should tell you *what* broke without needing to open a debugger.

## Git & commits

- Commit message format: `<type>: <short summary>` — types: `feat`, `fix`, `refactor`,
  `chore`, `docs`, `test`. Example: `fix: prevent null ref when inventory is empty`.
- One logical change per commit. If the message needs "and," it's probably two commits.
- Write the commit body when the *why* isn't obvious from the diff — not a restatement of it.

## Working with Claude Code specifically

- Ask before: adding a new dependency, deleting files, large refactors touching >3 files, or
  changing a public API/signature.
- Don't ask before: fixing an obvious bug in the file already being edited, formatting,
  writing tests for code just written.
- Prefer proposing a plan for anything non-trivial before writing code.
- Match the style already present in a file over the rules in this doc, if they conflict —
  consistency within a file beats a global rule.

## Quick review checklist

- [ ] Would this make sense to me in 6 months with no other context?
- [ ] Does a name, comment, or test lie about what the code actually does?
- [ ] Is there dead code, debug logging, or a TODO that should be resolved first?
- [ ] Is this the smallest change that solves the actual problem?
