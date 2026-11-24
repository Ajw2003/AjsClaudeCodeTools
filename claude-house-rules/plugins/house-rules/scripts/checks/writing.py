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
_CAP = ("Bash", "python3 scripts/visualcheck.py shots --steps s.json --out docs/qa/f/cap")
_LED = ("Bash", "python3 scripts/ledger.py check docs/qa/f")
_IMG = ("Read", "/proj/docs/qa/f/cap/phone-light.png")


def _vn(name, uses, **env):
    _, v, ctx = _stop_notes(_turn_transcript(name, "make the header blue", uses), "The header is blue.", **env)
    return v, ctx


_v, _c = _vn("pv-nocap", [("Edit", "/proj/site.css"), ("Bash", "echo screenshot browser playwright")])
pv_case("Stop: a command that merely contains screenshot or browser no longer satisfies the visual check; the note names the capture",
        _v and "no: capture, ledger check, image read" in _c and "visual-loop" in _c, "ctx=%r" % _c[-300:])
_v, _c = _vn("pv-nolg", [("Edit", "/proj/site.css"), _CAP, _IMG])
pv_case("Stop: a capture and an image read but no ledger check is flagged naming the ledger",
        _v and "no: ledger check" in _c, "ctx=%r" % _c[-200:])
_v, _c = _vn("pv-nolook", [("Edit", "/proj/site.css"), _CAP, _LED])
pv_case("Stop: a capture and ledger check but no image read is flagged naming the look",
        _v and "no: image read" in _c, "ctx=%r" % _c[-200:])
_v, _c = _vn("pv-all", [("Edit", "/proj/site.css"), _CAP, _LED, _IMG])
pv_case("Stop: capture, ledger check and image read after the visual write leave the turn silent", not _v, "ctx=%r" % _c[-200:])
_v, _c = _vn("pv-stale", [_CAP, _LED, _IMG, ("Edit", "/proj/site.css")])
pv_case("Stop: evidence from before the last visual write does not count", _v and "capture" in _c, "ctx=%r" % _c[-200:])
_v, _c = _vn("pv-svg", [("Write", "/proj/art/logo.svg")])
pv_case("Stop: an .svg write is a visual write", _v, "ctx=%r" % _c[-200:])
_v, _c = _vn("pv-png", [("Write", "/proj/art/after.png")])
pv_case("Stop: a .png write is an output, not a visual source, so it is silent", not _v, "ctx=%r" % _c[-200:])
_, _vis, _ = _stop_notes(_turn_transcript("pv-off", "make the header blue", [("Edit", "/proj/site.css")]),
                         "Done.", HOUSE_RULES_VISUAL_CHECK="off")
pv_case("Stop: HOUSE_RULES_VISUAL_CHECK=off switches the visual check off", not _vis, "visual=%s" % _vis)
import shutil
import tempfile
_pg_dir = tempfile.mkdtemp(prefix="hr-pagevis-")
try:  # handover pages (make_page mark or house-rules-page meta) are not visual-loop work
    _pg_mk = os.path.join(_pg_dir, "built.html")
    _pg_hw = os.path.join(_pg_dir, "hand.html")
    _pg_pl = os.path.join(_pg_dir, "plain.html")
    with open(_pg_mk, "w") as _f:
        _f.write("<!doctype html>\n<!-- house-rules make_page 2.87.0 -->\n<p>x</p>")
    with open(_pg_hw, "w") as _f:
        _f.write('<!doctype html><meta name="house-rules-page" content="plan"><p>x</p>')
    with open(_pg_pl, "w") as _f:
        _f.write("<!doctype html><p>app fixture</p>")
    _v, _c = _vn("pv-pg-mk", [("Write", _pg_mk)])
    pv_case("Stop: a page built by make_page (carries the mark) is not flagged for the visual loop", not _v, "ctx=%r" % _c[-200:])
    _v, _c = _vn("pv-pg-hw", [("Write", _pg_hw)])
    pv_case("Stop: a hand-written page with the house-rules-page meta is not flagged", not _v, "ctx=%r" % _c[-200:])
    _v, _c = _vn("pv-pg-pl", [("Write", _pg_pl)])
    pv_case("Stop: a plain .html file with neither mark is still flagged", _v and "plain.html" in _c, "ctx=%r" % _c[-200:])
    _v, _c = _vn("pv-pg-mix", [("Write", _pg_mk), ("Write", _pg_pl)])
    pv_case("Stop: a turn with a page and a plain file is flagged for the plain file only",
            _v and "plain.html" in _c and "built.html" not in _c, "ctx=%r" % _c[-200:])
    _v, _c = _vn("pv-pg-gone", [("Write", os.path.join(_pg_dir, "gone.html"))])
    pv_case("Stop: a missing page path is not exempt and is still flagged", _v and "gone.html" in _c, "ctx=%r" % _c[-200:])
    _, _vis, _ = _stop_notes(_turn_transcript("pv-pg-off", "x", [("Write", _pg_pl)]), "Done.", HOUSE_RULES_VISUAL_CHECK="off")
    pv_case("Stop: HOUSE_RULES_VISUAL_CHECK=off still silences a plain .html file", not _vis, "visual=%s" % _vis)
finally:
    shutil.rmtree(_pg_dir, ignore_errors=True)
_PS_WIDE = _PS_PLAIN +"\n\n| a | b | c | d |\n|---|---|---|---|\n| 1 | 2 | 3 | 4 |\n"
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

import clarity as _cl
_SVGU = "data:image/svg+xml,%3Csvg xmlns=%27x%27 width=%2710%27 height=%2710%27 fill=%27red%27 stroke=%27black%27%3E"
_SVGP = ('<p>Hi there all</p><script>const PAGE = {\n pic: "%s",\n lead: "Plain words about the page here."\n};</script>'
         '<svg width="9"><text>mangled wordy picture label</text></svg>' % _SVGU)
_SVGT = _cl.page_text(_SVGP)
pv_case("page text (#612): an inline picture whose data address has raw spaces, and an inline <svg>, give no findings or text",
        "stroke" not in _SVGT and "mangled" not in _SVGT and "Plain words about the page here." in _SVGT
        and not _cl.findings(_SVGT), _SVGT[:80])


finish()
