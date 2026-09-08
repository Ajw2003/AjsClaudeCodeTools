# house-style — why it exists and how it is built

`CLAUDE.md` is auto-loaded every session and re-paid on every subagent spawn, so it stays short.
This is the long form: the reasoning behind the constraints it states, the sources the catalogue
draws on and what they are licensed under, and the decisions that are easy to reverse by accident
later.

## The problem it was built for

Before this plugin the repo had three visual artefacts and three unrelated colour systems:

| File | Look | Fonts |
|---|---|---|
| `plugins/house-rules/templates/step-card.html` | warm paper, `--accent:#2f6f4f` | system stack only |
| `artifact-test.html` | green-tinted, different tokens | IBM Plex from Google Fonts |
| `docs/architecture-review-2026-09-07.html` | Tailwind CDN, `bg-stone-50` | `font-serif` / `font-mono` |

None of them was wrong on its own. Together they said the repo had no look — each page was
designed by whichever model happened to be running that turn, and the author's taste entered the
result only when he happened to be watching. That is the authorship problem this plugin is for.
It is not a stylesheet; it is a place for a decision to live so that it outlives the session that
made it.

## Two tiers, and why the shipped one is the floor

**Three themes ship with the plugin.** They are hand-authored, they work with the network cable
out, and they are what `verify_style.py` asserts against.

**A live catalogue expands on top of them.** `style.py refresh` and `style.py gallery` fetch font
and colour data at command time. Every fetch falls through cache to the shipped themes and never
raises.

The tiering is the point. A catalogue-only design would mean a machine with no network has no
themes at all, and a test suite that needed the internet — which nothing else in this repo does.
A shipped-only design would mean the catalogue can never grow without a commit. The floor is
committed; the ceiling is fetched.

### Why nothing is composed automatically from fetched data

`catalogue()` returns fetched font families as *ingredients*, next to the shipped themes — it does
not assemble them into themes. A generator that paired a random display face with a random ramp
would produce plausible near-misses, and a picker full of near-misses is worse than a picker with
three considered options. A theme is a set of decisions. Fetching cannot make them.

## The CSP, which shapes more of this than anything else

A published artifact runs under a Content Security Policy that permits:

- scripts from `cdnjs.cloudflare.com`, `cdn.jsdelivr.net/npm/`, `cdn.tailwindcss.com`, `code.jquery.com`
- stylesheets from `fonts.googleapis.com`, with font files from `fonts.gstatic.com`
- **no `fetch`/XHR to any host at all**

Three consequences run through the whole design:

1. **The gallery cannot call an API.** `style.py` fetches in Python at command time and inlines
   the result into the page it generates. A page that tried to fetch would show nothing, with no
   error in the console the author would see.
2. **Google Fonts is the only usable webfont source.** Fontsource, Bunny and self-hosting are all
   blocked. Fontsource is still used, as the keyless *metadata* catalogue; delivery is always
   `fonts.googleapis.com/css2`. `validate()` enforces this, so a theme cannot regress into a font
   that silently never loads.
3. **Every theme needs a webfont-free stack.** `step-card.html` is opened off disk on a machine
   mid-install that may have no network, and `verify.py` fails if an external reference appears
   in it. `systemStack` is what those surfaces get, and it is chosen to keep the theme's
   character — a serif theme falls back to a serif — rather than to be a neutral default.

## Sources and licences

All keyless. No font binary is ever downloaded or redistributed by this plugin — only family
names and stylesheet URLs.

| What | Endpoint | Licence |
|---|---|---|
| Font catalogue | `https://api.fontsource.org/v1/fonts` | Fontsource MIT; the fonts themselves OFL / Apache / UFL |
| Font delivery | `https://fonts.googleapis.com/css2?family=…` | per-font, OFL or Apache |
| UI colour ramps | `raw.githubusercontent.com/yeun/open-color/master/open-color.json` | MIT |
| Named schemes | `github.com/tinted-theming/schemes` (base16/base24 YAML) | MIT |

