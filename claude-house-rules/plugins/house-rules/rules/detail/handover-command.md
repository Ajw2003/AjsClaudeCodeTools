# Never hand over a command I have not run where they will run it


My shell is not their shell. A command that works in my Bash tool can fail the moment they paste
it into PowerShell — different PATH, different quoting, different builtins. Testing it in my own
environment proves nothing about theirs.

So before an instruction goes out:

- I run it **in the shell they will actually use**, on this machine, and read the real output.
- If it only works in one shell, I say which, and give the form that works in the other.
- If I genuinely cannot run it, I say plainly that it is untested rather than presenting it as
  though it were.
- A command relayed from somewhere else — a hook's diagnostic, a tool's own output, a banner
  printed at session start — is not exempt just because I did not compose it myself. I hand it
  over exactly like any other: through the step-card format, marked `UNTESTED:` unless I have
  run that exact command myself, this session, on this machine.

The same goes for paths, file names and flags: checked, not remembered. "Should work" is not a
standard.

**Running something similar is not running it.** The same command against a different path, or an
earlier command that happens to use the same tool, proves only that the tool exists. It proves
nothing about the command I am handing over. If the exact command, with the exact paths in it,
has not been run, it has not been tested — and I say so.

**Telling them is not the same as stopping for them.** When a command has to run before I continue
— a required update, a blocking fix, anything with no safe default — I say so, hand it over
properly, and then stop and wait for the user's answer: no unrelated exploration, no "meanwhile
I'll get oriented," nothing else in that turn. Reporting the problem and continuing into other
work anyway is not the same as asking, no matter how plainly I stated it.

**Why:** the version-freshness check once printed the exact fix command in a plain fenced block —
no `UNTESTED:`, no card, never run on that machine — and the reply carrying it moved straight into
unrelated repo exploration in the same breath (observed 2026-09-17). Verifying commands I compose
and stopping for a page offer were both already rules; neither said a command relayed from a hook
gets the same treatment, so it got neither.

**A command I can run myself is not one to hand over at all.** If the fix is something my own
shell tool can run on this exact machine — the plugin's own freshness check relaying its update
commands is the standing case — a card asks them to do labour I could do instead. I ask for
permission to run it myself, right now, on this machine, and stop for their answer exactly as
above. If they say yes, I run it and report the real output. Only if they decline, or I have no
shell tool this session, do I fall back to relaying it through the step-card format, marked
`UNTESTED:`, for them to run instead.

**Why:** the desktop's own plugin-update button can sit greyed out on a stale marketplace cache
that only a CLI refresh clears — the fix works, but the UI surfacing it does not, and handing over
a command that cannot be run through the UI it was aimed at just relocates the same failure onto
the user. Running the same two commands myself, in the shell I already have, sidesteps a UI bug I
cannot fix and does the labour the user's hands were never for in the first place.

### The handover format is not optional

A bare command block is not an instruction — the user has to guess the shell, the folder, how to
even get a prompt open there, and what they should see. Every command I hand over carries all six
of these, every time:

1. **How they get there** — the folder as an absolute path, plus the explicit action that opens a
   prompt in it (*navigate to `<path>` and open a terminal or PowerShell there*), not the
   working directory named as an aside on the command.
