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

## The builder

Three themes shipped and a picker that chose between them left one gap: authoring a fourth still
meant hand-writing 22 hex values across two schemes, three font objects with their own fallback
stacks, and a voice block — then running `validate` and reading the failures back. That is bad
enough that in practice nobody adds a theme, which quietly turns a three-theme system into a
fixed one. A format only a script can comfortably write moves authorship straight back out of
the author's hands, which is the thing this plugin exists to prevent.

`style.py builder` generates a page; publishing it with `capabilities: {db:{}}` gives a tool that
opens in a working state — seeded, specimen already rendering — rather than an empty form.

### Two colours, not twenty-two

The colour step asks for a ground and an accent. Everything else is derived, and contrast is a
property of the derivation rather than a warning bolted on after it.

**The ground is a tint, not the background.** It supplies hue and chroma; the scheme supplies
lightness — light lands near `#f5f5f5`, dark near `#0f0f0f`, both carrying the tint.

This is not a stylistic choice, it is a correctness one. Used literally, a ground anywhere
between roughly 12% and 75% lightness **cannot support a readable `ink` at all**:

```
#f5f5f5 → 19.26 ok        #b3b3b3 → 10.02 impossible      #383838 → 11.73 impossible
#d9d9d9 → 14.88 ok        #8c8c8c →  6.25 impossible      #1f1f1f → 16.48 ok
                          #666666 →  5.74 impossible
```

`#787878` tops out at 4.76:1 against pure black. A "light" scheme built on one was neither light
nor readable. Deriving the page colour from the ground guarantees headroom in both directions
while keeping the chosen colour visible in every neutral.

**`solveOn` returns `null` when a target is unreachable.** It binary-searches lightness at a
fixed hue until the WCAG ratio against the ground is met; when no such lightness exists it says
so. An earlier version returned the value it was initialised with — white or black — which is how
a mid-grey ground silently turned `ink`, `muted` *and the user's chosen accent* into `#ffffff`.
Callers handle `null` explicitly; `solveBest` walks a list of targets best-first so a tight ground
degrades to a lower ratio rather than to a wrong colour.

**`ink` and `muted` are solved separately and must stay distinct.** When both fell back to white
the palette had no hierarchy left and nothing noticed. There is now a minimum contrast required
*between* them.

**`fitAccent` handles what `solveOn` cannot.** An accent has two jobs that pull against each
other — it must read on the ground, and text must read *on it*. For a mid-tone accent there is no
lightness at a fixed hue that clears 4.5 against it, because the accent sits in the middle where
neither white nor black is far enough away. So it picks whichever of white and a hue-tinted
near-black contrasts more, and walks the accent's own lightness until that clears — stopping
before the accent stops reading on the ground, because the ground matters more. It reports back
whether it moved the colour, and the page says so: silently changing someone's accent is what
made the tool untrustworthy.

**The dark scheme is not an inversion.** The ground becomes a very dark form of its own hue and
the accent is *lightened* until it clears on it. An accent that works on paper is nearly always
too dark on black; that is the single most common way a hand-built dark palette fails.

**The warn tokens are semantic.** They lean toward the ground's hue — along the short way round
the wheel, by at most about 7°, then clamped to the amber band — so they belong to the theme
without becoming a second accent. An unclamped one-fifth nudge toward a blue ground reached hue
0.19, chartreuse, which reads as a highlighter pen rather than a warning. The page states this
explicitly, because "I picked grey and teal, where did the orange come from?" is a fair question
that the interface previously did not answer.

An accent that already passes is left alone, and the suite asserts it — otherwise "pick an
accent" would quietly mean "suggest an accent".

The derivation lives only in the page. A second implementation in Python would double the drift
surface to buy a headless flag nobody asked for.

### How the page's validation stays honest

The page necessarily re-checks in JS what `validate()` checks in Python. The mitigation is that
it does not re-*state* it: `constraints()` returns the token names, roles, enum values and
patterns as data, `cmd_builder` inlines that JSON, and `verify_style.py` asserts the export still
equals the module constants. A token added to `COLOUR_TOKENS` therefore reaches the builder, or
the suite fails.

