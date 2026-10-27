# QA evidence by change type: build spec

Parent issue #389. Approved: "Design approved: QA evidence by change type 1A 2A 3A" and
"Build plan approved: QA evidence by change type" (aj, 2026-10-27). Design page:
`docs/plans/qa-evidence-by-type-design.html`; plan page: `docs/plans/qa-evidence-by-type-plan.html`.

All paths below are relative to `claude-house-rules/plugins/house-rules/` unless they start with `docs/`.

## The content format (new `qa.evidence` list)

```json
"qa": {
  "feature": "...", "base": "...", "unverified": ["..."], "files": {},
  "evidence": [
    {"change": "Wings-spread pose", "type": "animation",
     "media": "docs/art/anim/fear/ophan_spread.mp4",
     "before": "docs/generated/x/old-hover.mp4", "after": "docs/generated/x/new-spread.mp4",
     "caption": "The held pose after the arrival"},
    {"change": "Test helper", "type": "none", "reason": "A test-only script; nothing is drawn."}
  ]
}
```

Types and what each needs (choice 3A: no way to skip; every project, whatever page-style.json says):

| type | media | before / after |
|---|---|---|
| animation | a clip (.mp4 or .webm) | two clips |
| gameplay, ai | a clip (the recording) | two clips |
| model | a picture (.png .jpg .jpeg .gif .webp) | two pictures |
| visual | a picture | two pictures |
| none | nothing; needs a non-empty `reason` | nothing |

`qa.evidence` must be a non-empty list. Each entry needs `change` (non-empty string) and a known
`type`. Every file named must exist (resolved the same way `copy_pictures` resolves `src`: under the
project, then the content file's folder). Refusals go through `die()` (exit 2) and name the change,
its type, and exactly what is missing.

## Type detection from changed files (choice 1A)

The changed files come from the same `git diff --numstat <base>...HEAD` that QA mode already runs.
Each changed path is matched against patterns (Python regexes, `re.search`, on the `/`-separated
path); the first type that matches wins, in this order: animation, model, ai, gameplay, visual.
Paths matching an ignore pattern imply nothing.

Defaults (`DEFAULT_EVIDENCE_PATHS` in make_page.py):

- ignore: `(^|/)docs/`, `(^|/)Tests?/`, `(^|/)Editor/`, `\.meta$`, `(^|/)Tools/`, `\.md$`, `\.json$`
- animation: `\.(anim|controller|overrideController|playable)$`, `(^|/)Animations?/`
- model: `\.(fbx|obj|blend|glb|gltf|dae|3ds)$`
- ai: `(?i)(^|/)(ai|enemy|enemies|npc|behaviou?rs?)/.*\.cs$`
- gameplay: `(^|/)Scripts/Runtime/.*\.cs$`, `\.unity$`, `\.prefab$`
- visual: `\.(uxml|uss|css|html|tsx|jsx|vue|svelte|shader|shadergraph|hlsl|vfx)$`

A project overrides any of these keys with `"evidence_paths": {"ai": [...], "ignore": [...]}` in
`docs/page-style.json`; a key given there replaces that default key.

Every type a changed file implies must be covered by at least one evidence entry of that type;
`gameplay` and `ai` cover each other. The refusal lists each uncovered type with up to five of the
files that implied it.

## Named but not shown

In QA mode, before `apply_qa` adds its rows, every string in the page (excluding the `qa.files`
keys and the evidence entries' own path fields) is searched for paths ending in a picture or clip
extension. A named path whose basename is not the basename of some shown file (any `src` in the
page, or an evidence `media`/`before`/`after`) is refused, naming the path.

## Zero changed files (#393)

`apply_qa` refuses when the numstat lists 0 files: "QA mode counted 0 changed files against
<base>; the feature is probably already merged into it. Build from the feature branch, or set
qa.base to the commit from before the merge."

## Rendering (#392)

The builder turns each evidence entry into a Changes item placed first:
`["proof", "<Type label>: <change>", <caption or reason>, null, <detail>, null, null, <evidence object>]`
where the evidence object is `{"evidence": true, "type": ..., "media": {"src": ...},
"before": {"src": ...}, "after": {"src": ...}, "caption": ...}` (pictures or clips). `copy_pictures`
walks dicts with `src`, so these are copied next to the page. `copy_pictures` refuses any copied
file over 15 MB (15 * 1024 * 1024 bytes) with: "<path> is <n> MB; the claude.ai page host refuses
files over 15 MB, so shorten or re-encode it".

Template (`templates/handover-page.html`):
- tag map gains `proof: "Proof"`, counts gain `proof`, the count line says "N proof, N new, N changed, N kept".
- a `proof` item's `<details>` is open by default.
- `picHtml` renders a `media` object first (clip or picture), then the before/after pair.
- a src ending .mp4/.webm renders `<video src muted loop playsinline autoplay controls preload="metadata">`.
- a before/after pair of clips renders in `.cmp-vid`: two columns side by side, stacking to one
  column under 640px (no slider for clips). Playing, pausing or seeking one clip in a pair does the
  same to the other (a capture-phase listener on `play`, `pause`, `seeked`; guard against loops).
- image pairs keep today's compare markup unchanged.

## Stage record and the handover reply (#394)

After a successful QA build, `record_qa_page` also writes `"qa_evidence": {"types": [...sorted
types covered...], "entries": <n>}` into the stage file. In `scripts/house_rules/design_loop.py`
the handover ctx reads `qa_evidence=_st.get("qa_evidence")`, and `_check_qa_page` returns a
blocking reason when `qa_page` is set but `qa_evidence` is missing: "the QA page <page> was built
without the evidence check (an older builder or by hand); rebuild it with make_page.py so each
change carries its clip or picture". `_record_qa_link` must not mark it linked in that case.

## Tests (verify.py parts)

- `scripts/checks/make_page.py`: an Ophan fixture (#390) - a temporary git repo whose base commit
  has `Assets/Models/ArtBible/Enemies/Fear/TheOphanOfHours/TheOphanOfHours.controller` absent and
  whose HEAD adds it plus `Assets/_Project/Scripts/Runtime/Raid/Ophan/OphanHunt.cs`,
  `Assets/Models/ArtBible/Animations/TheOphanOfHours_Generic.fbx` and
  `docs/generated/ophan-418/solo-beam.png`; content copied in spirit from the Ophan QA page (items
  that say "Screenshot: docs/generated/ophan-418/staging-beam-host.png", no evidence list). It must
  be refused (exit 2). Plus one case per refusal listed above, one passing build with full evidence
  (tiny generated PNGs; tiny clips may be any bytes with an .mp4 name since nothing decodes them at
  build time), the 15 MB refusal (a sparse file via `f.truncate()`), the zero-count refusal, the
  evidence_paths override, and the stage record. Existing QA cases get a minimal `none` entry so
  they keep passing.
- `scripts/checks/design_loop.py`: the qa page check blocks a QA stage with `qa_page` but no
  `qa_evidence`, and passes with both.

Run `python3 claude-house-rules/plugins/house-rules/scripts/verify.py` from the repo root; it must
exit 0.
