# Audit 2 of the house-rules plugin: docs against code

Raw findings from a read-only scout pass on 2026-10-16 (Read, Grep and Glob only). Each finding
quotes both sides. Paths under `scripts/`, `hooks/` and `agents/` are inside
`claude-house-rules/plugins/house-rules/`. `ProjectState.md` is the tier-3 state doc under `docs/`.

All 30 hook entry points are wired in `hooks/hooks.json` across 9 events and dispatched in
`scripts/hook.py:8286-8316`. The disagreements are below.

## Doc against code
- `ProjectState.md:17` says "nineteen handlers"; the code has 30.
- `docs/architecture.md:54` says a long reply "over 200 words" gets a reminder; the code uses 160 words and blocks (`hook.py:7157`, `:7521`).
- `architecture.md:50` describes the idle-aj refusal and the nohup and tail/head prompts; both are gone (`hook.py:4360-4402`, `:1766-1767`).
- `architecture.md:68` describes #152 refusing later prompts; it was removed (`docs/4-systems/hook-engine.md:129`).
- `claude-house-rules/README.md:82` says the guard "never blocks"; the code denies (`hook.py:2418`).
- `docs/4-systems/verify-suites.md:38` and `:77` cite the retired `agents/executor.md` and the house-rules-last-seen file; `verify.py:830` still writes last-seen.
- `architecture.md:62` calls subagentcommit "the one handler that blocks"; handover also returns `decision: "block"` (`hook.py:7767`, `:7806`).
- The `hook-engine.md` table lists 15 of the 30 entry points. Missing: showrule, profile, docstiers, versioncheck, issuelist, userpromptaudit, guardgithub, branchnudge, agentcap, pagecheck, audit, subagentrules, subagentcommit, prompttimer, promptran.
- `hook-engine.md:50` and `README.md:39` say commitgate matches Write, Edit and NotebookEdit; `hooks.json:117` also matches Bash and PowerShell.
- `docs/4-systems/guards.md:18` says the never-blocked list includes publishing a make_page.py page; no such case exists (`hook.py:2358`, `:2379`). The same line says "files the agent created"; the code checks untracked files inside the project (`hook.py:2379-2391`).
- `architecture.md:64` says commitgate never gates Bash, while the same row's addendum says the matcher includes Bash.
- `README.md:131-132` says commit and push on other branches are refused; since 2.60.0 they run unasked (`hook-engine.md:117`).
- `README.md:25` says handover gives feedback "rather than a blocking error"; the code blocks once (`hook.py:7767`).
- `README.md:55-62` says "Three tier agents"; `agents/` ships five (scout, builder, reviewer, editor, archivist).
- `README.md:28` leaves `.mjs` and `.cjs` out of the runnable extensions; `hook.py:3066` includes them.
- `README.md:384` names `-NoVerbose` and `-NoModel`; `tools/install.py:269-270` defines only `--no-verbose` and `--no-model`.
- `architecture.md:73-76` says its table is checked against hooks.json; the hook-engine table is not checked (`verify.py:4838` reads only architecture.md).
- `verify.py:4521` prints "every hook is stateless", while prompttimer, agentcap, versioncheck and others write state.
- Test counts disagree: `verify-suites.md:11` says 365 PASS, `ProjectState.md:10` says 368/368, `verify-suites.md:104` says 203, `ProjectState.md:180` says 753. The suite run on 2026-10-16 reported "all 832 checks passed". `verify-suites.md:11` itself says counts are never written down.
- `hook.py:6279-6280` uses `except ...: pass` on the issues-cache read, which "Nothing fails silently" forbids.

