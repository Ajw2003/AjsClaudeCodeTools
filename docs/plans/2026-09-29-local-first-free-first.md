# Local first, free first: scoping two new developer rules

**Status: scoping only. Nothing here is built yet.** Open decisions are listed at the end; the
rule text is not final until they are answered.

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
  and free disk on the working drive. Each check is standard-library Python or one shell probe
  per OS (`nvidia-smi`, `/proc/meminfo`, `sysctl`, `wmic`/CIM). A probe that fails prints
  "not detected" with the reason, never a blank (*Nothing fails silently*).
- On a remote session, don't present sandbox hardware as the target. Put a line in the profile
  saying the local-build budget comes from `handover-target.md`, and add a `## Hardware` section
  to that file's template.

**Tests (`verify.py`):** the profile names each hardware field; a faked missing `nvidia-smi`
gives "GPU: not detected (nvidia-smi not on PATH)"; the remote profile does not claim sandbox
hardware as the build target.

## Part B: free and open-source first, paid last

**The ladder**, tried in order. Each step down needs a one-line reason why the step above fails:

1. **Build or run it locally** with free, open-source tools, within Part A's hardware.
2. **A free, open-source service or tool**, self-hosted or hosted (plugins, skills, sites,
   workflows, libraries, anything else).
3. **Free but not open source** (a free tier of a closed service). *Whether this rung exists is
   decision 1.*
4. **Paid.** Only here, and it has to be labelled as paid, with the price looked up, not
   remembered.

**Reaching rung 4 on Pro/Max triggers a build-your-own estimate.** It's a quick sum, shown
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

**Where the plan tier comes from:** a new line in the machine-local record (`environment.md`
locally, `handover-target.md` on remote), `Claude plan: Max`, asked once, the first time rung 4
comes up, then recorded. It's never guessed (finding 3).

**Rule text (draft, about 250 characters):**

> ## Free and open-source first; paid is the last resort
>
> Local → free open-source → paid, each step down given a reason. Paid on Pro/Max: estimate
> building our own first. See `<plugin>/rules/detail/free-first.md`.

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

## Decisions I need from you

1. **Is "free but closed source" allowed before paid?** (Rung 3.) Example: a free tier of a
   hosted service with no open-source equivalent. *Recommendation: yes, below open source and
   labelled as closed.*
2. **Whose Pro/Max?** I've read "if they're on Pro or Max" as *your Claude plan*: building costs
   usage you already pay for, so compare that to the paid tool. The other reading is *the paid
   tool's own Pro/Max tier*. *Recommendation: your Claude plan, as drafted above.*
3. **Remote hardware.** On a cloud session, should "build locally" mean your PC (from
   `handover-target.md`) or the cloud sandbox Claude is running in? *Recommendation: your PC for
   anything you'll run; the sandbox only for Claude's own checks.*
4. **The 81 characters of room.** Either (a) trim an existing rule's core text by about 200
   characters, moving the words to its detail file (the 2.17.0 pattern), or (b) raise
   `verify.py`'s `inject` budget from 9,000 to 9,300, which is still under the 10,000 hard limit.
   *Recommendation: (a). The budget is there to leave room for future rules, and this rule
   shouldn't be the one that uses it up.*

Once these are answered, this becomes an executable plan for `@house-rules:executor`. The work
touches `house-rules.md`, two detail files, `hook.py`, `verify.py`, the plugin version and the
tier docs.
