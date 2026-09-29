# Local first, free first: scoping two new developer rules

**Status: scoping. Nothing here is built yet.** Three of the four decisions were answered on
2026-09-29 (see "Decisions" at the end). The last one, which existing rule to trim, is waiting on
aj to pick between the two options measured below.

## What was asked (2026-09-29, in aj's words, lightly trimmed)

> Always try to build locally for the hardware we have, given it's known information after the
> first run because of the environment.md we generate. Furthermore, we only ever outsource to
> free open-source services, or recommend free open-source services, plugins, skills, sites,
> workflows, or any other solution. Paid alternatives are the last resort, not the first option.
> And if they're on a plan like Pro or Max, see if you can quickly scope and calculate what it
> might cost to build your own alternative.

## This is two rules, not one

| | Part A: local, sized to the hardware | Part B: free and open-source first |
|---|---|---|
| What it governs | Where work *runs* | What gets *picked or recommended* |
| Already partly covered? | Yes: "Find out what machine you are on, then build for that" (`rules/house-rules.md:5`) | No. Nothing in `house-rules.md` mentions cost, licences or paid services (searched 2026-09-29) |
| Recommended shape | Extend the existing rule and its detail file | New rule, new detail file |

Splitting them keeps each one short. They also fail in different ways, so each needs its own
test.

## What the code shows today (checked 2026-09-29, not assumed)

1. **The machine record has no hardware in it.** `_detect_environment()` in `scripts/hook.py`
   (around line 129) records OS, Python, git, shells and node, and nothing else. Its own footer
   tells Claude to go and discover "RAM, GPU, line-ending config" separately. So "the hardware
   we have" is *not* yet known after the first run. Part A needs the detector to record it.
2. **On a cloud session the sandbox is not your machine.** This session's sandbox has 4 CPUs,
   15 GB RAM and no GPU (`nproc`, `free -g`, `nvidia-smi` not found). None of that describes
   your PC. Hardware for "build locally" has to come from `rules/handover-target.md` on remote
   sessions. That is the same split the 2026-09-15 handover-target plan already made for shells.
3. **Claude Code cannot see your plan tier.** I searched `~/.claude.json` and the environment
   in this session. There is an organisation ID but no Pro/Max/Free field. So "if they're on
   Pro or Max" can't be detected. It has to be asked once and written down, like the handover
   target.
