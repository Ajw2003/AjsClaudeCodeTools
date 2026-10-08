# Long-form reasoning goes in a document, not in a comment


I keep writing the reasoning down as it occurs — that habit is right and I do not change it. What
changes is where it lands. A comment that has grown into an essay is documentation that ended up
in the wrong file: design rationale, a bug post-mortem, a derivation, a platform quirk, an
argument for why the obvious approach was rejected.

Before the turn ends, each long-form block moves — where depends on what it is. An ongoing
mechanism, invariant, or operational gotcha moves into the tier-4 system document under
`docs/4-systems/` that owns that code — a new one if none does — under the section that fits:
the design into *How it works*, a rule that must stay true into *Invariants*, an operational
trap into *Traps*. Design rationale, a rejected approach, or a post-mortem is different: it is
a record of a choice, not current truth about the system, so it becomes a dated entry in
`docs/6-decisions/Decisions.md` instead. Either way the site keeps a **one-line pointer**
`doc-ref <id> <path>` (in that language's comment syntax), where `<id>` is the 4-hex marker
`<!-- ref:<id> -->` on its own line under the moved note's heading, made with `docref.py new` —
so the code still leads to the reasoning and `docref.py check` can prove it still does. Anything a reader genuinely
needs *at that exact line* to not break the code stays an ordinary comment; only the long-form
context moves.

The move itself is mechanical once the thinking is done, so I hand it to the
`@house-rules:archivist` subagent with the file and the blocks named, rather than doing it on the
planning model.

**Why:** a comment is not bound to anything. Nothing forces it to change when the code beneath it
changes, which is the definition of a document that will rot — and while it rots there it is
invisible to everyone reading `docs/`. The reasoning was worth writing; it was just filed
somewhere it cannot be maintained or found.

