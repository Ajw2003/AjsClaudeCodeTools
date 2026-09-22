# Edit in place; a full rewrite is a delete, not an edit


The rule above carves out "ordinary edits to tracked, committed files" because git already holds
them. A full rewrite of a file is not one of those ordinary edits, even when the file is tracked:
it throws away everything already in the file — the parts the change was never meant to touch —
and replaces the lot with whatever the new version happens to contain. That is a delete and a
recreate wearing a single file-write, and git being able to recover the old blob afterward does
not make the loss safe, because nobody is checking the diff line by line before it ships.

- **Changing only the lines that need to change is the default**, not a nicety. Most real edits
  touch a fraction of a file, and an in-place change is the only form that leaves the rest of it
  exactly as it was.
- **Rewriting a file that already exists, wholesale, is the exception**, and it gets approved by
  name every time: before it happens, I say plainly which existing content is being discarded and
  why an in-place edit will not do. "I regenerated it" is not that reason; "the structure can't
  hold the new content without changing throughout" is.
- This matters most exactly where nobody is watching in real time — an unattended or scheduled
  run. That is precisely when a bad rewrite ships unnoticed, so the rule does not relax there; if
  anything, that is the case it exists for.

**Why:** a scheduled, unattended task once rewrote a CSS file wholesale instead of touching the
one thing that needed to change, and the regression it introduced sat unnoticed until someone
found it later. Git holding the old version did not prevent the regression — it only proved,
after the fact, that the loss had been avoidable.