4. **The rules file is nearly full.** `inject` emits 8,919 characters. `verify.py`'s budget for
   it is 9,000 (Claude Code's hard limit is 10,000). **That leaves 81 characters**, and a new
   rule heading plus a two-line body is about 250. So something has to give. See decision 4.

## Part A: build locally, sized to the recorded hardware

**Rule change (edit in place, `house-rules.md` "Find out what machine you are on"):** add one
clause: *Recorded hardware (CPU, RAM, GPU, disk) is the budget: run it locally within that, and
go remote only if the hardware can't.*

**Detail file (`rules/detail/environment.md`):** a new section on what "fits" means. For example:
a model that needs more VRAM (graphics-card memory) than recorded doesn't fit; a build that
needs more free disk than recorded doesn't fit. When it doesn't fit, say which number is short,
then fall to Part B's ladder for the remote option.

**Code (`hook.py`):**
- Extend `_detect_environment()` with CPU model and core count, total RAM, GPU name and VRAM,
  and free disk on the working drive. **Detected on whatever machine the plugin runs on, nothing
  hardcoded**, so it works for anyone who installs it (decision 2):
  - CPU cores and free disk: standard-library Python (`os.cpu_count()`, `shutil.disk_usage()`),
    the same on every OS.
  - RAM: `/proc/meminfo` on Linux, `sysctl hw.memsize` on macOS, `GlobalMemoryStatusEx` through
    `ctypes` on Windows. All built in, nothing to install.
  - GPU: `nvidia-smi` when it's on PATH; otherwise `system_profiler SPDisplaysDataType` on macOS
    and `Get-CimInstance Win32_VideoController` on Windows. Windows reports at most 4 GB of VRAM
    through that call, so a reading of exactly 4 GB is marked "may be higher".
  - Each probe has a short timeout, so a slow machine can't hold up session start. A probe that
    fails or times out prints "not detected" with the reason, never a blank (*Nothing fails
    silently*).
- On a remote session, don't present sandbox hardware as the target. Put a line in the profile
  saying the local-build budget comes from `handover-target.md`, and add a `## Hardware` section
  to that file's template.

**Tests (`verify.py`):** the profile names each hardware field; a faked missing `nvidia-smi`
gives "GPU: not detected (nvidia-smi not on PATH)"; the remote profile does not claim sandbox
hardware as the build target.

## Part B: free and open-source first, paid last

**The ladder** (aj, 2026-09-29), tried in order. Each step down needs a one-line reason why the
step above fails. It covers every kind of solution: tools, services, plugins, skills, sites,
workflows, libraries, anything else.

1. **Local, open source**: runs on this machine, within Part A's recorded hardware.
2. **Cloud, open source**: a hosted or self-hosted open-source service.
3. **Local, free but closed source**.
4. **Cloud, free but closed source**: for example, the free tier of a closed service.
5. **Paid**, any kind. Only here, labelled as paid, with the price looked up, not remembered.

Claude's own cloud sandbox is fine for Claude's own checks and sandboxing. "Local" in this ladder
means the machine the user will run the thing on.

**Reaching rung 5 on Pro/Max triggers a build-your-own estimate.** It's a quick sum, shown
before the paid option is recommended:

| Line | How it's worked out |
|---|---|
| Paid option, per year | Its current listed price × 12, looked up and cited, never from memory |
| Build effort | A rough number of Claude Code sessions to build it, from the size of the feature list. It's paid for by the plan you already have, so it costs usage and time, not new money. Say which. |
| Running cost | Nothing for local on recorded hardware; any hosting or electricity estimate, stated as an estimate |
| Upkeep | Rough hours per month, stated as a guess |
| Break-even | When build plus running cost falls below the paid price, or "never" |

It's a scoping sum, not a quote. Every guessed number is labelled as a guess (*Evidence before
claims*).

**Where the plan tier comes from: detected, never hardcoded** (decision 2). At session start,
`hook.py` runs `claude auth status --json` and reads its plan field if it has one. In this cloud
session the output has no plan field at all (checked 2026-09-29: it lists `loggedIn`,
`authMethod: oauth_token`, `apiProvider` and two directories, nothing else). **Unverified:**
whether a normal local claude.ai login reports the plan there. That is the first thing the build
checks on a real machine. If no source reports it, the profile says "Claude plan: not detected
(why)", and Claude asks once, the first time rung 5 comes up, then records the answer in the
machine-local record. It is never assumed.

**Rule text:** the tested draft is under "The trim" at the end.

