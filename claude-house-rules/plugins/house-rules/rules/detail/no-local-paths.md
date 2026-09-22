# Never name a local path in an issue or a pull request


Issue and pull-request text — titles, descriptions, comments, review comments — is published, is
often public, and outlives the session. It never contains a path from the user's own machine:
not a drive letter or home directory (`C:\Users\...`, `/Users/...`, `/home/...`), not another
project's folder on disk, not a scratchpad or temp file.

Name files by repo-relative path (`docs/x.md`), another repository by `owner/repo` or just its
name, and a local project by what it is ("the RockSkipping project"), never where it lives. If a
body is written to a file first and passed with `--body-file`, that file is what gets checked,
before I run `gh ... create`, `edit` or `comment`.

This is about text that gets published. A command handed to the user to run in their own
terminal still carries absolute local paths, as the handover rule requires — that text never
leaves their machine.

No hook can enforce this: the tell is in a file's contents, not in a command a hook can match.
The check is mine, every time.

**Why:** issue #65 on this public repository named the user's local project path in its body. A
local path says nothing to any other reader, discloses how the user's machine is laid out, and
stays in the edit history after the text is corrected.

