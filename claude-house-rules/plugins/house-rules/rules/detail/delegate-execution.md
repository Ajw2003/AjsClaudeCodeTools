# Once the approach is decided, delegate the execution


Planning and executing are different jobs and they do not want the same model. Deliberating an
approach is worth an expensive model; typing out steps that have already been decided is not.

So when a plan is settled — approved out of plan mode, or simply agreed in conversation — I hand
the implementation to a subagent with the decided steps written out, instead of implementing it
myself on the planning model. One subagent per issue, never per step. Three tiers, each with a
short tool allowlist so a spawn starts small: `@house-rules:scout` (haiku; Read, Grep, Glob) for
read-only lookups; `@house-rules:builder` (sonnet) for one issue's chunk of work, three steps or
fewer; `@house-rules:reviewer` (opus) for a second opinion on a finished diff, only when asked or
after a builder failed twice. The tier files set only model, tools and role; the job goes in the
spawn prompt. One at a time, never more than two running (the `agentcap` hook denies a third,
ignoring records older than 45 minutes; `HOUSE_RULES_AGENTS=off` disables it). Subagents do not
start subagents: the tiers omit the `Agent` tool and `agentcap` denies a spawn made from inside one. I do not re-plan inside the delegation;
if the plan turns out to be wrong, that comes back to me, it is not quietly redesigned down there.

The one exception is a count, not a judgement call, because a judgement call is one I talk myself
past: I skip the delegation only when the plan touches one file AND is three steps or fewer. Taking
that exception means saying so in one line that names the count — an exception used silently is
indistinguishable from the rule being forgotten, which is how this one kept failing.

**A multi-group plan is one delegation per group.** The reminder fires once, when the plan is
approved; the rule does not expire when group 1 comes back. Absorbing the remaining groups inline
because nothing re-fired is the specific failure this sentence exists to prevent.

**This applies in every session, not just ones that used plan mode.** Auto and accept-edits
sessions never cross a plan-mode boundary, and the desktop Code tab takes its model from the
picker rather than from any settings file, so nothing switches models on my behalf there. The
delegation is the only part of the split that works on every surface.

Spawning a subagent on my own initiative is otherwise gated behind either the user explicitly
asking or the target agent's own description saying to use it proactively — so
each tier agent's description is written to say exactly that. A generic instruction like
"implement the plan" is not itself an explicit ask, and without that description marking, the
gate would win and I would execute in the main loop instead, silently defeating this whole
section.

**Why:** the `opusplan` setting only covers the CLI and the IDE, and only at the plan-mode
boundary. Everywhere else, a whole implementation runs on the planning model and the user pays
for reasoning that was already finished. And the delegation itself would silently not happen
without the proactive-use marking, for the same reason a hook cannot set a model: the mechanism
that makes the split real is not obvious from reading the rule text alone.

**A delegation to `@house-rules:builder` (or any implementation delegation) that touches more
than one file, or changes behavior rather than just reading, passes `isolation: "worktree"` on
the `Agent` call.** Two concurrent delegations must never be able to land in the same working
directory.

**Why:** two `Agent` calls delegating implementation work once ran against the same working
directory at the same time, neither passing `isolation: "worktree"`. Both edited the same files
concurrently and corrupted the checkout. Two isolated worktrees cannot clobber each other
regardless of any later judgement error, so this is mechanical, not a judgement call.

A subagent stopping is not the same as its task finishing, and a `SubagentStop` or background-task
notification reporting only a status update ("I've launched...", "I'll report back...") is not a
report of concrete deliverables. Before treating a delegation as done, or relaunching one, check
whether a copy of it is already running via `ListAgents`/`TaskOutput` — the plugin cannot track
this itself (no hook keeps state between invocations, and that constraint is intentional), so the
live registry the host app already maintains is the source of truth.

**Why:** the same incident that produced the worktree-isolation rule above also involved a hollow
"stop" being read as real completion, which is part of how a duplicate dispatch happened in the
first place.

**A subagent commits its own work as it goes**, scoped to what it changed, on its own branch or
the worktree opened for it — the same rule as mine. The `subagentcommit` hook sends it back once
if it tries to finish with files it wrote still uncommitted.

**A subagent's work is saved while it runs, not only when it finishes.** On its own
`worktree-agent-` branch, every edit is snapshotted to `refs/house-rules/autosave/<branch>` and
pushed to `origin` once a minute. Edits are blocked once 3 files are uncommitted; if it ignores
that once, or goes 10 minutes without a commit, the hook commits for it. When I launch one in the
background I schedule a check-in every 10 minutes, and on every wake `worktreesweep` commits any
subagent worktree left untouched that long. To recover a killed subagent's work from its save
point: `git fetch origin 'refs/house-rules/autosave/*:refs/house-rules/autosave/*'` (skip it if
the save is only local), then `git worktree add -b recovered <path> refs/house-rules/autosave/<branch>`.

**Why:** on 2026-09-29 a safety-classifier outage killed a subagent mid-run. `SubagentStop`
never fired, so nothing checked its work, and it sat uncommitted until the parent noticed.

**When I tell a subagent not to run git, the commit is mine after it hands back.** Its files are
my uncommitted work from that moment, under the same commit rule as anything I wrote myself. The
`audit` summary names any file the subagent wrote that is still uncommitted.

**Why:** three subagent runs in one task were each told "no git commands", correctly, and the
parent never committed either. Every final summary reported "nothing is committed" as a neutral
status line until the user asked why.
