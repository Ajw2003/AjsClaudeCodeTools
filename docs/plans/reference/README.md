# Reference pages

aj's references for what a handover page should look like. Use them for the form, not the
content: each was written for one specific project.

| Page | Chosen | The reference for |
|---|---|---|
| `sword-fighting-proposal.html` | 2026-11-02 | **Plans and pitches.** aj's template for every future plan and pitch. |
| `learning-tools-plugin.html` | 2026-10-17 | Pictures on every item, pictures that follow the theme, and text that matches its pictures. |

## `sword-fighting-proposal.html`: the plan-and-pitch template

The page pitches a first-person phone-as-sword duel game for `Ajw2003/AjsCanadaPrty`, built on
`Ajw2003/RockSkipping`'s phone-controller stack. aj chose it because the language, the
rendering, the level of detail and the diagrams together let a reader picture the idea and
understand all of it. What a new plan or pitch should copy from it:

- **It opens with the moment, not the mechanism.** The first item shows a concept frame of the core
  experience (a sword clash on a dock) and says the pitch in one line before any detail.
- **It shows what exists before what is new.** Every item's "today, creates, impact" lines name the
  existing file or system it reuses, and one diagram colours each part as reused, adapted or new.
- **It has one picture per idea, of the right kind.** Rendered concept frames show what it will look
  like (hero shot, roster, arenas). Plain labelled diagrams explain how it works (the grip, the
  move set, a timing chart, the reuse map). Every picture has a caption that says what it shows,
  and says when a picture is a mock-up rather than the real product.
- **It is honest about what is unknown.** Untested numbers are labelled as starting values, and
  unmeasured risks name the milestone that will measure them. A "Risks" item says what could sink it.
- **Its milestones can be checked.** Each milestone has an acceptance test someone else could run
  (for example, "18 of 20 swings read correctly").
- **The choices close the page.** Each open decision has two to four options, one marked as the
  suggestion, the reason for that suggestion, and pictures where the options are visual.
- **It reads plainly.** It defines jargon on first use (gimbal lock, POSE and SWING), names every
  file and system, and uses short sentences that read on a phone. It went through
  `@house-rules:editor` before aj saw it.

### Files

| Path | What it is |
|---|---|
| `sword-fighting-proposal.json` | The content file. Build with `make_page.py build` |
| `sword-fighting-proposal-pics/` | The nine pictures the page shows |
| `sword-fighting-proposal-sources/scene.html` | The three.js scene that renders the low-poly concept frames. Pick a frame with `?shot=hero`, `roster`, `arena-dock`, `arena-maple` or `arena-ice` |
| `sword-fighting-proposal-sources/shoot.js` | Serves `scene.html` locally and screenshots each frame with Playwright into `out/` |
| `sword-fighting-proposal-sources/*.svg` | The four diagrams (grip, moves, timing, reuse), hand-written SVG |
| `sword-fighting-proposal-sources/svg2png.js` | Rasterises those SVGs to PNGs beside them, with Playwright |

### Regenerating the pictures

Both scripts need Node and Playwright with Chromium. The renderer also needs three.js
`0.169.0`, installed into the sources folder, because `scene.html` imports it from
`./node_modules/three`. From the repo root, in bash:

```bash
cd docs/plans/reference/sword-fighting-proposal-sources && npm install --no-save three@0.169.0 && node shoot.js hero roster arena-dock arena-maple arena-ice && node svg2png.js "$PWD/grip.svg" "$PWD/moves.svg" "$PWD/timing.svg" "$PWD/reuse.svg"
```

The renders land in `out/`, and each SVG's PNG lands next to it. Delete `node_modules/` and
`out/` afterwards, or copy the PNGs into a page's `-pics/` folder first.

## `learning-tools-plugin.html`

What makes it a reference:

- **A picture for every item.** Each item in the overview and each item in the Changes section
  carries a picture showing what it creates: a folder tree, a step flow with its loop, a
  stable-versus-draft outline, an install path, a progress list, and the documentation tiers. aj
  wants pictures like these to become mandatory.
- **Pictures follow the theme.** The SVGs carry their own light and dark colours, so they read on
  either page background.
- **Text matches the pictures.** Counts, section names and labels are the same in the words and the
  drawings.

`learning-tools-plugin.json` is the content file it was built from with `make_page.py build`; the
pictures are in `learning-tools-plugin-pics/`. The page was written for the AjsLearningTools plan,
so its subject is that plan.
