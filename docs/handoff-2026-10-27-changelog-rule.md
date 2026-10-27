# Handoff: a changelog page in every repo (2026-10-27)

Paste this into a fresh Claude Code session on `Ajw2003/AjsClaudeCodeTools`.

**State:** the design is approved, and the build plan is written and waiting on approval. No plugin code has
changed. The work is on branch `claude/project-thread-4je2dp` and is all docs. It started in a PlunderSpell project
thread, and aj moved the build here because it doesn't belong in that project.

## What aj asked for

aj liked the Changes section of PlunderSpell's visual roadmap and asked for it to become a changelog page that every
repo needs. They picked "A house rule that requires it" over a skill or PlunderSpell-only. They approved the design
on 2026-10-27 as **"Design approved: changelog page rule 1A 2A 3A"**:

- **1A.** The changelog lives in `docs/changelog/`, next to the six tiers rather than as a seventh tier. The folder
  holds `changelog.json`, the built `changelog.html` and `changelog-pics/`.
- **2A.** The session-start docs check names a missing changelog. A pull request whose branch leaves
  `docs/changelog/` unchanged gets a reminder, never a block.
- **3A.** A row marked visual must carry a real, existing picture.

## Next steps, in order

1. **Get the build plan approved.** Show aj `docs/plans/changelog-rule/build-plan.html` (published at
   https://claude.ai/artifact/HkCZV8e1ZLofXrAqRTGbg4) and wait for "Build plan approved: changelog page rule".
   This session's design-loop stage won't carry over, so if the hooks ask for it, aj has to repeat the design
   approval line above first.
2. **#385, the template.** Add `templates/changelog.page.json` to the plugin. Copy it from PlunderSpell's
   `docs/templates/changelog/changelog.template.json` (branch `claude/project-thread-4je2dp` of `Ajw2003/PlunderSpell`;
   its README and filled example are next to it). Also add a section to the `house-rules:project-docs` skill.
3. **#386, the session-start check.** In `scripts/house_rules/docs.py`, extend `event_docstiers` to look for
   `docs/changelog/changelog.json`, and add verify.py cases next to the existing docstiers fixtures
   (`scripts/checks/common.py`, `_docstiers_repo`).
4. **#387, the pull request reminder.** Add it to `gh pr create` in `guard` (`scripts/house_rules/safe_git.py`,
   near the Refs check) and to `guardgithub` for the GitHub tool. Use `git diff --name-only <base>...HEAD` under the
   staged-docs check's timeout, and add the `HOUSE_RULES_CHANGELOG=off` switch.
5. **#388, the rule text, docs and release.**
   - Add one sentence to `rules/house-rules.md` ("Documentation goes in tiers"). It sits at about 8,900 of a
     9,700-character inject margin.
   - Put the detail in `rules/detail/docs-tiers.md`.
   - Update `docs/4-systems/changelog.md`, which is already written as the plan.
   - Add a Decisions entry, update state and today, and give this repo its own first `docs/changelog/`.
   - Bump the version, open a pull request that says "Refs #384", and send a QA page.

## Where everything is

- Issues: #384 (parent), with #385, #386, #387 and #388 as its sub-issues. All are labelled
  `AjsAgent created this` and `in progress`.
- Design page: `docs/plans/changelog-rule/changelog-rule.html` (https://claude.ai/artifact/PUnxthJ9ViwaykT5UXxt1M).
- Build plan page: `docs/plans/changelog-rule/build-plan.html`.
- Systems doc (planned mechanism): `docs/4-systems/changelog.md`.
- The page it comes from: PlunderSpell's roadmap, `docs/roadmap-visual/roadmap.html`
  (https://claude.ai/artifact/6LzKZXSuHpiVjtTnkA8E5s).
