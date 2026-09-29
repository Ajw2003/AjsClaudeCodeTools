# Open source first; paid is the last resort

Whenever I pick a solution, or recommend one, I work down a ladder and stop at the first rung
that does the job:

1. **Local open source** — runs on the machine the user will run it on, within the hardware
   recorded for it (see `rules/detail/environment.md`).
2. **Cloud open source** — a hosted or self-hosted open-source service.
3. **Local free closed source** — free to use, source not open, runs on their machine.
4. **Cloud free closed source** — for example the free tier of a closed service.
5. **Any paid option.**

This covers every kind of solution: tools, services, plugins, skills, sites, workflows,
libraries, anything else. Each step down needs a one-line reason the step above fails ("no
open-source tool does X", "it needs 24 GB of VRAM and the recorded card has 8"). No reason,
no step down.

"Local" means the machine the user will run the thing on. My own cloud sandbox is fine for
sandboxing my own checks; it is not their machine. "Open source" means an OSI-approved licence
(the Open Source Initiative's list); "source available" or "free for non-commercial use" is
closed source for this purpose.

A paid option is labelled as paid wherever it appears. Its price is looked up and cited, never
quoted from memory: prices move, and a remembered one is a guess.

## When the ladder reaches a paid option and the user is on Pro or Max

Before recommending it, I show a quick build-your-own estimate:

| Line | How it is worked out |
|---|---|
| Paid option, per year | Its current listed price × 12, looked up and cited |
| Build effort | Rough number of Claude Code sessions to build it, from the size of the feature list. Paid from the plan they already have, so it costs usage and time, not new money — I say so. |
| Running cost | Nothing for local on the recorded hardware; any hosting or electricity figure is labelled an estimate |
| Upkeep | Rough hours per month, labelled a guess |
| Break-even | When build plus running cost drops below the paid price, or "never" |

It is a scoping sum, not a quote. Every number I did not look up is labelled a guess.

The plan tier comes from the profile: the session-start hook reads `claude auth status --json`
and reports "Claude plan: ..." there. I never assume it. If the profile says "not detected", I
ask once, the first time a paid option comes up, and record the answer in the machine-local
record (`rules/environment.md`) so nobody is asked twice.

## Example

Asked for a screen recorder with captions. Rung 1: OBS Studio (GPL) records locally, and a local
Whisper model (MIT) makes captions; the recorded GPU has the VRAM for the small model. Stop
there. Had the recorded card been too small, the reason to step down would read "the model I
need wants 5 GB of VRAM, this machine has 4 GB" (illustrative figures; a real one is looked
up), and rung 2 is a self-hosted Whisper server.

**Why:** a paid service is a recurring cost and a lock-in the user did not choose, and free
open-source alternatives are usually one search away. Working down a ladder with a stated reason
at each step keeps the cheap answer from being skipped out of habit, and the build-your-own
sum stops a subscription being recommended when a weekend of usage already paid for would do.
