# Published artefacts

The two pages the `house-style` plugin produces, kept here so they outlive the session that made
them. `manifest.json` records where each one is published, which command produced it, and what
capabilities it was published with.

**Do not hand-edit the HTML in this directory.** Both files are generated, and the next run of
their command overwrites them wholesale. Edit the template or the themes instead:

| File | Regenerate with | Built from |
|---|---|---|
| `house-style-gallery.html` | `style.py gallery docs/artifacts/house-style-gallery.html` | `templates/gallery.html` + every file in `themes/` |
| `house-style-builder.html` | `style.py builder docs/artifacts/house-style-builder.html` | `templates/builder.html` + `constraints()` + the font catalogue |

Both commands live at `claude-house-rules/plugins/house-style/scripts/style.py`, and both write
here by default when this directory exists.

## Why these are committed, and what stops them rotting

A generated file in version control drifts from its generator: add a theme, forget to regenerate,
and the committed page describes a world that no longer exists — which is worse than having no
page at all, because it looks authoritative.

So `verify_style.py` holds these files to the themes actually on disk. Every page here must name
every theme in `themes/`, and must name no theme that does not exist. Adding a theme without
regenerating fails the suite.

The guard is structural rather than byte-exact on purpose. Both pages embed a generation
timestamp and the live font catalogue, so regenerating never reproduces the same bytes twice and
a byte comparison would fail for reasons that mean nothing.

## Standalone here, stripped when published

These are the **standalone** documents the commands emit: doctype and wrappers included, so
opening one off disk works, offline, exactly as the published page does.

Publishing removes the `<!doctype>`, `<html>`, `<head>` and `<body>` wrappers, because the
artifact host supplies its own — see `commands/house-style.md` for the step. Keep the `<title>`,
the `<style>`, the markup and the script. That is the only difference between what is here and
what is at the URLs in `manifest.json`.

## The one host rule

Both pages load fonts from `fonts.googleapis.com` and nothing else. A published artifact runs
under a CSP that permits stylesheets only from that host and font files only from
`fonts.gstatic.com`, and a blocked load fails silently — the page renders in a fallback face and
nothing says why. `verify_style.py` checks these committed files for stray hosts as well as the
freshly generated ones.