## Doc against doc
- `architecture.md:50` (idle-aj refusal present) against `hook-engine.md:122` (removed in #290).
- `architecture.md:556` and `:561` say "five-tier"; `architecture.md:41` and `:46` say "six".
- `architecture.md:54` says 200 words; `docs/4-systems/design-loop.md:24` and `ProjectState.md:186` say 160.
- `ProjectState.md:131` puts the loop file at `.git/house-rules-loop.json`; `design-loop.md:15` says `.claude/house-rules-loop.json`; the code uses `.claude/` with `.git/` as a legacy fallback (`hook.py:5261-5270`).
- `hook-engine.md:60` says two entry points are exempt from statelessness; `architecture.md:144` says versioncheck is the only exception; `README.md:86` says every hook is stateless.
- `docs/4-systems/label-setup.md:3` says "built"; `docs/4-systems/README.md:14` says "planned".
- `ProjectState.md:3` says "as of 2026-09-23", while its later entries run to 2026-10-16.
- `ProjectState.md:275` says one session ledger exists; `docs/sessions/` holds two files.

## Undocumented behaviour
- `hook.py:4896-4898`: `_wip_message` adds "Co-Authored-By: Claude <noreply@anthropic.com>" and an optional Claude-Session trailer to autosave commits (used at `hook.py:6370`, `:6435`, `:4692`, `:6526`). This contradicts the plugin's own credit rule and guard. Confirmed by reading the code.
- `tools/install.py:205-211` writes an attribution setting; `README.md:380-386` and `docs/4-systems/plugin-distribution.md:37-40` list only verbose and model.
- Switches with no tier-4 or architecture mention: `HOUSE_RULES_VC_GITHUB` (`hook.py:1260`), `HOUSE_RULES_VC_MARKETPLACE` (`:1205`), `HOUSE_RULES_VC_INSTALLED_PLUGINS_JSON` (`:1364`), `HOUSE_RULES_AGENTS_STATE` (`:3964`), `HOUSE_RULES_REPO_LABELS_FILE` (`labels.py`). `HOUSE_RULES_ENV_FILE` (`:692`) and `HOUSE_RULES_HANDOVER_TARGET_FILE` (`:724`) appear only in plan docs.
- `hook.py:402` `MEMORY_SCAN_MAX_FILES = 50` is undocumented.

## Portability: hardcoded person, repo, email or label
- `hook.py:1026` `DEFAULT_GITHUB_OWNER = "Ajw2003"`, which drives `.git/info/exclude` in docstiers.
- `hook.py:1169-1170` raw URL for `Ajw2003/AjsClaudeCodeTools`.
- `hook.py:1353` `_VC_DEFAULT_MARKETPLACE = "aj-house-rules"`.
- `hook.py:6101` credit-fix text with the author's GitHub noreply email, emitted in refusal messages; also `verify.py:199`, `:4114`, `:4126`.
- `hook.py:5937-5953` the credit name "AJ's agent" is hardcoded; the configurable name (#287) was never built (`guards.md:5-7`).
- `tools/install.py:52`, `tools/clean_install_test.py:29` and `tools/update.bat:36` hold the Ajw2003 repo URL.
- `tools/sync_standards.py:2,6` points at `Ajw2003/Coding-Standards`; `architecture.md:573` cites it.
- `README.md:334` and `:417` give marketplace and source URLs under Ajw2003.
- Shipped rule text: `rules/detail/deliver-workflow.md:14` (Ajw2003 URL), `rules/detail/commit-branches.md:80` (noreply email), `rules/detail/delegate-execution.md:61` (Ajw2003/PlunderSpell#350), `rules/detail/docs-tiers.md:45` (Ajw2003 default owner).
- `templates/step-card.html:136,145` hold `C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools`.
- The author email appears in line 7 of `.claude-plugin/plugin.json` for house-rules, agent-router and prompt-workshop; the marketplace owner is "aj" at `.claude-plugin/marketplace.json:5`.
- `verify.py:1533` and `:1559` use Windows paths under aj's user folder in fixtures; `verify.py:275-292` use Ajw2003 fixture remotes.
- `docs/4-systems/label-setup.md:3` names `Ajw2003/Unblocked`; `hook-engine.md:159` holds the noreply email.

## Stale citations
- `hook-engine.md:34` puts EVENTS at `hook.py:2034-2046`; it is now at `:8286`.
- `hook-engine.md:194` puts event_guard at `hook.py:793-803`; it is now at `:2394`.
- `hook-engine.md:205` puts main() at `hook.py:2049-2085`; it is now at `:8320-8361`.
- `hook-engine.md:223` puts _trace_subject at `hook.py:1006-1014`; it is now at `:2297`.
- `hook-engine.md:228` and `:233` put _unity_markers_in_parent at `hook.py:340-349`; it is now at `:834-856`.
- `ProjectState.md:23` puts INJECT_CHAR_LIMIT at `hook.py:71`; it is now at `:84`.
- `ProjectState.md:25` puts _subagent_core at `hook.py:1886`; it is now at `:3293`.
- `ProjectState.md:27` puts _staged_docs_status at `hook.py:1174`; it is now at `:1948`.
- `verify-suites.md:72` cites `verify.py:2372-2393`; the code is now at `:5103-5140`.
- `plugin-distribution.md:20` cites `install.py:88-124`; the code is now at `tools/install.py:160-185`.

## Not verified by the scout
- The scope reminder sizes (260 and 909 characters) need a run.
- The `update.bat` CRLF line endings were not checked.
- `ProjectState.md:268-272` claims a `Modified.md` and five `.claude/worktrees/` folders; Glob found neither and cannot list empty folders.
- The `architecture.md` claims from live probes (SubagentStart and SubagentStop context, CLAUDE.md reaching subagents) could not be rerun.
