# Audit: the plunderspell "Wick and the Ophan, In Game" handover page

Date: 2026-10-15. Subject: the plan page a plunderspell session published on 2026-10-14 (proposal for
plunderspell issue "Raids feel frightening"). I checked the page against what the plugin asks for in
`claude-house-rules/plugins/house-rules/rules/detail/show-dont-tell.md`, then traced each gap back to the
plugin code.

## What the page does well

- It opens with what already exists, and gives each part a fate (reuse, change, keep, replace), as the
  rule asks.
- It offers choices with one marked as the suggestion, and gives an approval phrase that names the plan.
- It shows a real Editor render and states what was run: a build with no errors, 7 import tests, and
  250 passed / 3 skipped.

## What is missing, measured against the rule

The rule (detail file, "The handover page") says every page is built from
`templates/handover-page.html`, in four parts. This page was hand-written, so none of the template's
structure is there:

| Required | On the page? |
|---|---|
| **In short**: plain sentences plus a row of icons to tap, each showing what it creates beside what it needs from you | No. There is a lede paragraph and no icons. |
| **Changes**: each item tagged New / Changed / Kept; tapping a Changed item shows before and after; tapping a New item shows what triggers it, what it does and what you get | Partly. A static table uses its own tags ("reuse", "replace, piece 3"). Nothing can be tapped, and there is no before/after. The two creatures and the quota are never tagged as New items. |
| **Choices**: a "why" to open, plus a box for your own answer | Partly. The "why" is always shown rather than opened on tap, and there is no box for your own answer. |
| **Wrap-up**: summary, what's changing, what's blocking, what's next, numbered steps for you, then a reply to copy | Mostly missing. There is one example phrase. It has no copy button, no "blocking" line, no numbered steps, and the reply doesn't change as you pick options. |
| Detail only on tap; something you can try | No. The page is entirely static. |
| One colour, one meaning: orange only for something you act on | Broken. Orange (`--fire`) marks the Wick *and* the "replace" tag. Blue (`--lapis`) marks the Ophan, the "change" tag *and* the suggestion. There is no legend. |
| Names, never bare numbers | Broken. The header gives a bare issue number ("issue #386"), and the pieces have no issue names at all. |
| Each step has its own issue (sub-issue per step, with depends-on and done-when) | Not shown. The three pieces have no issues, so you can't see dependencies or progress. The plugin also refuses "Build plan approved" until at least two issues labelled `AjsAgent created this` were made during the plan, so the page's own approval phrase may not have worked. (Not checked against plunderspell's GitHub: that repo is not in this session.) |

## Why: traced to the plugin code

1. **The template rule never reaches the session.** The session is injected only the short rule,
   `rules/show-dont-tell.md`, by the `showrule` hook (`scripts/hook.py:584-597`). That short text never
   mentions the template, the four parts, the orange rule or bare numbers. All of that sits only in
   `rules/detail/show-dont-tell.md:97-108`, which a session reads only if it chooses to. A grep of
   the plugin finds `handover-page` only in that detail file and in `verify.py`.
2. **Nothing checks a page's shape.** `hook.py` has no check that a page came from the template, has
   the four parts, or keeps to the colour rule. The only page-related checks are the over-200-word
   reminder (`hook.py:6609-6629`), which a page link satisfies, and the editor-helper nudge for
   `docs/plans/*.html` (`hook.py:6647-6687`). Neither looks inside the page. `verify.py:8517-8529`
   checks only that the template file exists and that the *detail* file names it. It doesn't check
   the injected rule, which is the text a session actually sees.
3. **The Artifact tool brings its own design system, and that one wins.** Publishing to claude.ai
   tells the model to load the `artifact-design` skill before writing the page. The page shows
   exactly that: colour tokens on `:root`, dark-mode guards, Google-font pairing. That instruction
   sits in the system prompt, and the template is two levels away in a file nobody points at. So the
   model followed the instruction it could see.
4. **Ruled out: the template was live.** At first I suspected the session predated the template. The
   template reached `main` with the PR #234 merge at 2026-10-14 20:28 local time (02:28 UTC on
   2026-10-15). aj confirmed the page was made after that merge, so the template existed and was simply
   not used. That leaves causes 1 to 3.

## Fixes this points to (not built; each needs your approval)

- Put a one-line pointer to the template, with its absolute `<plugin>` path, into the injected
  `rules/show-dont-tell.md`, and have `verify.py` check the injected text for it, not just the detail
  file.
- Add a check on written or published pages: the four `data-part` markers and `const PAGE = {`
  present, or say clearly that the page wasn't built from the template.
- State in the rule that the template overrides the `artifact-design` skill's look for handover
  pages.
