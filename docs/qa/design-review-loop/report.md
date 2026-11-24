# Acceptance report: design review loop (plugin 2.92.0)

Run by the reviewer helper in a throwaway clone (the installed reviewer is 2.91.0 and cannot write; the branch's 2.92.0 reviewer can). Copied here by the main session. Criteria are in `criteria.md`.

PASS C2 page stamp: missing, stale and current stamps behave; review and QA pages exempt; `--rounds 3` refused.
PASS C3 acceptance run: stamp refused after a failed round (exit 2), accepted after the fix (exit 0), stale after a later commit (exit 1).
PASS C4 QA gate: missing or stale stamp refused (exit 2), current accepted; screenshots `shots/qa-375-light.png`, `qa-375-dark.png`, `qa-changes-375-light.png`, `qa-changes-375-dark.png`; no sideways scroll, 0 console errors.
PASS C7 parked questions: plain question refused with a park note, `[HARD STOP]` allowed and holds edits until aj's next message.
PASS C8 deviations: row carries all four fields; bypass reply with no ledger call sent back, passes with a call or in default or unknown mode. The "park a change of intent" half is instruction text only, untested.
PASS C9 docs and full run: verify.py 1577 of 1577, verify_tools exit 0 (53 checks; the use_branch switch skipped), docref OK, docs_drift 0, four reversals present.
FAIL C1 reviewer modes: modes and model pins pass, but no saved page-mode findings exist to check.
FAIL C5 self-judging test: the template prints PASS and exits 0; nothing checks the handover card format.
FAIL C6 one approval: the combined line moves the stage to Build with 0 labelled issues; the "refuses" half is not built.

Result: 6 PASS, 3 FAIL. Not stamped.
