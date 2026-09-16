
house-rules
a Claude Code plugin

Your rules, followed on every machine, without a file to keep copying.
house-rules is an add-on for Claude Code — the way a browser extension is an add-on for a browser — that makes the assistant follow one person's standing preferences automatically, in every project, on every device, from the moment a session opens.

The problem it replaces
The old way to give an AI coding assistant standing preferences — commit often, ask before anything destructive, never hide a running command, hand over instructions that actually work when pasted — was a text file pasted into every project by hand. It had to be copied to every device, and it drifted the moment one copy was edited and the others weren't.

Install house-rules once on a device and every session on it already knows the rules — a work laptop, a cloud session, a project never opened before. Nothing to paste, nothing to keep in sync.

How it actually reaches Claude
Claude Code exposes a handful of moments during a session — starting up, receiving a message, calling a tool, finishing a reply — where an installed plugin is allowed to run a small check and feed something back into the conversation. Those moments are called hooks. house-rules attaches one narrow, specific check to several of them. None of it needs a person to do anything; it just runs.

A session, moment by moment
What actually happens, in the order it happens, across one ordinary session.

Session opens
SessionStart
The rules get printed straight into Claude's context, already read before anyone has typed a word — the same effect as pasting a rules file in, except automatic and impossible to let go stale. The coding conventions for whatever kind of project just got opened come along with it — Unity/C# gets Unity conventions, JS/TypeScript gets its own.

Every message you send
UserPromptSubmit
A short reminder rides along, so the rules haven't faded from view two hundred messages into a long conversation — the way fine print from an hour ago quietly stops registering.

Before a terminal command runs
PreToolUse
The command's text gets checked against a list of things worth a heads-up first — deleting things, rewriting git history, force-pushing, running something hidden in the background. A match asks for approval before it runs; nothing is ever blocked outright, it just can't slip past unnoticed. An ordinary save-my-work commit or push goes through without asking, but only on a branch Claude opened for its own work, never on your main branch.

Every file write or edit
PostToolUse
One check notices a report or plan that landed in a scratch folder instead of the actual project, and flags it before the turn ends — a file that only exists in a temp directory isn't really a deliverable. A second notices a script that just got written and flags that it should actually be run, not just claimed to work. A third notices a comment that's grown into a small essay explaining a decision, and flags it for a move into proper documentation, where it can stay in sync with the code and be found again.

Right before the reply goes out
Stop
If the reply hands over a command to run, this checks that the instruction is actually usable — where to run it, in which shell, the exact text, what to expect back — rather than a bare command left for someone to guess at.

Handing work to a helper
SubagentStart / SubagentStop
When Claude delegates a job to a smaller helper assigned to one task — carrying out an already-agreed plan, say — the handoff gets announced, and afterwards it's confirmed which model the helper actually ran on. A request quietly running on the wrong model stops being invisible.

Keeping itself honest
On every session start, the plugin compares its own version against the copy it was installed from and the latest copy on GitHub. If they've drifted, it says so immediately and loudly, with the exact commands to bring things back in sync — a plugin quietly running on a stale copy of its own rules would defeat the entire point of having it.

fix
claude plugin marketplace update && claude plugin update house-rules
What it deliberately never does
Block a command outright — the strongest thing it ever does is ask for confirmation.
Edit a file on its own initiative — every check only flags and reminds.
Act on a branch someone else authored without being told to.
Remember much between one check and the next — each one reacts to what's happening right now, not to accumulated state that could quietly drift from reality. One narrow exception exists, just to avoid repeating the same out-of-date-version warning twice in a session.
Two younger siblings
The same repository carries two smaller, newer experiments built the same way — neither as depended-on yet as house-rules itself.

prompt-workshop
Watches for a prompt that's grown complicated enough to be worth refining before it's sent.

agent-router
Reads how complex a request seems and nudges it toward a helper pinned to an appropriately sized model — cheap for a simple job, capable for a hard one.

How you'd know it's actually working
An automated suite feeds realistic examples through every check above and confirms each one makes the decision it's supposed to. Nobody needs to run it day to day — it exists so a change to the rules can be proven to have taken effect, rather than just read like it should have.

house-rules — a personal Claude Code plugin
Ajw2003/AjsClaudeCodeTools