The page's checking is a convenience. `validate()` stays the authority and runs again at install,
so the worst case is a theme that looks fine in the page and is refused at install with a real
message — never a bad theme on disk.

### `install` is the only verb that writes a theme

```bash
python claude-house-rules/plugins/house-style/scripts/style.py install -   # JSON on stdin
```

It exists rather than having the caller write the file because it is where the gate belongs:
validate, refuse to clobber, check the variety rule, and only then write. A rejected theme
produces a message naming what is wrong instead of a file that fails the suite ten minutes later.
`--force` exists for a collision the author has decided is deliberate; it is not a way past a
result you did not like.

### The font floor

`cmd_builder` inlines the fetched catalogue, but a builder whose picker is empty is not a
builder, and `api.fontsource.org` is unreachable from some environments. `FALLBACK_FAMILIES` is
roughly 60 families with their categories — no metrics, no binaries — used when the fetch and the
cache both miss. Same shipped-floor / fetched-ceiling shape as the themes.

Every family in it must exist **on Google Fonts**, not merely exist. A face that is only on
Fontshare or a foundry's own site is blocked by the CSP and fails silently — the page renders in
a fallback and nothing says why. Check `fonts.google.com/specimen/<Name>` before adding one; the
suite runs offline and cannot.

### Testing the deriver

`verify_style.py` extracts the deriver from the **generated** page and runs it under node,
sweeping grounds from 2% to 98% lightness across seven hues and four saturations against six
accents — around 47,000 contrast assertions over 3,360 ground/accent pairs, both schemes. It also
asserts that `solveOn` returns `null` for an unreachable target, that `ink` and `muted` never
collapse, that the accent's hue survives, that an already-passing accent is preserved, and that
the warn hue stays in the amber band. Where node is missing the check skips loudly rather than
quietly not existing.

**The sweep replaced a list of hand-picked cases, and that is the lesson worth keeping.** The old
list had a "mid-tone" case at `#c9c4b8` — 12.8:1, scraping past the boundary — so it passed while
the entire unusable band behind it went untested. The cases had been chosen to be *plausible*
rather than *hostile*. Running the same sweep against the old deriver produces 4,924 failures;
against the current one, none. A test that only covers the inputs you imagined is a test that
agrees with you.

What it still cannot check is whether the result is *good*. Contrast is necessary and not
sufficient, and a palette can clear every ratio and remain ugly. That is judged by eye, in the
specimen, which is why the specimen is not optional.

### What the page shows about its own working

The colour step displays the resulting light and dark page colours and the accent as it will
actually appear on each, and every token in the expanded grid carries a line saying where it came
from — "your ground, lightened", "yours, unchanged", "semantic amber, not your accent". A tool
that derives has to show its working, or it is indistinguishable from one that ignores you.

## Where the published artefacts live

`docs/artifacts/` holds the generated gallery and builder pages, plus a `manifest.json` recording
each live URL, the command that produced it and the capabilities it was published with. Its
README has the regeneration commands.

They are committed rather than left in a scratch directory because an artefact that exists only
in the session that made it is not an artefact — it is a side effect. An earlier `.gitignore`
line here (`house-style-gallery.html`) quietly defeated exactly the rule the `artifact` hook
exists to enforce; it has been removed, and `style.py gallery`/`builder` now default to writing
into `docs/artifacts/` when that directory exists.

Committed build output rots, so `verify_style.py` holds it to the themes actually on disk: every
page there must name every theme in `themes/`, and no theme that has been deleted. Adding a theme
without regenerating fails the suite, and the failure prints the command to fix it. The guard is
structural rather than byte-exact because both pages embed a generation timestamp and the live
font catalogue — regenerating never reproduces the same bytes, so a byte comparison would fail
for reasons that mean nothing.

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
- **Adding a constraint the builder must respect** means adding it to `constraints()` as data and
  reading it in the page, never typing it into the JS. The export check is what makes that hold.
