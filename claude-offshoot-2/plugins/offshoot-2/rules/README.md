# offshoot-2 rules

Empty on purpose. There is no `inject`-loaded rules document yet because there is no defined
purpose yet for this plugin to encode — see `docs/offshoots-plan.md` at the repo root.

When this offshoot's purpose is decided, this is where its "what to do" document goes (the
`prompt-workshop.md` / `house-rules.md` equivalent) — `hook.py`'s `inject` handler would then
read and print it here instead of `INJECT_NOTE`, mirroring how the other two plugins in this
repo load their rules text at `SessionStart`.
