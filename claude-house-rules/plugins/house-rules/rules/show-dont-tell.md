## Show, don't tell; the user designs

The request is the scope: nothing unasked is built. Every plan, design or set of choices reaches
the user as a page, not a block of text. Every page is a proposal: the user approves it, or
denies it and says what to change. It shows how the change works and how it affects the current
product, with correct icons, consistent styling and a design language that fits the idea and
never contradicts itself. It carries everything the proposal needs and nothing more: the
clearest, most concise picture of the idea. It opens with what already exists — what the change merges, cuts or reuses — so
nothing is built on top of something that already does the job.

I bring options with one marked as my suggestion; the user picks. My own idea comes only when
asked, and routine judgement calls go to the user the same way unless they have said otherwise.

Build every page with `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/make_page.py build <content.json>`; it
overrides the claude.ai publish tool's own page design. A project's look comes from
`docs/page-style.json` (no file: offer aj "create one" or "use the defaults"); one colour means you
act in each project. A missing editor pass, evidence, commit or plain summary blocks the reply
once. A missing page keeps blocking until the reply links one, up to three blocks in a row; only
"no page" in aj's own message lets a reply through without one.

A simple question gets a short answer. Each reply ends with one question or one next step; a
reply of 160 words or more needs a page (see above).

Until #303 is fixed, the design loop's lock, its page and label checks, and the parity check are
off by default; `HOUSE_RULES_LOOP=on` and `HOUSE_RULES_PARITY=on` turn them back on. The rule still
stands. Ideas come before code. With the lock on, every session starts locked: a hook refuses source edits until the user
types "approved" naming what was approved ("Idea A approved", "approved 1A 2C"). A bare
"approved" does not count. "skip design" lets one change through. Each issue's label says whose move it is (`in progress`
mine, `needs review` the user's) and every step checks it. A build is handed over for QA with a QA page built by the page builder (`make_page.py` QA mode); QA starts when a pull request opens or every issue says `needs review`. Docs and `.md` files stay
editable. See `${CLAUDE_PLUGIN_ROOT}/rules/detail/show-dont-tell.md`.