**Detail file `rules/detail/free-first.md`:** the ladder, the estimate table, worked examples,
and what counts as "open source" (an OSI-approved licence, the Open Source Initiative's list).

**Hook or guard?** The repo's convention (CLAUDE.md) is that a rule with a shell signature gets
a `guard` pattern. This one mostly doesn't have one: recommending a product is prose, not a
command. The only shell-shaped edge is installing a paid SDK or CLI, and there's no reliable
list of which packages are paid. **Recommendation: no guard.** Add a `verify.py` phrase check
that the rule and its detail file exist and agree, like the other rules' drift checks.

## Out of scope unless you say otherwise

- A maintained list of paid vs free products. It would go stale, so the rule makes Claude look
  it up each time.
- Blocking paid-service commands in `guard`.
- Changing Claude Code's own model or plan choice. This rule covers what Claude *recommends and
  builds*, not the subscription it runs on.

## Decisions

Answered by aj on 2026-09-29:

1. **The ladder** is local open source → cloud open source → local free closed source → cloud
   free closed source → any paid option. Written into Part B above.
2. **Detect, don't hardcode.** The plugin is meant for anyone who installs it, so hardware and
   plan tier are both detected at runtime (Parts A and B above), never written in for one person.
   The Pro/Max question is read as *the user's Claude plan*, detected as described.
3. **Cloud sessions.** "Local" means the machine the user will run it on. Claude's own cloud is
   fine for sandboxing Claude's own work.
4. **Make room by trimming an existing rule, but show the choice first.** Measured options below.

### The trim: two measured options, waiting on aj

Both options were applied to scratch copies of the repo together with the new rule and the Part A
clause, then measured with the real `inject` hook and run through the full `verify.py` suite.
Today `inject` is 8,919 characters against a 9,000 budget.

**The new rule text used in both trials** (about 190 characters once injected):

> ## Open source first; paid is the last resort
>
> Local OSS → cloud OSS → local free closed → cloud free closed → paid; each step down reasoned.
> Paid on Pro/Max: estimate building our own. See `<plugin>/rules/detail/free-first.md`.

Plus, in the environment rule: *"Detected hardware is the local budget."*

**Option A: tighten three existing rules' wording, dropping nothing.** Result: 8,949
characters, 51 under budget. `verify.py` exit 0.

| Rule | Now | After |
|---|---|---|
| Edit in place | "Changing only the lines that need to change is default. A wholesale rewrite needs approval by name: say what's discarded, why in-place won't do." | "Change only the lines that need it. A wholesale rewrite needs approval by name: say what's discarded and why." |
| Edit in place | "Port, rewrite, restructure, migrate: inventory the original from its code first — keep/change/drop, shown before building; verify against the original; name every drop, an issue per deferred re-add." | "Port, rewrite, restructure, migrate: inventory the original first, shown before building." The removed steps are already in `rules/detail/parity-inventory.md` (steps 2 to 5). |
| Handover | "My shell is not theirs — run each command in their shell, read the real output. Can't → say untested. Required command: hand it over, then wait." | "Run it in their shell, read the output; can't → untested. Required: hand over, wait." |
| Handover, "The card" | Three lines pointing at the output style and the template | "Shape: the forced `handover-cards` output style. Template, publish-a-page rule: `<plugin>/rules/detail/handover-command.md`." |

The cost: the port steps are shorter in the always-loaded text. Claude only sees the full
five-step list when it opens the detail file. The `delegate` hook still adds the keep/change/drop
reminder to any approved port plan that lacks one (`verify.py`'s "parity note" cases pass).

**Option B: move the Unity rule out of every session and into Unity projects only.** "Unity work
starts with the Unity plugin and the Unity CLI" moves from `house-rules.md` to the end of
`rules/standards/csharp-unity-standards.md`. That file is only loaded when a project has Unity
markers (`ProjectSettings/ProjectVersion.txt`, `Assets/`, or a `.csproj`). Result: 8,968
characters, 32 under budget. `verify.py` exit 0. This suits the "widely usable" goal best, since
people who don't use Unity stop paying for a Unity rule.

**But Option B isn't safe as measured.** In a fake Unity project, the `standards` hook already
emits **9,832 characters today**, over its own 9,500 budget. With the Unity rule added it reached
**10,132, over Claude Code's hard 10,000 limit**, so the end would be cut off. `verify.py` never
caught this because it only measures `standards` in this repo, which has no Unity markers. So
Option B also needs about 250 characters trimmed from `csharp-unity-standards.md`, plus a new
`verify.py` case that measures `standards` in a Unity project. **That missing check is a real gap
whichever option is picked.** Unity projects are already over budget today.

**Recommendation: Option A now.** Separately, fix the Unity standards overrun and add its
missing check as its own change, since it is broken either way.

Once the trim is picked, this becomes an executable plan for `@house-rules:executor`. The work
touches `house-rules.md`, two detail files, `hook.py`, `verify.py`, the plugin version and the
tier docs.
