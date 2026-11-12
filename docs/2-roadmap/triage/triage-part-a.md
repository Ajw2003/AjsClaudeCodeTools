# Triage, part A (issues #41 to #302), 2026-11-09

Made by a read-only scout from `open-issues-part-a.json`, with the code searched for each claim. Format:
`#N | theme | verdict | reason`. The themes and verdicts are listed in `README.md` beside this file.

#41 | T9 | KEEP | EVENTS table (hook.py:264) maps events only; fail-closed/loud policy still lives in each handler.
#42 | T9 | UNSURE | Prompt-field regex consolidation not confirmed.
#43 | T9 | UNSURE | Standards detection/prose seam not confirmed.
#44 | T5 | KEEP | verify.py has --parts (verify.py:7) but no per-check name filter.
#45 | T10 | KEEP | No CONTEXT.md or docs/adr.
#46 | T5 | KEEP | checks/docs.py:542 and checks/delegation.py:653 still forbid permissionMode/hooks/mcpServers.
#62 | T9 | KEEP | Research only.
#69 | T12 | KEEP | Research on the superpowers workflow.
#94 | T2 | SUPERSEDED #110 | Same ask as #110.
#95 | T12 | KEEP | Cost-benefit research.
#102 | T2 | KEEP | No final plain-language pass before push.
#103 | T2 | SUPERSEDED #110 | Same plan-to-issues request.
#107 | T2 | KEEP | Parent; children #110, #119, #128 open or partial.
#110 | T2 | KEEP | Plan-approval-to-issues path not confirmed (design_loop.py:85-87 asks for issues).
#116 | T13 Unity workflow | KEEP | Unity project-choice behaviour.
#117 | T10 | KEEP | No "never hardcode" rule text.
#119 | T2 | SUPERSEDED #128 | Replaced by the step split under #128.
#120 | T8 | KEEP | stallcheck.py exists (threshold 300, :30); reminder text unchanged.
#122 | T8 | DONE | stallcheck.py:134-146 re-alerts each threshold.
#123 | T8 | KEEP | No flags still watches all sessions (stallcheck.py:114-115).
#124 | T8 | KEEP | No STALLED-line procedure in rules.
#125 | T12 | KEEP | No executor agent rule.
#127 | T8 | KEEP | stallcheck.py:50-59 has no dedupe by agent id.
#128 | T2 | KEEP | Parent; commitgate covers only worktree-agent branches (delegation.py:1527).
#129 | T2 | KEEP | commitgate scoped to worktree-agent branches.
#130 | T2 | KEEP | No docs/plans trigger in delegation.py.
#131 | T1 | DUP #141 | Same ask as #141.
#132 | T1 | KEEP | Code uses "AjsAgent completed this" (design_loop.py:1651); title names the old label.
#134 | T3 | SUPERSEDED #197 | Non-default-branch commits no longer prompt (safe_git.py:75-76).
#136 | T11 | DUP #196 | Same blocked-builder prompt problem.
#137 | T5 | KEEP | No call-operator (&) guidance in handover-command.md.
#138 | T12 | KEEP | No Unity CLI JSON guidance in agents/.
#139 | T12 | KEEP | No one-run-per-check rule.
#140 | T6 | SUPERSEDED #406 | The 95%-usage ask became #406 (its body says it replaces #140).
#141 | T2 | KEEP | No ask-to-close step as described.
#142 | T11 | KEEP | Parent; prompt timer built (safe_git.py:1322-1330); children open.
#144 | T11 | DONE | prompttimer registered (hooks.json:326), handler at safe_git.py:1533.
#145 | T11 | UNSURE | Whether the issue list shows timed-out actions is unread.
#146 | T11 | UNSURE | Wording present (destructive-action.md:65); docs and version unchecked.
#147 | T11 | KEEP | Overnight real-session check never run.
#149 | T11 | KEEP | Desktop app keeps the dialog open after refusal; unverified.
#150 | T8 | KEEP | Phone progress visibility.
#151 | T11 | DONE | AskUserQuestion and ExitPlanMode exempt from the timer (safe_git.py:1330).
#152 | T11 | KEEP | Next-prompt wait after a timeout not confirmed.
#153 | T3 | DONE | Destructive steps run unasked only off the default branch and when pushed (safe_git.py:78-79, :110).
#155 | T1 | KEEP | Step-card or multiple-choice UI routing.
#156 | T3 | KEEP | No branch delete after merge; worktreesweep covers worktrees only.
#158 | T4 | KEEP | Per-task plain summary with visual check not built.
#159 | T11 | KEEP | Worker-restart timer behaviour unverified.
#160 | T12 | KEEP | Growing test count not addressed.
#161 | T13 art-pipeline | KEEP | Exists only as origin/claude/art-pipeline, not on main.
#162 | T13 art-pipeline | KEEP | Not on main.
#163 | T13 art-pipeline | KEEP | Not on main.
#164 | T13 art-pipeline | KEEP | Not on main.
#167 | T13 art-pipeline | KEEP | PR 166 status unverified.
#168 | T13 art-pipeline | KEEP | Code not on main to check.
#169 | T13 art-pipeline | KEEP | Not on main.
#170 | T13 art-pipeline | KEEP | Not on main.
#171 | T13 art-pipeline | KEEP | Not on main.
#172 | T12 | KEEP | No failed-task recovery steps in agents/.
#173 | T11 | SUPERSEDED #197 | Non-default-branch commits and pushes run unasked (safe_git.py:75-76).
#174 | T7 | UNSURE | Plugin credits "Edens Agent" (labels.py:17), not "AJ's agent"; confirm the wanted name.
#175 | T7 | DONE | AjsAgent/ prefix (core.py:2094); label defined (labels.py:17).
#176 | T7 | DONE | Cloud claude/ to AjsAgent/ switch at session start (safe_git.py:277-291).
#177 | T7 | UNSURE | Trailer is Edens Agent (delegation.py:1371); author name unverified.
#179 | T7 | KEEP | Attribution setting written by tools/install.py only.
#180 | T13 Focus Deck | KEEP | Belongs to the focus-deck-app repo.
#181 | T7 | KEEP | No retro report script.
#182 | T7 | KEEP | Depends on #181.
#183 | T13 Eldritch goose | KEEP | Parent; children open.
#184 | T13 Eldritch goose | KEEP | Not built.
#185 | T13 Eldritch goose | KEEP | Not built.
#186 | T13 Eldritch goose | KEEP | Not built.
#187 | T13 Eldritch goose | KEEP | Not built.
#189 | T3 | KEEP | Attribution guard tests only the plain -c form (checks/safe_git.py:1127).
#191 | T7 | KEEP | Cloud PR credit unverified.
#192 | T3 | SUPERSEDED #197 | Non-default-branch commits no longer gated.
#194 | T4 | KEEP | Step-card check on non-shell steps not found.
#196 | T11 | UNSURE | #197 and #198 built; docs and version (#199) unchecked.
#197 | T3 | DONE | Non-default branches run unasked; default refused (safe_git.py:75-76, :420-423).
#198 | T11 | DONE | Refused-not-asked text when nobody can answer (safe_git.py:1404, :1443, :1477).
#199 | T10 | UNSURE | Rule text at destructive-action.md:65; version and docs unchecked.
#200 | T3 | KEEP | Second-line rm/nohup bypass not tested.
#201 | T12 | KEEP | agentcap state (delegation.py:890-939) has no lock.
#202 | T5 | KEEP | docref failure not reproduced.
#203 | T3 | DONE | cd counts only where a command starts (core.py:2118-2120).
#204 | T9 | UNSURE | run.sh has an interpreter cache (run.sh:54); per-call compile not measured.
#205 | T5 | KEEP | Silent path for credit check and issue gate with no Python not confirmed.
#206 | T9 | KEEP | _command_dir (core.py:2135); second copy not located.
#215 | T5 | KEEP | Not reproduced; no fix found.
#218 | T12 | KEEP | Parent; no per-frame gate.
#219 | T12 | KEEP | Unity standards lack a per-frame-only rule.
#220 | T12 | KEEP | No per-frame refusal in the write guard.
#221 | T12 | KEEP | No architecture-first step in agents/.
#222 | T12 | KEEP | No no-polling rule in delegation briefs.
#224 | T10 | DONE | Show-don't-tell rule in the rules; detail at rules/detail/show-dont-tell.md.
#228 | T10 | KEEP | Audit exists (docs/audits/2026-10-16-plugin-audit/); per-rule check gate not built.
#244 | T10 | KEEP | No per-turn change log hook.
#260 | T11 | KEEP | Prompt readability.
#273 | T1 | KEEP | _loop_stop_line (design_loop.py:1167) has no repeat limit.
#281 | T4 | DONE | 160-word threshold (core.py:2879); only aj's "no page" skips.
#282 | T4 | DONE | LONG_REPLY_WORDS = 160 (core.py:2879).
#283 | T4 | KEEP | Checks report only on retry (hook.py:123).
#284 | T4 | KEEP | Counts by file time (writing.py:132); clone exclusion unconfirmed.
#285 | T3 | KEEP | Refusals still on timeout paths (safe_git.py:1437).
#287 | T7 | KEEP | Name hard-coded (core.py:2094); no config.
#296 | T1 | KEEP | No non-git handling for design approvals.
#297 | T4 | KEEP | No PR how-to-test/what's-next check.
#298 | T4 | KEEP | No PR body heading check.
#299 | T4 | KEEP | No test steps on QA pages.
#300 | T4 | KEEP | No reply check for PR test/next.
#301 | T10 | KEEP | No matching rule text.
#302 | T4 | KEEP | Before/after optional (show-dont-tell.md:134).

Clusters: #136 duplicates #196; #134, #173 and #192 superseded by #197; #94 and #103 superseded by #110; #119
superseded by #128; #131 duplicates #141; #120 and #122-#127 are the stall-check cluster.

Correction after checking: the scout marked #140 KEEP; #406's body says it replaces #140, so it is SUPERSEDED #406.