Every shipped theme carries a `sources[]` array recording the same, per font. Type scale, shape
and voice are ours and are recorded as `licence: "in-repo"` — nothing free publishes those as
machine-readable data, so they were authored, and the file says so rather than implying they were
found somewhere.

> Note: in some sandboxed environments an egress proxy blocks `api.fontsource.org` (it returns
> `403 Forbidden` on the tunnel). That is the fallback path working as designed — `refresh`
> reports the source as `unavailable`, exits 0, and the three shipped themes are unaffected.

## The prose voice is not decoration

`voice.proseTone` is injected verbatim into context at `SessionStart` and is the half of a theme
that is not CSS. Without it, choosing a theme would repaint the same document three ways, which
is a skin, not authorship. With it, Ledger produces a terser document than Quarry, not merely a
bluer one.

This is also the part most likely to be quietly dropped in a future edit, because it is the only
field whose effect cannot be seen in a screenshot. `verify_style.py` asserts it is non-empty, that
no two themes share one, and that the string actually reaches the injected context.

## The variety rule

`verify_style.py` asserts that no two shipped themes share an accent, a display font, a body
font, a radius, a scale ratio, a measure or a prose tone.

The failure it guards against is slow and looks reasonable at every step: themes get edited one
at a time, each change is defensible on its own, and three distinct looks converge into three
tints of whichever was touched last. The check cannot prove taste. It can prove nobody made the
choice meaningless, which is the part that actually decays.

## Failure modes, per hook

Each handler fails the way its event permits, which is the same discipline `hook.py` is built on:

- **`style`** (SessionStart) fails **loud, not closed** — there is nothing to block at session
  start, but a session that silently has no style is worse than a noisy one, so it emits a
  `systemMessage` and exits 0.
- **`styleguard`** (PreToolUse) fails **closed** — exit 2. This is the last moment before a page
  becomes public. It uses the same three-tier ladder as `guard`: payload parses and names a file
  → judge that file; payload does not parse but a `file_path` is extractable → judge that,
  exactly as it behaved before the parse existed; neither → block. The middle tier is what keeps
  a payload whose shape shifts slightly from being either waved through or blocked outright.
- **`styled`** (PostToolUse) **never obstructs** — the write already happened.

### Why `styleguard` is silent on a compliant page

A hook that fires on a *correct* publish cannot end quietly: the turn continues, `suppressOutput`
has no effect, and the only thing left to say is that nothing needed saying. That is the house
rule against announcing your own compliance, broken by the hook meant to enforce it. So a page
carrying a known marker passes in silence.

The cost is deliberate and worth stating: a page stamped with a marker it did not earn — the
comment pasted in without the tokens — passes unchecked. That is traded for removing a prompt
that would otherwise appear on every correct publish. It is the same trade the `handover` hook
already makes, for the same reason.

## No hook keeps state

The active theme is resolved fresh on every call: `./.claude/style.json`, then
`~/.claude/house-style/active.json`, then the fallback. Nothing is cached between invocations and
no hook writes anything. A pin naming a theme that no longer exists falls through to the fallback
rather than failing, because a stale pin is a normal consequence of renaming a theme and should
not take a session down.

The catalogue cache under `~/.claude/house-style/cache/` is the one thing written to disk, it is
machine-local and gitignored, and nothing depends on it existing.

## Editing this plugin

- **A new theme** is a new file in `themes/`, and nothing else. Run `style.py validate` and then
  `verify_style.py` — the variety rule will reject a theme too close to an existing one, which is
  the check doing its job, not an obstacle to route around.
- **A new colour token** means changing `COLOUR_TOKENS` in `style.py`, `themes/schema.md`, every
  theme file, and `templates/tokens.css` together. `verify_style.py` checks the schema lists every
  token the code requires, so a partial change fails rather than half-applying.
- **Changing the marker shape** means changing `MARKER_PREFIX` and the three docs that state it
  (`tokens.css`, `commands/house-style.md`, `themes/schema.md`). There is a drift check for each.
- **Adding a hook event** means a row in the `CLAUDE.md` house-style table in the same change.
  It is checked in both directions, so a hook without a row and a row without a hook both fail.
