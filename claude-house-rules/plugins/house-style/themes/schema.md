# The theme format

One JSON object per theme, one file per theme, in this directory. `style.py validate` checks
every file here against the rules below, and `verify_style.py` runs that on every commit.

A theme is not a palette. It carries four things a page needs and one thing prose needs, and a
file missing any of them is rejected rather than half-applied.

## Why every field is required

There is no "optional with a sensible default" in this schema. A default is a decision made
somewhere other than the theme file, and the whole point of the plugin is that the theme file is
where the decisions live. A theme that cannot say what its mono font is has not been authored.

---

## `identity`

| Key | Type | Notes |
|---|---|---|
| `name` | string | lowercase, `[a-z0-9-]+`. The pin value and the filename stem. Must match the filename. |
| `label` | string | Display name. `Quarry`, not `quarry`. |
| `summary` | string | One sentence, shown in `/house-style list` and on the gallery card. |
| `for` | string | What this theme is *for*. The line that makes choosing easy. |
| `defaultScheme` | `"light"` \| `"dark"` | Which scheme the theme was authored in. Both are still required in full — this only says which one is the design and which is the derivation. |
| `sources` | array | One `{what, url, licence}` per ingested piece. Fonts, palettes, anything not ours. |

`sources` is not bookkeeping. Every font here is somebody's work under a licence, and a theme
that cannot say whose is a theme that cannot be shipped. Type scale, shape and voice are ours
and are recorded as `licence: "in-repo"`.

## `fonts`

Three roles — `display`, `body`, `mono` — each an object:

| Key | Type | Notes |
|---|---|---|
| `family` | string | The Google Fonts family name, exactly as Google spells it. |
| `googleFontsUrl` | string | Must begin `https://fonts.googleapis.com/`. Nothing else loads. |
| `stack` | string | Full CSS stack, webfont first, real fallbacks after. |
| `systemStack` | string | **No webfont.** System faces only. Non-empty, always. |
| `weights` | array of int | The weights the URL actually requests. |

### Two stacks, and why the second is not optional

Published artifacts run under a CSP that allows stylesheets only from `fonts.googleapis.com` and
font files only from `fonts.gstatic.com`. Every other host — Fontsource, Bunny, self-hosting — is
blocked outright, with no visible error. So `googleFontsUrl` is checked, not trusted: a theme
pointing anywhere else would render in a fallback face and nobody would be told why.

And some surfaces load no webfont at all. `templates/step-card.html` in the house-rules plugin is
required to be self-contained and offline — a machine mid-install may have no network, and that
plugin's `verify.py` fails if an external reference appears in it. `systemStack` is what those
surfaces get. A theme whose identity collapses without its webfont is a theme that cannot be used
on half the surfaces this repo ships to, so `systemStack` is chosen to hold the *character* of
the theme, not merely to be a safe default: a serif theme falls back to a serif.

## `colour`

`light` and `dark`, both complete, both carrying exactly this token set:

```
bg  card  ink  muted  line  accent  accent-ink  code-bg  warn-bg  warn-ink  warn-line
```

These are the names `templates/step-card.html` already uses. That is deliberate and it is the
reason the existing template became themeable without renaming a single variable.

Rendered into CSS, the light set defines bare `:root`, the dark set is repeated under both
`@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) }` and
`:root[data-theme="dark"]` — so the viewer's explicit choice wins in both directions and the
default "system" setting still works. `templates/tokens.css` is the shape; `style.py css` emits it.

Never give a colour its only definition inside a media block. A page whose `body` has no explicit
token background borrows the host's ground and breaks in one theme or the other.

## `scale`

| Key | Type | Notes |
|---|---|---|
| `base` | string | Root font size, e.g. `"16px"`. |
| `ratio` | number | Modular scale ratio. `--step--1` through `--step-4` are derived from it, not stored — a stored ladder drifts from its own ratio. |
| `lineHeight` | number | Body line height. |

## `shape`

| Key | Type | Notes |
|---|---|---|
| `radius` | string | Corner radius. |
| `border` | string | Border width, or `"0"` for a theme that separates with shadow instead. |
| `shadow` | string | Full CSS `box-shadow`, or `"none"`. |
| `space` | string | The spacing unit the rhythm is built from. |
| `measure` | string | Container max-width. This is what makes a dense theme dense. |

## `voice`

| Key | Type | Notes |
|---|---|---|
| `density` | `"generous"` \| `"balanced"` \| `"tight"` | |
| `headingStyle` | `"sentence"` \| `"title"` | |
| `useEyebrow` | bool | |
| `useLede` | bool | |
| `prefer` | `"prose"` \| `"table"` \| `"card"` | What this theme reaches for first when it has a choice. |
| `proseTone` | string | **Injected verbatim into context at SessionStart.** Non-empty. |

`proseTone` is the half of this system that is not CSS. A theme that only changed colours would
let the same prose sit under three different skins, which is a paint job, not authorship. This
string is an instruction to Claude about how to *write* under this theme, and it is why choosing
Ledger produces a different document rather than the same document in a different font.

---

## The marker

`style.py css` writes this as the first line of every token block it emits:

```css
/* house-style: <name> */
```

It is not a comment for humans. The `styleguard` hook reads it on every publish: a page carrying
a known theme name passes silently, a page without one raises a permission prompt naming the
active theme and its alternates. The name inside it must be a theme that exists here - a page
stamped with a theme that was deleted or renamed is treated as unthemed, which is the correct
answer rather than a false pass.

## The variety rule

`verify_style.py` asserts that no two shipped themes share an `accent`, a `body.family`, a
`shape.radius` or a `scale.ratio`.

This is a mechanical guard against a real and slow failure: themes are edited one at a time, each
edit is individually reasonable, and three distinct looks converge into three tints of whichever
one was touched last. The check cannot prove taste. It can prove that nobody quietly made the
choice meaningless, which is the part that actually decays.
