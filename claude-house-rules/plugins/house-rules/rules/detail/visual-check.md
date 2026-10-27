# A visual change is checked by looking at it

Code does not always tell the whole story. When a change affects something a person sees — a
page, a component, a layout, a style, a scene, a rendered chart — I look at it, not only at the
code:

- **Screenshot the same flow before and after**, plus any flow the change adds, and compare them.
  The "before" is the committed version: a `git worktree` or `git stash` of HEAD renders it
  without losing the change.
- **Debugging something visual or nuanced starts by capturing it.** An image of the actual
  problem is evidence; reasoning about what the CSS probably does is not.
- **Inspect the images**, and say what they show. A screenshot nobody looked at is not a check.
- **No way to render here** — no browser, no display, no engine — says so and why, per "not
  checked needs a reason", and names the screenshot the user should take.

Chromium with Playwright, the built-in browser, or the platform's own capture tool are all fine;
what matters is that an image of the real result is in the turn.

The `handover` (Stop) hook reminds a turn that wrote a visual file (`.css`, `.html`, `.tsx`,
`.vue`, `.uxml`, a Unity scene or prefab, …) with no screenshot, browser capture or image read
anywhere in it.

**Why:** visual regressions pass every test that reads code, because the code is what changed on
purpose. The user asked for the same flow to be screenshotted old and new whenever a change is
visually noticeable, and for a captured image to be part of debugging anything visual.

## On a QA page, evidence by change type

A QA page (`make_page.py` QA mode) proves each change with the evidence its type needs. There is no skip: it
runs in every project, whatever `docs/page-style.json` says.

| type | media | before / after |
|---|---|---|
| animation | a clip (.mp4 or .webm) | two clips |
| gameplay, ai | a clip (the recording) | two clips |
| model | a picture (.png .jpg .jpeg .gif .webp) | two pictures |
| visual | a picture | two pictures |
| none | nothing; needs a non-empty `reason` | nothing |

Content format, a non-empty `qa.evidence` list, one entry per change:

```json
"evidence": [
  {"change": "Wings-spread pose", "type": "animation", "media": "docs/art/spread.mp4",
   "before": "docs/generated/old.mp4", "after": "docs/generated/new.mp4", "caption": "The held pose"},
  {"change": "Test helper", "type": "none", "reason": "A test-only script; nothing is drawn."}
]
```

- **Types come from the changed files** (`git diff --numstat <base>...HEAD`), matched against default patterns
  (`DEFAULT_EVIDENCE_PATHS` in `make_page.py`): first match wins in the order animation, model, ai, gameplay,
  visual. A project replaces any key with `"evidence_paths": {"ai": [...], "ignore": [...]}` in
  `docs/page-style.json`. Every implied type needs an entry of that type (gameplay and ai cover each other).
- **Named but not shown is refused:** a picture or clip path written in the page text that no shown file
  matches fails the build, naming the path.
- **15 MB limit:** a copied file over 15 MB is refused (the claude.ai page host refuses it); shorten or re-encode.
- Zero changed files against the base is refused too.
