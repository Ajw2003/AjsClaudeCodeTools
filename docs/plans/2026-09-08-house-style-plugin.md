# Ship house-style: a second plugin for fonts, colour, shape and prose voice

## Context

Every visual artefact this repo produced invented its own look. Three files, three unrelated
colour systems, three independent font decisions:

| File | Ground | Accent | Fonts |
|---|---|---|---|
| `plugins/house-rules/templates/step-card.html` | `#f7f6f3` warm paper | `#2f6f4f` | system stack only |
| `artifact-test.html` | `#f2f3f0` green-tinted | `#3f7d3a` | IBM Plex, from Google Fonts |
| `docs/architecture-review-2026-09-07.html` | Tailwind `bg-stone-50` | `indigo-500` | `font-serif` / `font-mono` |

None was wrong alone. Together they said the repo had no look: each page was designed by whichever
model happened to be running that turn, and the author's taste entered the result only when he
happened to be watching.

`house-rules` exists so behavioural rules follow every device via hooks rather than a file that
has to be copied around. This is the same move for the *look* — and, crucially, for the voice.

## What shipped

A second plugin at `claude-house-rules/plugins/house-style/`, added as a second entry in the
existing `.claude-plugin/marketplace.json` (which `docs/architecture.md` already anticipated:
"another entry in this same list, not a new marketplace file"). Same shape as the first: one
`run.sh` shim, one stdlib-only Python file, dispatched by event, with its own suite.

### A theme is one JSON file

`themes/schema.md` is the contract. Fonts in three roles, an 11-token colour set in light and
dark, a type scale as base plus ratio, shape, and a `voice` block. Every field is required —
a default is a decision made somewhere other than the theme file, and the theme file is where
the decisions live.

Three ship, deliberately far apart on every axis:

| | Quarry | Ledger | Signal |
|---|---|---|---|
| For | prose, handovers | dense reference | one-pagers |
| Body | Source Serif 4 | IBM Plex Sans | Inter |
| Accent | `#2f6f4f` | `#2c5d8f` | `#8b6bff` |
| Radius / measure | 14px / 46rem | 4px / 72rem | 18px / 40rem |

Quarry is the fallback because it *is* the palette `step-card.html` already used — adopting it
renamed nothing, and the two are now asserted identical token for token in both schemes.

**`voice.proseTone` is the half that is not CSS.** It is injected verbatim at `SessionStart`, so
choosing Ledger produces a terser document rather than a bluer one. Without it, picking a theme
would repaint the same document three ways, which is a paint job, not authorship.

### Three hooks, each failing as its event permits

| Event | Arg | Effect | Failure |
|---|---|---|---|
| `SessionStart` | `style` | Resolves the active theme and injects its tokens, alternates and prose voice | loud, not closed |
| `PreToolUse` (`Artifact`) | `styleguard` | Silent on a page carrying a known marker; asks otherwise | **closed**, exit 2 |
| `PostToolUse` (`Write`) | `styled` | Reminds after an unthemed in-project visual write | never obstructs |

`styleguard` stays silent on a compliant page for the same reason `handover` does: a hook that
fires on a *correct* publish cannot end quietly, and the only thing left to say is that nothing
needed saying. The cost is a page stamped with a marker it did not earn passes unchecked.

### The constraint that shaped everything

Published artifacts run under a CSP permitting stylesheets only from `fonts.googleapis.com`, font
files only from `fonts.gstatic.com`, and **no `fetch` to any host at all**. So Google Fonts is
the only usable webfont source (`validate()` enforces it, or a theme would silently render in a
fallback face); every theme carries a second, webfont-free stack for `step-card.html` and other
offline surfaces; and the font catalogue is fetched **in Python at command time and inlined into
the generated page**, never by the page.

### The builder, and the bug it shipped with

Authoring a fourth theme by hand meant 22 hex values, three font objects and a voice block — bad
enough that in practice nobody would, which turns a three-theme system into a fixed one.
`style.py builder` generates a page: pick a ground and an accent, the rest derives.

The first version had a real defect. `solveOn` binary-searched lightness for a colour meeting a
contrast target and, when none existed, returned the value it was initialised with. Against a
mid-grey ground a 12:1 `ink` is unreachable at any lightness — `#787878` tops out at 4.76:1
against pure black — so `ink`, `muted` **and the user's chosen accent** silently became `#ffffff`.

Three fixes:

- `solveOn` returns `null` when a target is unreachable; every caller handles it.
- The ground became a **tint**: it supplies hue and chroma, the scheme supplies lightness. Used
  literally, any ground between roughly 12% and 75% lightness cannot support a readable `ink`.
- `ink` and `muted` are solved separately with a required minimum contrast between them — when
  both fell back to white the palette had no hierarchy and nothing noticed.

The warn tokens stay semantic amber, clamped to the amber band. An unclamped nudge toward a blue
ground reached hue 0.19 — chartreuse — which reads as a highlighter pen, not a warning.

### Verification, and the lesson from it

`verify_style.py` runs offline (a suite needing the network would fail on exactly the machines the
fallback exists for) and extracts the deriver from the *generated* page to run under node.

The original deriver test used a hand-picked case list. Every case sat outside the broken band;
the nearest scraped past at 12.8:1 and hid the rest. It was replaced by a sweep across 2–98%
ground lightness, seven hues, four saturations and six accents — about 47,000 assertions over
3,360 pairs. **The old deriver fails that sweep 4,924 times.**

The lesson is worth more than the bug: the cases had been chosen to be *plausible* rather than
*hostile*. A test that only covers the inputs you imagined is a test that agrees with you.

### Artefact custody

The generated pages, their live URLs and this plan initially existed only outside the repo, and
an ignore line I added — `house-style-gallery.html` — actively defeated the rule the `artifact`
hook exists to enforce. They now live in `docs/artifacts/` with a manifest, and a staleness guard
asserts every committed page still names every theme on disk. The guard is structural rather than
byte-exact: both pages embed a generation timestamp and the live font catalogue, so regenerating
never reproduces the same bytes and a byte comparison would fail for reasons that mean nothing.

## Outcome

- `verify_style.py` and `verify.py` both green; the latter unchanged at 108 throughout.
- The three pages that motivated the plugin are now on three different themes from one token set:
  `step-card.html` on Quarry (still loading nothing external), `artifact-test.html` on Signal, and
  the architecture review on Ledger — the last by binding Tailwind's own scales to the theme
  (`slate-500` *is* the theme's muted) rather than overriding 44 utility classes.
- SessionStart injection costs ~350 tokens, against ~5,100 for the rules injection beside it.

## Not done

`tools/clean_install_test.py` has not been run — it strips the local install and reinstalls from
GitHub, so it needs the `claude` CLI and a real device. Worth running before relying on the
two-plugin marketplace.

`api.fontsource.org` is blocked by this environment's egress proxy, so the 62 curated families in
`FALLBACK_FAMILIES` could not be checked against the live catalogue. Every one must exist on
Google Fonts specifically — a face that is only on Fontshare is blocked by the CSP and fails
silently. One (Clash Display) was caught and removed on those grounds.
