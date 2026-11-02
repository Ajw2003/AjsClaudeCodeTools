# Plugin split

How house-rules becomes nine plugins plus a shared library. Approved 2026-11-02
(`docs/6-decisions/Decisions.md`, "Design approved: plugin split"); proposal
`docs/plans/2026-11-02-plugin-split.html`. Nothing is built yet: this doc is the target.

## The principle

No rule is optional. Every rule is enforced by code, not left to the agent. A check that causes
friction is reworked, never removed or switched off (`docs/6-decisions/Decisions.md`, "The plugin
split: no rule is optional"). The 21 `HOUSE_RULES_*` switches that turn a check off are removed;
the 17 that set a path, URL or number stay.

## Target structure

| Plugin | Takes from house-rules today |
|---|---|
| Shared library (no hooks) | `core.py` plumbing: `read_payload`, `emit`, trace, the `register_*` links, transcript and git helpers; `run.sh`; `make_page.py` and its templates |
| Rule enforcement | `inject`, `showrule`, `subagentrules`, `scope`; the repeat-failure lock (choice 6A) |
| Safe work | `safe_git.py` (guard, guardwrite, guardgithub, creditcheck, branchnudge, prompttimer/promptran); autosave, commitgate, worktreesweep, subagentcommit from `delegation.py`; no local paths; the planned secret scrub (`session_triage.py`) |
| Design loop | `design_loop.py`: approval lock, stages, pages, QA, issue workflow, close guard, issuelist, closablemerge, labels |
| No hiding | artifact location, fails silently, what prompted me; announce, audit, userpromptaudit, verdict, subagent ledger, rclink from `delegation.py`; `session_ledger.py`, `stallcheck.py`; new research-citation check |
| Living docs | `docs.py`: docstiers, harvest, commit-time docs reminder; archivist, docref, project-docs skill; plain-docs |
| Code standards | `standards` hook, `rules/standards/`, build-alone, open source first; new code checks |
| Check your work | green suite, shim compiles, reported update, visual check, runnable, parity, reviewer; handover rule, step cards, `handover-cards` output style; new screenshot and video tools |
| No trust memory | read docs first, evidence check (`handover_evidence_check`), stale-memory warning, `profile`; new docs-freshness check |
| Accessible AI | `clarity.py`, `writing.py`, editor, voice, plain summary, the 160-word page rule |
| `claude-agent-router` (existing) | delegation rule, scout/builder/reviewer, agentcap |

## Known risks

- The 2.74.0 restructure was reverted because a shared settings gate refused every tool
  (`docs/3-state/ProjectState.md`, 2026-10-28). The library has no hooks, so it cannot do that.
- Today one Stop hook gathers every part's end-of-reply checks. After the split each plugin has its
  own, so several could block the same reply; the repeat-failure lock has to count across plugins.
- `guard` calls the docs reminder (`register_docs_status`) at commit time: 17 `register_*` calls link
  the parts today and each needs a cross-plugin route.
- Plugin `dependencies` in `plugin.json` is not yet verified to install the library.
