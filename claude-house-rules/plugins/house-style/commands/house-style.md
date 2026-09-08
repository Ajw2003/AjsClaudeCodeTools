---
description: Show, choose or pin the house theme - fonts, colour, shape and prose voice for every visual artefact
---

The house style is a small set of themes, each defining fonts, a colour token set, a type scale,
shape, and a prose voice. Whichever one is pinned is injected into every session and is what
visual work gets built on.

Everything below runs through one script:

```sh
python "${CLAUDE_PLUGIN_ROOT}/scripts/style.py" <subcommand>
```

If `python` is not the working interpreter on this machine, use the same probe `run.sh` uses -
run each candidate and check its output, never just `command -v`:

```sh
[ "$(python3 -c 'print(9)' 2>/dev/null)" = 9 ] && echo python3 works
```

## Pick the subcommand from what the user asked for

**No argument, or "what's my style", "show", "which theme":** run `show`, then say in one line
which theme is active and where the pin came from. Do not publish anything.

**"list", "what themes are there", "options":** run `list` and show the table as-is. It is
already formatted; do not restyle it into prose.

**"use X", "switch to X", "pin X":** run `use X`. Add `--global` only if the user said this
machine / everywhere / all projects rather than this project. Confirm the path it wrote.

**"gallery", "show me", "let me pick", "compare":** the visual picker. See below.

**"css", "tokens", "give me the variables":** run `css [name]`, or `css <name> --system` when the
target cannot load a webfont - anything self-contained, offline, or emailed. Paste the output at
the top of the page's `<style>`.

Its first line is the marker:

```css
/* house-style: quarry */
```

Keep it. The `styleguard` hook reads that comment to decide whether a page about to be published
was built on a house theme, and stays silent when it finds a known one. A page without it gets a
permission prompt in front of the user - so stripping the marker does not make a page cleaner,
it makes publishing it noisier.

**"refresh", "update the catalogue":** run `refresh`. It reports each source as network, cache or
unavailable and always exits 0; unavailable is a normal offline state, not a failure.

## The gallery

1. Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/style.py" gallery <path>`, writing to the
   scratchpad. It fetches the font catalogue and inlines it - the page cannot fetch anything
   itself, because artifacts run under a CSP that blocks fetch to every host.
2. Publish that file with the Artifact tool, passing `capabilities: {"db": {}}` so the Use-this
   buttons can record a choice, and a favicon on first publish. Strip the
   `<!doctype>`/`<html>`/`<head>`/`<body>` wrappers; keep the `<title>`, `<style>`, markup and
   script. **Read `artifact-design` first** - the page is a deliverable, not a dump.
3. Give the user the link and say they can click a theme or reply with a name.
4. When they pick, read `choice/active` back with `read_db` (or take the name they typed) and run
   `use <name>` to write the real pin. **The db row is not the pin.** It is what the page could
   reach; the pin is a file on disk, and only `use` writes it.

## Rules for this command

- Never invent a theme, a font, or a hex value. If the user wants a look none of the themes
  cover, say so and offer to author a new theme file rather than one-off styling a page.
- `use` writes a file. Say which one, and never write the global pin when the user asked about
  this project.
- The prose voice is part of the theme, not decoration. After a switch, write in the new theme's
  voice, not only in its colours.