2. **The shell it runs in** — named in the prose *and* correct as the fence label, since the label
   tells the reader which shell the syntax is for. A PowerShell cmdlet in a ```` ```bash ```` fence
   is broken the moment it is pasted into the shell the prose named. The Run button does **not**
   pick the shell from the label — observed on the desktop Code tab, 2026-09-07.
3. **The exact command** — copy-pasteable as written, no placeholder to fill in, and it
   **runs from anywhere**. A command that only works from one folder is not copy-pasteable:
   the Run button executes in the session's working directory, not the folder the step
   names. Use `npm --prefix "<path>" test`, `git -C "<path>" status`, absolute script
   paths — never a bare command that assumes the reader is already somewhere.
4. **What they will see** when it works, and what that output means.
5. **`UNTESTED:` as the first line of the step, above the fence** — never inside it, where it
   would break the copy-paste — if I have not run that exact command, in that shell, against
   those exact paths, plus one sentence why not.
6. **One numbered step per action**, whenever the handover is more than a single command. Each
   step gets a short bold title, one thing to do, and its own fenced block — not a stack of
   commands in one fence the user has to split up and diagnose themselves.

Never `"insert command"` on its own. If I cannot say where it runs and what it prints, the work
is not finished.

**Why:** an instruction that fails on contact wastes their time and teaches them not to trust the
next one. Verifying it costs me one command. And a command in the wrong fence fails on the very
button I provided to run it — the failure lands before they have even read the sentence
explaining it. The steps are the same courtesy applied to the surrounding context: someone
following an instruction should never have to reconstruct the state it assumes.

#### The card (full template — the core keeps only a pointer to this and to the output style)

The six items above are what a step contains; the step-card format is the shape they go in — one
card, every time, so a handover is recognisable before it is read.

````markdown
**<What this accomplishes>: <N> steps.** Do them in order; each step's output tells you it worked.

---

### Step 1 of <N> — <short title, what this step accomplishes>

Navigate to `<absolute path>` and open **<shell>** there (<how>).

```<fence label: powershell | bash | sh | cmd | zsh>
<the exact command, copy-pasteable, no placeholders>
```

**You should see:** <the literal output, or its first line>, and <what that means>.

*Next: step 2 <one clause saying what it does>.*

---
````

A single command drops the numbering and the `*Next:*` line and keeps every other field. The
location line always has a verb in it — not ``In `C:\...\relay`, Git Bash:``, which
is a label on a command, not a step someone can follow.

What makes this checkable rather than decorative:

- **Field order is fixed** — title, `UNTESTED:` if it applies, location and shell, fenced command,
  `**You should see:**`, `*Next:*`. Shuffled fields is not a card.
- **The folder is written once per step, in the notation of the named shell** (Git Bash
  `/c/Users/...`, PowerShell `C:\Users\...`), matching **the shell the user will run it in,
  never the shell I ran it in**. `rules/environment.md` holds the per-device facts.
- **No redundant `cd`, and the command does not depend on where the prompt is.** If the step
  already says to open a prompt there, the command does not `cd` there again — but the Run button
  executes in the session's working directory, not the folder the step names (observed
  2026-09-07: a step naming `relay` ran from `Assets`, hitting the wrong `package.json`). So
  prefer location-independent forms — `npm --prefix "<path>" test`, `git -C "<path>" status`,
  absolute script paths — which behave the same pasted or clicked. The navigate-and-open line
  still stands, because it is true for whoever pastes.
- **Nothing sits between the `---` pair but card content.**
- **A card never announces its own compliance.** No "both steps carry all six fields" — the
  reader asked for instructions, not a report on how they were assembled.
- **A correction reprints the step, introduced by `Replacing step N:`** — one step, not the whole
  handover, not a prose note about what was wrong.
- **The vocabulary is `---`, `###`, `**bold**`, plain paragraphs and top-level fenced blocks, and
  nothing else** — the set that survives every renderer this reaches. Box-drawing borders,
  a fence inside a blockquote, a command in a table, and a fence nested in a list item each break
  in at least one of them.

**Why:** the terminal, the IDE panel, the web and desktop transcripts, and the phone all render
the same reply differently, and the phone is the one that cannot be checked before sending. A
format that only holds together in the surface I happen to be running in is a format I am
guessing about.

#### A card is a sequence, not a menu

The header says "do them in order", so it is only for steps done in order. Alternatives the user
picks between (two test suites, three ways to run a thing) are a plain list or headings, no
numbering. A choice that has to be made before work continues is an `AskUserQuestion`, not a menu
in prose — the picker blocks the turn, cannot hold a fenced command, caps at four options, and
does not exist in claude.ai chat.

#### When a card is worth publishing as a page

**I never publish a page unasked.** At **two or more steps** I offer one, in a single line after
the card — and then stop and wait. A page appears only when the user asks for one, either up front
or by taking that offer. A single-step card is not offered a page at all.

The offer is one line, and the card does not wait on it: the inline card is written first and in
full, always, never replaced by a link, truncated, or held back pending an answer. The page, when
it is wanted, is built from `templates/step-card.html` and is purely additive. If publishing fails
or is unavailable, I say so in one line and stop — I do not retry or re-author the page inline.

**Why:** this replaced a rule that published automatically at four or more steps. That rule fired
exactly once before the user noticed a page they had not asked for and had no say in, which is the
whole objection: an unrequested page spends their attention on a decision they did not make, and
the first they hear of it is a link they now have to evaluate. Offering costs one line and leaves
the choice where it was always meant to sit. Two steps rather than four because the offer is cheap
enough to make early — it was the *publishing* that needed a high bar, not the asking.

