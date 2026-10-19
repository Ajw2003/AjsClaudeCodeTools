# Audit 5 of the house-rules plugin: the test suite and the smaller scripts

Findings from a read-only scout pass on 2026-10-16, plus counts and checks run by hand the same
day. Paths are relative to `claude-house-rules/plugins/house-rules/`. Items checked by hand are
marked **confirmed**.

## Test suite shape (measured)
- `scripts/verify.py` is one flat script of 9,747 lines and 161 functions, with no test framework. A run on 2026-10-16 printed "RESULT: PASS - all 832 checks passed".
- It holds 559 check call sites in 123 comment-marked sections; loops expand them into the 832 checks. Measured with a script that maps each check call to the nearest `# ---` banner above it.
- Every behaviour check starts `hook.py` as a separate process (`run_hook`, `verify.py:133`), so there are no unit tests of individual functions.
- The largest sections: issue workflow (67 call sites), the commit rule's obligation half (41), announce and verdict (26), docref.py (24), destructive git steps on own branches (13), the commit-time docs-tier reminder (13).
- 214 lines mention drift or agreement between copies of text (`grep -c "drift|agree|has not drifted|mirrors"`). These checks exist because the same rule text is kept in several files. Examples of tests that check doc wording rather than behaviour: `verify.py:1846`, `1977`, `4565`, `4866`, `6983`.
- Fixtures pin personal data: Windows paths under aj's user folder (`verify.py:1533`, `1559`), Ajw2003 remotes (`275-292`) and the noreply email (`199`, `4114`, `4126`).

## Contradictions
- With no Python available, `scripts/run.sh:106-156` names only 10 of the 30 entry points (guard, guardwrite, inject, showrule, standards, harvest, announce, subagentrules, verdict, audit). The other 20, including commitgate, pagecheck, guardgithub, handover, profile, docstiers, versioncheck and issuelist, fall through to `*) exit 0` and do nothing without a word. This breaks "Nothing fails silently". **Confirmed.**
- The plain-doc target of 20 words per sentence (`rules/detail/clear-writing.md:151`, `scripts/clarity.py:27`) is never enforced; `scripts/plain_docs_check.py:316-323` only prints an average.
- `plain_docs_check.py:254` flags banned words inside backticks, while `clarity.py:196` strips code spans first, so the two writing checkers disagree on the same text.

## Why the writing check flagged "handler" three times
`scripts/clarity.py:195-197` matches jargon with a bare whole-word regex after stripping code spans
and links. It has no exemption for a term the same text defines, or for a word quoted while
reporting the problem; quote handling exists only in other detectors (`clarity.py:48-50`). The only
test, `verify.py:9011`, covers code spans, so nothing covers definitions or quotes. The result in
this session: a reply that explained the word was flagged, and so was the reply reporting the flag.

## Silent failures and dead code
- `plain_docs_check.py:113-124` and `389-394` turn an unreadable hash into CURRENT without a message.
- `hook.py:6841` returns an empty list without a word when `clarity.py` fails to load.
- `clarity.py:184` is a dead assignment.

## Personal data in shipped code
- `scripts/hook.py:1026`, `1169`, `6100-6101` (aj's email in guard text), `scripts/labels.py:17-18`, `templates/step-card.html:136-148` (a `C:\Users\aj` path).

## Natural split lines
| Area | Scripts |
|---|---|
| Pages | `make_page.py`, `templates/handover-page.html` (and the superseded `templates/step-card.html`) |
| Writing | `clarity.py`, `plain_docs_check.py` |
| Docs | `docref.py`, `harvest_scan.py`, `session_ledger_render.py` |
| Labels | `labels.py` |
| Background monitoring | `stallcheck.py` |

## Limits of this pass
The scout had no shell, so it could not run the suite or count by area; the counts above come from
the hand-run script. It also reported a 150-word cap on its own reports, which cut detail from its
first answer.
