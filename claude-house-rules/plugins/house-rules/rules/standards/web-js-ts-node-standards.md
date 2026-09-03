# Web / JS / TS / Node Standards

> Scope: HTML/CSS/JS/TS/Node side projects and "vibe coding." Assumes `coding-philosophy.md`
> also applies. Intentionally lighter-weight than the Unity doc — these are mostly small,
> fast-moving projects, not production codebases.

## Formatting & linting

- **Prettier** for formatting, default config unless a project has a strong reason otherwise
  (don't bikeshed formatting rules per project).
- **ESLint** with a standard base config (`eslint:recommended` + the TypeScript equivalent
  when using TS). Fix or explicitly disable a rule inline with a reason — don't leave lint
  warnings unaddressed and unexplained.
- Let the tools decide semicolons/quotes/etc. — not worth a manual convention once Prettier
  is running.

## TypeScript

- Default to TS over plain JS for anything you'll touch again in a week; plain JS is fine for
  true one-off scripts.
- Turn on `strict: true` in `tsconfig.json` for new projects. Avoid `any` — use `unknown` and
  narrow it, or define a minimal interface, instead.
- Prefer `interface` for object shapes that might be extended; `type` for unions, tuples, and
  everything else.
- Let TypeScript infer return types for simple functions; annotate explicitly once a function
  has more than one exit path or the inferred type would be misleading.

## Naming & style

- `camelCase` for variables/functions, `PascalCase` for classes/types/interfaces/React
  components, `SCREAMING_SNAKE_CASE` for true constants (config values, env var names).
- File names: `kebab-case.ts` for modules/utilities, `PascalCase.tsx` for React components.
- Prefer named exports over default exports — easier to refactor and grep for.

## Project structure (small/prototype projects)

```
src/
  index.ts / index.html
  components/        # if UI-framework based
  lib/                # shared utilities
  server/             # if Node backend
.env.example          # committed; real .env is gitignored
```

- Don't over-architect a prototype — a flat `src/` with a handful of files is fine until the
  project actually grows past it.
- `.env` files are never committed. Commit an `.env.example` with the variable names and
  placeholder values.

## Async & error handling

- `async`/`await` over `.then()` chains or raw callbacks.
- Every `await` that can reject gets a `try`/`catch` (or a caller that has one) — no
  unhandled promise rejections.
- On a Node server: centralize error handling in one middleware/handler rather than
  try/catch-ing identically in every route.

## Node specifics

- Read config from environment variables (via `.env` + a loader like `dotenv`), never
  hardcoded secrets or URLs.
- Pin dependency versions (commit the lockfile) — vibe-coded projects are exactly the ones
  that silently break from an unpinned transitive update.

## "Vibe coding" ground rules

Since these projects move fast and standards are intentionally lighter:

- If you skip a convention above for speed, leave a one-line comment saying so (e.g.
  `// TODO: no error handling yet, prototyping the happy path`) so it's an intentional
  shortcut, not a forgotten one.
- Before a prototype becomes a "real" project (shared with others, deployed, or revisited
  after a long gap), do one pass applying the rules above properly.
