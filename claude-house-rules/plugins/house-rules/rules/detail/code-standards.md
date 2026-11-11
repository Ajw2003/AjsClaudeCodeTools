# Code follows the standards loaded for this project


The coding standards injected at session start are binding for code written in this repo, not
background reading. Where a file's existing style conflicts with them, the file wins — that
carry-over is already stated in `coding-philosophy.md` itself, consistency within a file beats
a global rule.

A repo can be more than one stack, and when several documents load, each governs only its own
languages — the preamble that comes with them says which document applies where. Applying one
stack's conventions to another's files (formatting C# like TypeScript because both loaded) is
the failure this rule exists to prevent.

A repo whose needs differ from what got detected pins its own set in `.claude/standards` rather
than the standards being ignored quietly.

**Why:** injected text with no rule behind it is background reading, easy to skim past. A repo
sitting on two stacks needs the two kept apart, not merged into one undifferentiated wall of
rules.


## Values a person may want to change are never hardcoded (#117)

Values a person may want to change are never hardcoded: they go in a settings file, an exposed field
(for example a Unity serialized field or ScriptableObject) or a config value, unless they were set by
measurement. The `harvest` hook reports (never blocks) a Write or Edit that assigns a bare number to a
tuning-shaped name (speed, delay, timeout, cooldown, duration, damage, health, rate, scale, limit, max,
min, threshold, count, interval, force, gravity, volume), naming the first 3 file:lines. A "measured" or
"empirical" comment, an UPPER_CASE constant commented "a starting value", and test files are skipped.

**Why:** a number buried in code can only be changed by editing code; the person tuning it is rarely the one who can.
