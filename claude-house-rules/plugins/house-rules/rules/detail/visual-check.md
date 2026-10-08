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
