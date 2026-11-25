## Show, don't tell; the user designs

The request is the scope: nothing unasked is built. Every plan, design or set of choices reaches
the user as a page, not a block of text. Every page is a proposal: the user approves it, or
denies it and says what to change. It shows how the change works and how it affects the current
product, with correct icons, consistent styling and a design language that fits the idea and
never contradicts itself. It carries everything the proposal needs and nothing more: the
clearest, most concise picture of the idea. It opens with what already exists — what the change merges, cuts or reuses — so
nothing is built on top of something that already does the job.

I ask aj only about choices that change how something looks or what it does (a new dependency, data format or API change counts); with nobody present I decide those too and log the assumption with `ledger_note.py decide`. Everything else I decide and log the same way, in every mode; aj sees decisions on the QA page only. Hard stops stay aj's (licence, login, purchase, deletion, money, secrets, other people, outward posts): that part is marked NEEDS YOU or parked with `ledger_note.py park --category ... --tried ...`, and the rest carries on.

Any page format passes if it meets seven basics: one-sentence summary, a next-step box that stays on screen, a picture per idea, no block over 60 words, numbered one-action steps, a tick-box checklist when aj acts, fits 375px in light and dark. A type (proposal, build plan, QA, review, art) adds only what it needs; the page declares it with `<meta name="house-rules-page">` and marks `data-basic="..."`. `make_page.py build|start <type>` is an optional shortcut; an unmarked page is read and refused once naming each failed basic. A project's look comes from
`docs/page-style.json` (no file: offer aj "create one" or "use the defaults"); one colour means you
act in each project. A missing editor pass, evidence, commit or plain summary blocks the reply
once. A missing page keeps blocking until the reply links one, up to three blocks in a row; only
"no page" in aj's own message lets a reply through without one.

Any page I make, rebuild or edit in a turn is sent to aj with the file-send tool as my last action, and sent again after any later change; a published artifact link counts as sent.

A plan or pitch follows aj's reference page `docs/plans/reference/sword-fighting-proposal.html` (`Ajw2003/AjsClaudeCodeTools`); checklist in the detail file.

A simple question gets a short answer. Each reply ends with one question or one next step; a
reply of 160 words or more needs a page (see above).

Ideas come before code. Every session starts locked: a hook refuses source edits until the user
types "approved" naming what was approved ("Idea A approved", "approved 1A 2C"). A bare
"approved" does not count. "skip design" lets one change through; "design loop off" or "builders off" typed on its own line, switches the loop or the helpers off for the repo. Each issue's label says whose move it is (`in progress`
mine, `needs review` the user's) and every step checks it. A build is handed over for QA with a QA page built by the page builder (`make_page.py` QA mode); QA starts when a pull request opens or every issue says `needs review`. In Build I log a departure from the plan (`ledger_note.py deviate`) and go on; unattended or bypass, I park a reversible question or a change to what aj approved (`ledger_note.py park`); licence, login, purchase, deletion, money, secrets, people: [HARD STOP]: ask. Build replies end with the next step. Docs and `.md` files stay
editable. See `${CLAUDE_PLUGIN_ROOT}/rules/detail/show-dont-tell.md`.
