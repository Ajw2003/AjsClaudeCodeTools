# What house-rules actually does

This is the plain-English version. No familiarity with the rest of the repo, hooks, or Claude
Code's internals required — if a technical word shows up, it's explained the first time it's used.

## The problem it solves

If you have personal preferences for how you want an AI coding assistant to behave — commit
often, ask before doing anything destructive, never hide a running command from you, hand over
instructions that actually work when pasted — the normal way to state those is a text file you
paste into every project. That file has to be copied to every device and every new project by
hand, and it drifts the moment one copy gets edited and the others don't.

`house-rules` is a **plugin** (an add-on you install once into Claude Code, the same way you'd
install an extension into a browser) that gets rid of the copying. Once it's installed on a
device, every Claude Code session on that device automatically knows the rules — a work laptop,
a cloud session, a fresh project you've never opened before, all of it. There is nothing to paste
and nothing to remember to update.

## How it actually reaches Claude

Claude Code has moments during a session — starting up, receiving a message, calling a tool,
finishing a turn — where it lets an installed plugin run a small program and feed something back
into the conversation. Those moments are called **hooks**. `house-rules` has one small program
that runs at several of those moments, each one doing a specific, narrow job. None of it needs you
to do anything; it just runs.

## What it does, moment by moment

**When a session starts,** it prints the actual rules into Claude's context, so Claude has read
them before you've typed anything — the same effect as pasting your rules file in, except it
happens automatically and can't go stale. It also prints a summary of the coding conventions that
apply to whatever kind of project you've opened (a Unity/C# project gets Unity conventions, a
JS/TypeScript project gets those, and a plain rule set that applies everywhere always shows up).

**While you're chatting,** a short reminder rides along with every message you send, so the rules
haven't faded from view 200 messages into a long session — the way a person forgets the fine
print of something they read an hour ago.

**Before Claude runs a command in your terminal,** the plugin checks the command's text against a
list of things you've said you want a heads-up on first: deleting things, rewriting git history,
force-pushing, running something hidden in the background, and so on. If it matches, you get
asked to approve it before it runs — it never blocks anything outright, it just makes sure a risky
action doesn't slip past you unnoticed. A plain "save my work" commit or push is let through
without asking, but only on a branch Claude created for its own work — never on your main branch.

**Whenever Claude writes or edits a file,** two separate checks run. One notices if what got
written looks like a report, a plan, or some other document that ended up in a scratch folder or
temp directory instead of your actual project — and reminds Claude to move it in before finishing,
since a file that only exists in a temporary folder isn't really a deliverable. The other notices
if Claude just wrote a script or program file, and reminds it to actually run the thing rather than
just claiming it works.

**Whenever Claude writes a long comment inside your code** — the kind that's really a small essay
explaining a design decision or a workaround, not just a one-line note — it gets flagged so that
essay can be moved into your project's proper documentation instead of living inside a comment,
where nobody reading the docs would ever see it and nothing keeps it in sync with the code around
it.

**Right before Claude finishes answering,** if the reply handed you a command to run, a check
looks at whether that instruction is actually usable — does it say where to run it, in which
shell, with the exact text to type, and what you should expect to see — rather than just dropping
a bare command and leaving you to guess. If something's missing, it gets flagged before the reply
goes out.

**When Claude hands work off to a specialised helper** (a smaller, cheaper version of itself
assigned to one job, like carrying out an already-agreed plan or moving a comment into docs), the
plugin announces that the handoff happened and which helper is doing it, and afterwards confirms
which one it actually ran on — because it's possible for a request to quietly run on the wrong
model, and this makes that visible instead of invisible.

**Once a session starts,** the plugin also compares its own version against the copy it was
installed from and the very latest copy out on GitHub. If they've drifted apart, it says so
loudly, right away, along with the exact commands to bring things back in sync — because a plugin
that silently runs on an old copy of its own rules would defeat the entire point.

## What it deliberately does not do

It never blocks a command outright — the strongest thing it does is ask you to confirm. It never
edits your files on its own initiative. It doesn't run on branches you authored without your
say-so. And it keeps almost no memory between one check and the next — each of these checks looks
at the one thing happening right now and reacts to that, rather than accumulating hidden state
that could quietly get out of sync with reality. (There is exactly one narrow exception, used only
to avoid nagging you twice about the same out-of-date plugin within a single session.)

## The two smaller, younger add-ons living alongside it

The same repository also carries two newer, smaller experiments built the same way:

- **prompt-workshop** watches for a prompt that's grown complicated enough to be worth refining
  before sending.
- **agent-router** looks at how complex a request seems and nudges Claude toward delegating it to
  a helper pinned to an appropriately-sized model — a cheap model for a simple job, a more capable
  one for a hard one.

Neither is as mature or as depended-on as `house-rules` itself; they're both still being shaped.

## How you'd know it's actually working

There's an automated test suite that feeds realistic examples through every check above and
confirms each one makes the decision it's supposed to. It's not something you need to run
yourself day to day — it exists so that a change to the rules can be proven to have actually taken
effect, rather than just reading like it should have.
