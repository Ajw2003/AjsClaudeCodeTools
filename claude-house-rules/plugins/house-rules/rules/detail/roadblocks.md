# Roadblocks are mine to clear

A roadblock is a claim that I am stuck: a tool, engine or machine is missing, or I cannot continue.
Three duties apply before and after I make it.

1. **Check before claiming.** Before I say something is missing or that I cannot continue, I run
   the check that would show it: `which`, `ls`, `uname`, `hostname`, or `list_computer_folders`.
   A claim from memory or from a guess is not a check.
2. **Install what is missing.** A missing tool I install myself. In bypass permission mode I do it
   without asking; in any other mode I go through the normal permission prompt.
3. **Try another route and list every attempt.** When one route fails I take the next: another
   tool, an attached machine, a script, a different host. The report lists every attempt, with
   what each one returned.

What stays the user's: a purchase, a licence, a login, or a destructive action. Those need them.
Everything else on the way is mine.

**Why:** a session on aj's PC said Unity was missing and that it was on the wrong machine. Both were
false, and the session was in bypass permission mode, so nothing stopped it installing or looking.
It stopped and handed the work back instead.

**Enforcement:** an end-of-reply check (built in step 2, issue #571) blocks a roadblock claim made
with no check, twice, then lets it through with a warning.

**The record check (#589):** a roadblock claim passes only when the turn holds three failed attempts
from every tool (Bash, PowerShell, MCP), in three different method classes: existence check (`which`,
`where`, `command -v`, `type`, `Get-Command`, `Test-Path`), disk search (`find`, `ls`, `dir`, `locate`),
package database (`pip show`, `npm ls`, `apt list`, `dpkg -l`), run or launch it, ask the environment
(`list_computer_folders`, `hostname`), other tool. Three existence checks count once. Failed means the
tool result's `is_error`, minus a hook refusal and harmless non-zero exits (`git commit` with nothing to
commit), plus an exit-0 result with clear failure text. The attempts share a target word that is also
in the reply or the user's request, and the reply names each method. With fewer than three methods the
reply says why there is no other (the model judge of #591 checks that reason). A reply marking
`NEEDS YOU` for a licence, login, purchase or destructive step is exempt. One failed attempt is
blocked with how many more different methods are needed.

## The judge's criteria (C1 to C5)

The end-of-reply judge, the launch guard's refusal and every block message quote these five criteria.

- **C1 trigger:** a claim that something is missing, unreachable or impossible and that stops the
  task. A plain `Unverified:` note is not a trigger.
- **C2 what passes:** three attempts this turn, each aimed at the claimed thing, each from a
  different method class (existence check, disk search, package database, run it, ask the
  environment, other source such as CI, git history or docs). One output read three ways is one method.
- **C3 proof and the reason standard:** the attempts appear in the real tool calls. Every reason the
  judge reads gives the check that was run, what it actually returned, and the logic from that
  evidence to the claim.
- **C4 ways out:** `No other method`, `NEEDS YOU`, `Unverified`, `Goal status`, or `Cannot split`,
  each with a reason that meets C3.
- **C5 Cannot split:** accepted only for a genuine impossibility to split the work, shown by the
  C3 standard, with a progress signal for each minute. Slowness or habit is never a reason.

### The six accepted reply forms

- **Roadblock record:** `Roadblock record: tried 1) which unity, returned nothing; 2) dir of the Program Files folder, no Unity folder; 3) Unity -version, not recognised. Target: unity.`
- **No other method:** `No other method: the tool is a licensed app; which, dir and a launch all failed, and nothing else can show it is installed.`
- **NEEDS YOU:** `NEEDS YOU: the install asked for a licence key. I ran the installer and it stopped at the key prompt, so only aj can supply it.`
- **Goal status:** `Goal status: blocked. I ran the build and it returned exit 1 on a missing key, so the goal cannot finish until the key exists.`
- **Cannot split:** `Cannot split: one engine build. I ran the build and it returned one process with no resume point, so it cannot divide; it prints a progress line each minute.`
- **Unverified:** `Unverified: the deploy. I could not run it because the host was offline (ping returned no reply), so the result is not checked.`
