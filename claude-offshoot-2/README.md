# offshoot-2 (placeholder)

STATUS: shell only. No purpose has been assigned to this plugin yet. It exists so the second
offshoot mentioned in [docs/offshoots-plan.md](../docs/offshoots-plan.md) has scaffolding ready
the moment it's defined, instead of someone re-deriving the plugin skeleton from scratch.

## What's actually here

The structural minimum every plugin in this repo shares:

- `plugins/offshoot-2/.claude-plugin/plugin.json` — plugin manifest, version `0.0.1`.
- `plugins/offshoot-2/hooks/hooks.json` — registers one hook: `SessionStart` → `inject`.
- `plugins/offshoot-2/scripts/run.sh` — the same interpreter-probing shim `house-rules` and
  `prompt-workshop` use, adapted only in its env var names (`OFFSHOOT2_PYTHON`,
  `OFFSHOOT2_DEBUG`) and its one fallback message.
- `plugins/offshoot-2/scripts/hook.py` — one handler, `event_inject`, which does nothing more
  than announce (via `systemMessage`) that this plugin is a placeholder. No rules file is
  loaded because none exists yet.
- `plugins/offshoot-2/scripts/verify.py` — proves the placeholder announces itself correctly and
  never fails, the same numbered-PASS/FAIL shape as the other two plugins' suites.
- `plugins/offshoot-2/rules/README.md` — a note, not a rules document; explains where the real
  one goes once this offshoot has a purpose.

## Filling this in

When the purpose is decided:

1. Replace `INJECT_NOTE` in `scripts/hook.py` and write the real rules doc under `rules/`.
2. Add whatever new hook events the purpose needs, following `prompt-workshop`'s `event_workshop`
   as the worked example of adding a second handler next to `inject` — including picking the
   right failure-mode contract per event (closed+loud, loud-only, or never-fail) the way
   `docs/architecture.md`'s pattern for `house-rules` explains.
3. Register the new events in `hooks/hooks.json` and extend `scripts/verify.py` to cover them —
   the hooks.json/`EVENTS` parity check already in this suite will fail loudly if the two drift.
4. Rename the plugin (directory, `plugin.json`'s `name`, the marketplace entry) away from the
   placeholder `offshoot-2` once it has a real one.

## Running the test suite

```bash
python claude-offshoot-2/plugins/offshoot-2/scripts/verify.py
```
