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
