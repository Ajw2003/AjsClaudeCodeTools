# Every wait has a deadline

Before any wait I state four things: what I wait for, how I will check it, when it counts as done,
and the deadline. Then I check first at one minute and every minute after, with
`scripts/waitfor.py`, run in the background with a timeout. It prints a line per check and exits
done 0, failed 1, stalled 2, timed out 3, bad usage 4.

A wait that is stalled (3 quiet checks in a row) or past its deadline **ends**: I stop waiting, say
plainly what is still unknown, and carry on. A background launch always carries a timeout (the
guard refuses none, or one over 60,000 ms). I never hand-write a sleep loop.

**Numbers** live in `rules/waits.json`: first check 60 s, interval 60 s, stalled after 3 quiet
checks, foreground limit 60 s, every deadline (command, agent, build, ci) 60 seconds, one segment; `long_runners` lists the known long runners.
Change them there (or with `HOUSE_RULES_WAIT_*` environment variables).

**Example:** "Waiting for the CI run on this branch; I check `gh run view` for `completed`; done
means conclusion `success`; deadline 60 s per segment." I launch
`waitfor.py ...` in the background with a timeout, read its line at one minute, and at the deadline I
report "CI still unknown" and move on.

**Why:** aj: anything that lets a session wait for an extended period or indefinitely kills
productivity. A hook cannot interrupt a tool that is already hung, so the launch is the only place
a limit holds.

## Verify a wait, then leave it

I never set a timer, start a wait loop, or leave a background task running until two things are
verified:

1. **The name it waits on is real.** I read the exact identifier it waits on — test class full
   name, process, file, log marker — from the source, and check the watcher's matcher actually
   accepts it.
2. **It is working.** One direct status check shows the task started and the watcher reads that
   status correctly — for example, the verdict script run once against the current status gives
   a sensible answer.

A wait's output streams live. I never pipe a wait loop through `tail` or `head`, which hides
everything until it exits; `guard` prompts when a command does.

**Why:** a test-runner wrapper was called with a bare class name, `CarryFeelTests`, while its
verdict script matched results by full-name prefix, `Plunderspell.Tests.CarryFeelTests…`. It
reported "running" for its whole 10-minute timeout on a run that had finished in 62 seconds, and
the wait was piped through `tail`, so nothing showed until it ended. A wait that can never see its
own completion is a silent failure.

## Segments: nothing runs over a minute

Before waiting on anything over 60 seconds I write a segment plan, one line per segment:

| Part | What it holds |
|---|---|
| name | what this segment does |
| command | the one command it runs |
| input check | how I check, in seconds, that its input is there |
| output | what it leaves and how I read it |
| deadline | 60 seconds |

I run segment 1, read its output, then start segment 2; a failed segment stops the later ones.
The launch guard refuses a foreground or background launch over 60 seconds, and a known long
runner (`long_runners` in `rules/waits.json`) with no timeout counts as over 60 seconds.

**Cannot split:** is the only way past that refusal, for a genuine impossibility to split the work
(one engine build, one CI run). Put it in the launch description:

    Cannot split: check: <the command you ran to see whether it splits>; evidence: <what it actually returned>; logic: <why that evidence means it cannot be split>; progress: <the signal you will read each minute>

Slowness or habit is never a reason; "it takes a while" is refused. The reason follows C5 and C3 in
`rules/detail/roadblocks.md`: the check run, its evidence, the logic, and a progress signal for each
minute. The guard checks the four parts are present; the Stop judge checks them against the real tool calls.
