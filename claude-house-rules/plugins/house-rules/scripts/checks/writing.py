#!/usr/bin/env python3
"""checks/writing.py - the writing part: the Stop-time plain-summary, long-reply and visual checks (#370).

Run it alone:  python3 claude-house-rules/plugins/house-rules/scripts/checks/writing.py
It prints its own numbered results and a RESULT line, and exits non-zero if any check fails. verify.py runs
every part at the same time; see docs/4-systems/verify-suites.md, "The split layout (#370)".

STDLIB ONLY, like hook.py.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: F401,F403 - common.py sets __all__ to everything it defines

print()
print("house-rules hooks - verification (Python) - part: writing")
print("=" * 43)
print()


missing = [
    ph
    for ph in [
        "Write it so nothing is left to guess",
        "### The voice",
        "gloss",
        "never buys warmth with accuracy",
        "HOUSE_RULES_VOICE=off",
    ]
    if ph.lower() not in rules_text.lower()
]
if not missing:
    report("PASS", "the clear-writing rule carries the voice and its hard constraint")
    print("          tone is a preference; not softening a failure is not")
else:
    report("FAIL", "the clear-writing rule carries the voice and its hard constraint")
    print(f"          missing from house-rules.md: {'; '.join(missing)}")
pv_case("Stop: the same turn changed an .html file and looked at nothing, so it gets the visual note (#88)",
        _vis, "visual=%s" % _vis)
_pv_shot = _turn_transcript("pv-shot", "make the header blue",
                            [("Edit", "/proj/site.css"), ("Bash", "npx playwright screenshot http://localhost:3000 after.png")])
_, _vis, _ = _stop_notes(_pv_shot, "The header is blue.")
pv_case("Stop: a visual edit with a Playwright screenshot in the turn gets no visual note", not _vis, "visual=%s" % _vis)
_pv_read = _turn_transcript("pv-read", "make the header blue", [("Edit", "/proj/site.css"), ("Read", "/proj/after.png")])
_, _vis, _ = _stop_notes(_pv_read, "The header is blue.")
pv_case("Stop: a visual edit whose turn read a captured image gets no visual note", not _vis, "visual=%s" % _vis)
_, _vis, _ = _stop_notes(_turn_transcript("pv-off", "make the header blue", [("Edit", "/proj/site.css")]),
                         "Done.", HOUSE_RULES_VISUAL_CHECK="off")
pv_case("Stop: HOUSE_RULES_VISUAL_CHECK=off switches the visual check off", not _vis, "visual=%s" % _vis)
_PS_WIDE = _PS_PLAIN + "\n\n| a | b | c | d |\n|---|---|---|---|\n| 1 | 2 | 3 | 4 |\n"
_ps_wrote = _turn_transcript("ps-wrote", "add the commit hooks", [("Edit", "/proj/src/app.py")])
_ps_read = _turn_transcript("ps-read", "what does this do?", [("Bash", "cat app.py")])
_ps_commit = _turn_transcript("ps-commit", "commit it", [("Bash", "git commit -m x -- a.py && git push")])


def _ps(transcript, reply, **env_extra):
    return "plain summary first" in _stop_notes(transcript, reply, **env_extra)[2]


pv_case("Stop: a work report opening with a pile of code names is sent back to lead with a plain summary (#98)",
        _ps(_ps_wrote, _PS_TECH), "fired=%s" % _ps(_ps_wrote, _PS_TECH))
pv_case("Stop: a work report that opens plainly is left alone", not _ps(_ps_wrote, _PS_PLAIN),
        "fired=%s" % _ps(_ps_wrote, _PS_PLAIN))
pv_case("Stop: a plain opening with a 4-column table still fires - too wide for a phone", _ps(_ps_wrote, _PS_WIDE),
        "fired=%s" % _ps(_ps_wrote, _PS_WIDE))
pv_case("Stop: a turn that only committed counts as reporting work", _ps(_ps_commit, _PS_TECH),
        "fired=%s" % _ps(_ps_commit, _PS_TECH))
pv_case("Stop: a turn that changed nothing is not a work report, so a technical answer is fine",
        not _ps(_ps_read, _PS_TECH), "fired=%s" % _ps(_ps_read, _PS_TECH))
pv_case("Stop: HOUSE_RULES_PLAIN_SUMMARY=off switches it off",
        not _ps(_ps_wrote, _PS_TECH, HOUSE_RULES_PLAIN_SUMMARY="off"), "")


finish()
