#!/usr/bin/env python3
"""checks/make_page.py - tools/make_page: the page builder and its visual check (#370).

Run it alone:  python3 claude-house-rules/plugins/house-rules/scripts/checks/make_page.py
It prints its own numbered results and a RESULT line, and exits non-zero if any check fails. verify.py runs
every part at the same time; see docs/4-systems/verify-suites.md, "The split layout (#370)".

STDLIB ONLY, like hook.py.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: F401,F403 - common.py sets __all__ to everything it defines

print()
print("house-rules hooks - verification (Python) - part: make_page")
print("=" * 43)
print()


# ---- make_page.py: the handover page builder and project style file (#255) ----
MAKE_PAGE = os.path.join(HERE, "make_page.py")
_mp_tmp = tempfile.mkdtemp(prefix="mp-")
_mp_cases = []


def _mp(*args):
    r = subprocess.run([sys.executable, MAKE_PAGE] + list(args), capture_output=True, text=True, timeout=300)
    return r.returncode, r.stdout + r.stderr


def _mp_proj(name, style=None):
    d = os.path.join(_mp_tmp, name)
    os.makedirs(os.path.join(d, "docs"), exist_ok=True)
    if style is not None:
        with open(os.path.join(d, "docs", "page-style.json"), "w", encoding="utf-8") as f:
            json.dump(style, f)
    return d


def _mp_content(name, extra_changes=None, text="Plain.", approval="Build plan approved: demo thing", choices=None, forRepo=None):
    page = {"title": "T " + name, "eyebrow": "e", "approval": approval,
            "short": {"lead": text, "hint": "h", "key": [["We", ""]], "items": [["bulb", "Idea", "The idea", "", "c", "r"]]},
            "changes": [["new", "A thing", "One line.", None, "Detail.", None, None]] + (extra_changes or []),
            "wrapup": {"summary": "s", "changing": "c", "blocking": "b", "next": "n", "todo": ["t"]}}
    if approval is None:
        del page["approval"]
    if choices is not None:
        page["choices"] = choices
    if forRepo is not None:
        page["forRepo"] = forRepo
    path = os.path.join(_mp_tmp, name + ".page.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(page, f)
    return path


def _mp_page_of(html_path):
    with open(html_path, encoding="utf-8") as f:
        h = f.read()
    m = re.search(r"^const PAGE = (\{.*?^\});$", h, re.S | re.M)
    return json.loads(m.group(1)) if m else None


_PS_STYLE = {"name": "X", "themes": ["dark"],
             "colors": {"background": "#14120E", "surface": "#1E1A14", "text": "#DCD2BA", "text_muted": "#9A9078", "line": "#332D22"},
             "roles": {"you_act": {"color": "#5FA288"}, "accent": {"color": "#7A6AA0"}, "blocking": {"color": "#C4542E"}, "done": {"color": "#9A9078"}},
             "reserved": [{"color": "#C9A227", "rule": "gold only"}],
             "fonts": {"display": "Eczar", "body": "Spectral", "label": "Overpass Mono",
                       "load": "https://fonts.googleapis.com/css2?family=Eczar&display=swap"},
             "shape": {"corner_radius": 0}, "labels": {"family": "label", "case": "upper"}, "icons": {"frame": "sigil"},
             "pictures": "required"}

_c1 = _mp_content("basic")
_d = _mp_proj("nostyle")
_rc, _o = _mp("build", _c1, "--project", _d)
_mp_cases.append(("make_page: build with no style file exits 3 and names both commands",
                  _rc == 3 and "make_page.py style --draft" in _o and "make_page.py style --quick" in _o))

_rc1, _ = _mp("style", "--quick", "--project", _d)
_rc2, _o2 = _mp("build", _c1, "--project", _d)
_html = os.path.join(_d, "docs", "plans", "basic.html")
_txt = open(_html, encoding="utf-8").read() if os.path.isfile(_html) else ""
with open(os.path.join(HERE, "..", ".claude-plugin", "plugin.json"), encoding="utf-8") as _f:
    _ver = json.load(_f)["version"]
_mp_cases.append(("make_page: style --quick then build succeeds and stamps the mark right after the doctype",
                  _rc1 == 0 and _rc2 == 0 and _txt.startswith("<!doctype html>\n<!-- house-rules make_page %s -->" % _ver)
                  and "visual check" in _o2 and "<title>T basic</title>" in _txt))
_mp_cases.append(("make_page (#558): a successful build ends with the SEND THIS PAGE NOW line",
                  _rc2 == 0 and _o2.rstrip().splitlines()[-1].startswith("make_page: SEND THIS PAGE NOW: ")))

_d = _mp_proj("ps", _PS_STYLE)
_rc, _o = _mp("build", _c1, "--project", _d)
_txt = open(os.path.join(_d, "docs", "plans", "basic.html"), encoding="utf-8").read() if _rc == 0 else ""
_mp_cases.append(("make_page: the PlunderSpell-shaped style file puts its role colours, fonts link and sigil frame in the page",
                  _rc == 0 and "--you:#5FA288" in _txt and "--accent:#7A6AA0" in _txt and "--gap:#C4542E" in _txt
                  and "family=Eczar" in _txt and "border-radius:0!important" in _txt and "dashed" in _txt))

_cr = _mp_content("reserved", text="Gold is #c9a227 here.")
_rc, _o = _mp("build", _cr, "--project", _d)
_mp_cases.append(("make_page: a PAGE colour equal to a reserved colour is refused, naming the colour",
                  _rc == 2 and "#c9a227" in _o.lower() and "reserved" in _o))

_bad = dict(_PS_STYLE, roles=dict(_PS_STYLE["roles"], accent={"color": "#c9a227"}))
_dd = _mp_proj("ps-bad", _bad)
_rc, _o = _mp("build", _c1, "--project", _dd)
_mp_cases.append(("make_page: a style-file role colour equal to a reserved colour is refused",
                  _rc == 2 and "role 'accent'" in _o))

_cv = _mp_content("visual", [["chg", "Shiny button", "Looks new.", None, "Detail.", None, None, {"visual": True}]])
_rc, _o = _mp("build", _cv, "--project", _d)
_mp_cases.append(("make_page: a required-pictures project refuses a visual Changes item with no picture, naming it",
                  _rc == 2 and "Shiny button" in _o))

_cv2 = _mp_content("visual2", [["chg", "Shiny button", "Looks new.", None, "Detail.", None, None, {"visual": True},
                                {"src": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==", "alt": "a", "caption": "c"}]])
_rc, _o = _mp("build", _cv2, "--project", _d)
_mp_cases.append(("make_page: the same visual item with a picture builds", _rc == 0))

# pictures are embedded in the page file
_pd = _mp_proj("pics", _PS_STYLE)
_pp = os.path.join(_pd, "pic")
os.makedirs(_pp, exist_ok=True)


def _pic_page(name, src):
    return _mp_content(name, [["chg", "Pic item", "L.", None, "D.", None, None, {"visual": True},
                               {"src": src, "alt": "a", "caption": "c"}]])


def _pic_src(name):
    return _mp_page_of(os.path.join(_pd, "docs", "plans", name + ".html"))["changes"][1][8]["src"]


with open(os.path.join(_pp, "a.svg"), "w") as _f:
    _f.write('<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>')
with open(os.path.join(_pp, "b.png"), "wb") as _f:
    _f.write(__import__("base64").b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="))
with open(os.path.join(_pp, "big.png"), "wb") as _f:
    _f.write(b"0" * 1000001)
_rc, _o = _mp("build", _pic_page("psvg", os.path.join(_pp, "a.svg")), "--project", _pd)
_mp_cases.append(("make_page: an SVG picture is embedded as a data: address and no -pics folder is written",
                  _rc == 0 and _pic_src("psvg").startswith("data:image/svg+xml;base64,") and "embedded" in _o
                  and not any(n.endswith("-pics") for n in os.listdir(os.path.join(_pd, "docs", "plans")))))
_rc, _o = _mp("build", _pic_page("ppng", os.path.join(_pp, "b.png")), "--project", _pd)
_mp_cases.append(("make_page: a PNG picture is embedded as image/png", _rc == 0 and _pic_src("ppng").startswith("data:image/png;base64,")))
_rc, _o = _mp("build", _pic_page("pbig", os.path.join(_pp, "big.png")), "--project", _pd)
_mp_cases.append(("make_page: a picture over 1,000,000 bytes is refused, naming file and size",
                  _rc == 2 and "big.png" in _o and "1000001" in _o))
_rc, _o = _mp("build", _pic_page("pweb", "https://example.com/x.png"), "--project", _pd)
_mp_cases.append(("make_page: a picture linked from the web is refused", _rc == 2 and "linked from the web" in _o))
_rc, _o = _mp("build", _pic_page("pdata", "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="), "--project", _pd)
_mp_cases.append(("make_page: an existing data: picture is left unchanged", _rc == 0 and _pic_src("pdata") == "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="))

_tk = os.path.join(_mp_tmp, "tokens.json")
with open(_tk, "w", encoding="utf-8") as f:
    json.dump({"color": {"tokens": [{"name": "background", "value": {"dark": "#101010"}},
                                    {"name": "text", "value": {"dark": "#eeeeee"}},
                                    {"name": "accent-lapis", "value": {"dark": "#7A6AA0"}}]},
               "type": {"families": {"display": "Eczar, serif", "body": "Spectral, serif"}},
               "radius": {"tokens": [{"name": "sm", "value": "0"}]}}, f)
_d = _mp_proj("drafty", {"use": "defaults"})
_rc, _o = _mp("style", "--draft", "--from", _tk, "--project", _d)
_dp = os.path.join(_d, "docs", "page-style.draft.json")
if os.path.isfile(_dp):
    with open(_dp, encoding="utf-8") as _f:
        _dj = json.load(_f)
else:
    _dj = {}
with open(os.path.join(_d, "docs", "page-style.json"), encoding="utf-8") as _f:
    _kept = json.load(_f)
_mp_cases.append(("make_page: style --draft --from writes docs/page-style.draft.json, prints the role guesses, leaves page-style.json alone",
                  _rc == 0 and _dj.get("colors", {}).get("background") == "#101010" and _dj.get("fonts", {}).get("display") == "Eczar"
                  and _dj.get("shape", {}).get("corner_radius") == 0 and "confirm" in _o and _kept == {"use": "defaults"}))

# Colours named for what they are, with their job only in the usage note, shaped like PlunderSpell's
# tokens.json (checked against the real file on 2026-10-15).
_tk2 = os.path.join(_mp_tmp, "pigments.json")
with open(_tk2, "w", encoding="utf-8") as f:
    json.dump({"color": {"tokens": [
        {"name": "bone-black", "value": {"dark": "#14120E"}, "usage": "Page/app background."},
        {"name": "vellum", "value": {"dark": "#DCD2BA"}, "usage": "Primary text."},
        {"name": "vellum-faint", "value": {"dark": "#635C4C"}, "usage": "Tertiary text and rules -- hairline dividers."},
        {"name": "verdigris", "value": {"dark": "#5FA288"}, "usage": "The accent. Carries every interactive element."},
        {"name": "verdigris-lo", "value": {"dark": "#2E4C41"}, "usage": "Low-emphasis verdigris -- deep accent fields."},
        {"name": "orpiment", "value": {"dark": "#C9A227"}, "usage": "Spent on nothing but gold. No other UI element may use it."},
        {"name": "madder", "value": {"dark": "#C4542E"}, "usage": "Danger. Alarm states."},
        {"name": "lapis", "value": {"dark": "#7A6AA0"}, "usage": "Reserved for the voice."},
        {"name": "line", "value": {"dark": "#332D22"}, "usage": "Structural hairline border."}]}}, f)
_d = _mp_proj("pigments", {"use": "defaults"})
_rc, _o = _mp("style", "--draft", "--from", _tk2, "--project", _d)
with open(os.path.join(_d, "docs", "page-style.draft.json"), encoding="utf-8") as _f:
    _dj = json.load(_f)
_roles = {k: v.get("color") for k, v in _dj.get("roles", {}).items()}
_mp_cases.append(("make_page: a draft reads usage notes, prefers a token's own name, keeps shades out of a second role and reserves a one-meaning colour",
                  _rc == 0 and _dj.get("colors", {}).get("background") == "#14120E" and _dj.get("colors", {}).get("line") == "#332D22"
                  and _roles.get("you_act") == "#5FA288" and _roles.get("blocking") == "#C4542E" and _roles.get("accent") == "#7A6AA0"
                  and [r["color"] for r in _dj.get("reserved", [])] == ["#C9A227"]))

_orig = os.path.join(ROOT, "docs", "plans", "enforced-checkpoints-design.page.json")
if not os.path.isfile(_orig):
    if IN_REPO:
        _mp_cases.append(("make_page: rebuilding the enforced-checkpoints design page (content file missing in a checkout)", False))
    else:
        report("SKIP", "make_page: rebuilding the enforced-checkpoints design page reproduces its PAGE data (repo-only file)")
else:
    _d = _mp_proj("rebuild")
    _mp("style", "--quick", "--project", _d)
    _rc, _o = _mp("build", _orig, "--project", _d)
    _built = _mp_page_of(os.path.join(_d, "docs", "plans", "enforced-checkpoints-design.html")) if _rc == 0 else None
    with open(_orig, encoding="utf-8") as _f:
        _want = json.load(_f)
    _mp_cases.append(("make_page: rebuilding the enforced-checkpoints design page gives the PAGE data of the content file",
                      _built is not None and _built == _want))

# QA mode (#268): counts from git, the plan's estimates beside them, the page recorded in the stage file.
def _mp_git(d, *a):
    return subprocess.run(["git", "-C", d, "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"] + list(a),
                          capture_output=True, text=True, timeout=60).stdout


_d = _mp_proj("qa", {"use": "defaults"})
_mp_git(_d, "init", "-q", "-b", "main")
for _n, _t in (("planned.py", "a\n"), ("untouched.py", "u\n")):
    with open(os.path.join(_d, _n), "w", encoding="utf-8") as _f:
        _f.write(_t)
_mp_git(_d, "add", "-A")
_mp_git(_d, "commit", "-q", "-m", "base")
with open(os.path.join(_d, "planned.py"), "w", encoding="utf-8") as _f:
    _f.write("a\nb\nc\n")
with open(os.path.join(_d, "extra.py"), "w", encoding="utf-8") as _f:
    _f.write("x\ny\n")
_mp_git(_d, "add", "-A")
_mp_git(_d, "commit", "-q", "-m", "work")
_ns = {}
for _l in _mp_git(_d, "diff", "--numstat", "main~1...HEAD").splitlines():
    _a, _r, _f = _l.split("\t")
    _ns[_f] = (int(_a), int(_r))
_qa = {"feature": "demo feature", "base": "main~1", "unverified": ["The live run."],
       "files": {"planned.py": [5, 0, "grow"], "untouched.py": [3, 1, "tidy"]}}


def _mp_qa_content(name, qa):
    c = _mp_content(name)
    with open(c, encoding="utf-8") as f:
        pg = json.load(f)
    pg["qa"], pg["reply"] = qa, "old reply"
    with open(c, "w", encoding="utf-8") as f:
        json.dump(pg, f)
    return c


_acc = __import__("acceptance")
_qaf = os.path.join(_d, "docs", "qa", "demo-feature")


def _mp_stamp(proj=_d, folder=_qaf):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "acceptance-stamp.json"), "w", encoding="utf-8") as f:
        json.dump({"tree": _acc.tree(proj)}, f)


def _mp_text(name):
    p = os.path.join(_d, "docs", "plans", name + ".html")
    return open(p, encoding="utf-8").read() if os.path.isfile(p) else ""


_rc, _o = _mp("build", _mp_qa_content("qa0", _qa), "--project", _d)
_mp_cases.append(("make_page (#596): QA mode with no acceptance stamp is refused (exit 2), naming the stamp and the acceptance run",
                  _rc == 2 and "stamp missing" in _o and "acceptance run first" in _o and "acceptance.py stamp" in _o))
_mp_stamp()
with open(os.path.join(_d, "planned.py"), "a", encoding="utf-8") as _f:
    _f.write("d\n")
_rc, _o = _mp("build", _mp_qa_content("qa0", _qa), "--project", _d)
_mp_cases.append(("make_page (#596): QA mode with a stale stamp is refused (exit 2)", _rc == 2 and "stale" in _o))
_mp_git(_d, "checkout", "-q", "planned.py")
_stage = os.path.join(_d, ".claude", "house-rules-loop.json")
_rc, _o = _mp("build", _mp_qa_content("qa1", _qa), "--project", _d)
_mp_cases.append(("make_page: QA mode with no stage file builds, creates none and says it did not record",
                  _rc == 0 and not os.path.exists(_stage) and "not recorded" in _o))
_pg = _mp_page_of(os.path.join(_d, "docs", "plans", "qa1.html")) or {"changes": [], "replyPrefix": "", "reply": "x"}
_fc = next((c for c in _pg["changes"] if c[1].startswith("Files changed, counted from git against main~1")), None)
_rows = {r[0]: r for r in (_fc[6] if _fc else [])}
_mp_cases.append(("make_page: QA mode file counts equal git diff --numstat",
                  _fc is not None and all(_rows[f][1:3] == list(v) for f, v in _ns.items()) and set(_ns) <= set(_rows)
                  and _fc[2] == "%d files, +%d −%d" % (len(_ns), sum(v[0] for v in _ns.values()), sum(v[1] for v in _ns.values()))))
_mp_cases.append(("make_page: QA mode marks an unplanned file 'Not in the plan' and an untouched planned file 'Planned but not changed'",
                  _rows.get("extra.py", [0] * 4)[3] == [["Not in the plan", 0, 0]]
                  and _rows.get("untouched.py", [0] * 4)[3] == [["Planned but not changed: tidy", 3, 1]]
                  and _rows.get("planned.py", [0] * 4)[3] == [["Plan estimate: grow", 5, 0]]))
_mp_cases.append(("make_page: QA mode sets approval to the QA passed phrase and adds the Still unverified item",
                  _pg.get("approval") == "QA passed: demo feature" and "replyPrefix" not in _pg
                  and any(c[0] == "keep" and c[1] == "Still unverified" and c[2] == "1 things not yet proven" for c in _pg["changes"])))
_rc, _o = _mp("build", _mp_qa_content("qa1", _qa), "--project", _d)
_mp_cases.append(("make_page (#596): building the same QA page twice works (the built page does not stale the stamp)", _rc == 0))
_rc, _o = _mp("build", _mp_qa_content("qa2", dict(_qa, unverified=[])), "--project", _d)
_t2 = _mp_text("qa2")
_mp_cases.append(("make_page (#596): QA mode with an empty unverified list builds and says nothing is unverified, 0 things",
                  _rc == 0 and "Nothing is unverified: every acceptance item passed the acceptance run" in _t2
                  and "0 things not yet proven" in _t2))
_mp_cases.append(("make_page (#596): a non-empty unverified list is unchanged",
                  "1 things not yet proven" in _mp_text("qa1") and "The live run." in _mp_text("qa1")))
_nm = {"title": "Run it", "folder": "/home/aj/proj", "shell": "bash", "command": 'git -C "/home/aj/proj" status', "expect": "clean tree"}
_rc, _o = _mp("build", _mp_qa_content("qa4", dict(_qa, needs_machine=[_nm, dict(_nm, title="Second", untested=False)])), "--project", _d)
_t4 = _mp_text("qa4")
_mp_cases.append(("make_page (#596): needs_machine renders one item with UNTESTED first, folder, shell, command, what aj sees; untested false drops the line",
                  _rc == 0 and "Needs your machine" in _t4 and "2 step(s), one command each" in _t4
                  and "Run it\\nUNTESTED:\\nFolder: /home/aj/proj, shell: bash\\nCommand: git -C" in _t4
                  and "You should see: clean tree" in _t4 and "Second\\nFolder:" in _t4))
_rc, _o = _mp("build", _mp_qa_content("qa5", dict(_qa, needs_machine=[dict(_nm, command="")])), "--project", _d)
_mp_cases.append(("make_page (#596): a needs_machine entry missing a field is refused, naming the entry and the field",
                  _rc == 2 and "entry 0 (Run it) needs command" in _o))
_mp_cases.append(("make_page (#596): no ledger file adds no deviations item", "Deviations and parked" not in _mp_text("qa1")))
with open(os.path.join(_qaf, "ledger.md"), "w", encoding="utf-8") as _f:
    _f.write("| # | s | plan | done | why | undo |\n|---|---|---|---|---|---|\n| D1 | 1 | p | Did the thing. | w | u |\n"
             "| D2 | 1 | p | Did another. | w | u |\n\n| # | s | Question | Default |\n| P1 | 2 | Which way? | x |\n")
_rc, _o = _mp("build", _mp_qa_content("qa6", _qa), "--project", _d)
_t6 = _mp_text("qa6")
_mp_cases.append(("make_page (#596): ledger rows come first with right counts",
                  _rc == 0 and "2 deviation(s), 1 parked" in _t6 and "D1: Did the thing.\\nD2: Did another.\\nP1: Which way?" in _t6
                  and _t6.index("Deviations and parked") < _t6.index("Files changed, counted")))
with open(os.path.join(_qaf, "ledger.md"), "w", encoding="utf-8") as _f:
    _f.write("# empty\n")
_rc, _o = _mp("build", _mp_qa_content("qa7", _qa), "--project", _d)
_mp_cases.append(("make_page (#596): a ledger with no D or P rows says None recorded, 0 and 0",
                  _rc == 0 and "None recorded" in _mp_text("qa7") and "0 deviation(s), 0 parked" in _mp_text("qa7")))
os.remove(os.path.join(_qaf, "ledger.md"))


def _park(*a):
    r = subprocess.run([sys.executable, os.path.join(HERE, "ledger_note.py"), "park", "Demo Feature", "--step", "6", "--default", "d",
                        "--affects", "x", "--category", "login", "--tried", "cmd -> denied"] + list(a), cwd=_d, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    return r.returncode, r.stdout + r.stderr


_rc1, _o1 = _park("--question", "First?")
_ledg = open(os.path.join(_qaf, "ledger.md"), encoding="utf-8").read()
_mp_cases.append(("ledger_note (#598): park creates the file with both tables and P1, printing where",
                  _rc1 == 0 and _o1.startswith("parked P1 in ") and "## Deviations" in _ledg and "## Parked decisions" in _ledg
                  and "| # | Step | The plan said | What was done | Why | How to undo |" in _ledg
                  and "| P1 | 6 | [login] First? (tried: cmd -> denied) | d | x | Reply with the answer" in _ledg))
_rc2, _o2 = _park("--question", "Use a|b?\nsecond line")
_ledg = open(os.path.join(_qaf, "ledger.md"), encoding="utf-8").read()
_mp_cases.append(("ledger_note (#598): a second park is P2 after P1, and a | or newline in a cell is escaped",
                  _rc2 == 0 and _o2.startswith("parked P2 in ") and _ledg.index("| P1 ") < _ledg.index("| P2 ")
                  and "| P2 | 6 | [login] Use a\\|b? second line (tried: cmd -> denied) | d | x |" in _ledg))
_rc, _o = _mp("build", _mp_qa_content("qa8", _qa), "--project", _d)
_mp_cases.append(("make_page (#598): an escaped pipe in a parked question is shown whole, as a |",
                  "P2: [login] Use a|b? second line" in _mp_text("qa8")))
_mp_cases.append(("ledger_note (#598): the QA page lists the parked rows with 0 deviations, 2 parked",
                  _rc == 0 and "0 deviation(s), 2 parked" in _mp_text("qa8") and "P1: [login] First?" in _mp_text("qa8")))
_rc, _o = _park()
_mp_cases.append(("ledger_note (#598): a missing required option is refused, naming it",
                  _rc == 2 and "--question" in _o))
def _dev(*a):
    r = subprocess.run([sys.executable, os.path.join(HERE, "ledger_note.py"), "deviate", "Demo Feature", "--step", "7", "--plan", "p",
                        "--done", "d", "--why", "w", "--undo", "u"] + list(a), cwd=_d, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, universal_newlines=True)
    return r.returncode, r.stdout + r.stderr


_rc, _o = _dev()
_ledg = open(os.path.join(_qaf, "ledger.md"), encoding="utf-8").read()
_mp_cases.append(("ledger_note (#599): deviate adds D1 to the Deviations table, above the parked rows, printing where",
                  _rc == 0 and _o.startswith("deviated D1 in ") and "| D1 | 7 | p | d | w | u |" in _ledg
                  and _ledg.index("| D1 ") < _ledg.index("## Parked decisions") and "| P2 " in _ledg))
_rc, _o = _dev("--plan", "a|b")
_ledg = open(os.path.join(_qaf, "ledger.md"), encoding="utf-8").read()
_mp_cases.append(("ledger_note (#599): a second deviate is D2 and a | in a cell is escaped",
                  _rc == 0 and _o.startswith("deviated D2 in ") and "| D2 | 7 | a\\|b |" in _ledg))
_rc, _o = subprocess.run([sys.executable, os.path.join(HERE, "ledger_note.py"), "park", "Demo Feature", "--step", "6", "--question", "q",
                          "--default", "d", "--affects", "x"], cwd=_d, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         universal_newlines=True), None
_mp_cases.append(("ledger_note (#638): park is refused without a --category and --tried, naming them",
                  _rc.returncode == 2 and "--category" in _rc.stderr and "--tried" in _rc.stderr))


def _dec(feat, *a):
    r = subprocess.run([sys.executable, os.path.join(HERE, "ledger_note.py"), "decide", feat, "--step", "3", "--choice", "blue header",
                        "--assumption", "brand is blue", "--why", "matches logo", "--undo", "edit css"] + list(a), cwd=_d,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    return r.returncode, r.stdout + r.stderr


_rc, _o = _dec("Demo Feature")
_ledg = open(os.path.join(_qaf, "ledger.md"), encoding="utf-8").read()
_rc2, _o2 = _mp("build", _mp_qa_content("qa9", _qa), "--project", _d)
_t9 = _mp_text("qa9")
_mp_cases.append(("ledger_note (#638): decide adds K1 to the Choices table, and the QA page shows it first, before D and P rows, with why and undo",
                  _rc == 0 and _o.startswith("decided K1 in ") and "| K1 | 3 | blue header | brand is blue | matches logo | edit css |" in _ledg
                  and _rc2 == 0 and "K1: blue header (why: matches logo; undo: edit css)" in _t9
                  and _t9.index("K1: ") < _t9.index("D1: ") < _t9.index("P1: ") and "1 choice(s)" in _t9))
with open(os.path.join(_qaf, "ledger.md"), "w", encoding="utf-8") as _f:
    _f.write("# old\n\n## Deviations\n\n| # | Step | The plan said | What was done | Why | How to undo |\n|---|---|---|---|---|---|\n"
             "| D1 | 1 | p | d | w | u |\n\n## Parked decisions\n\n| # | Step | Question | Default taken for now | What it affects | How to answer |\n"
             "|---|---|---|---|---|---|\n")
_rc, _o = _dec("Demo Feature")
_ledg = open(os.path.join(_qaf, "ledger.md"), encoding="utf-8").read()
_mp_cases.append(("ledger_note (#638): decide on an older ledger with no Choices table inserts the table and K1, keeping D1",
                  _rc == 0 and "## Choices" in _ledg and "| K1 | 3 | blue header |" in _ledg and "| D1 | 1 | p |" in _ledg
                  and _ledg.index("## Choices") < _ledg.index("| K1 ") < _ledg.index("## Deviations")))
_mp_cases.append(("make_page (#638): a feature or branch name with a slash is one folder, - for /",
                  __import__("make_page").qa_folder("AjsAgent/Quiet Mode") == "ajsagent-quiet-mode"))
os.remove(os.path.join(_qaf, "ledger.md"))
_mp_cases.append(("rules (#598): show-dont-tell.md names ledger_note.py park and [HARD STOP], and is no longer than 3307 chars",
                  all(w in read(os.path.join(HERE, "..", "rules", "show-dont-tell.md")) for w in ("ledger_note.py park", "[HARD STOP]"))
                  and len(read(os.path.join(HERE, "..", "rules", "show-dont-tell.md"))) <= 3307))
# P3: the fingerprint ignores built pages but not plan markdown or source
_t0 = _acc.tree(_d)
os.makedirs(os.path.join(_d, "docs", "plans"), exist_ok=True)
with open(os.path.join(_d, "docs", "plans", "zz.html"), "w", encoding="utf-8") as _f:
    _f.write("<p>a</p>")
_t1 = _acc.tree(_d)
with open(os.path.join(_d, "docs", "plans", "zz.html"), "w", encoding="utf-8") as _f:
    _f.write("<p>b</p>")
_t2f = _acc.tree(_d)
with open(os.path.join(_d, "docs", "plans", "zz.md"), "w", encoding="utf-8") as _f:
    _f.write("m")
_t3 = _acc.tree(_d)
with open(os.path.join(_d, "extra.py"), "a", encoding="utf-8") as _f:
    _f.write("z\n")
_t4f = _acc.tree(_d)
_mp_cases.append(("acceptance (P3): the fingerprint ignores docs/plans/*.html added or edited, changes for docs/plans/*.md and for source",
                  _t0 == _t1 == _t2f and _t3 != _t2f and _t4f != _t3))
os.remove(os.path.join(_d, "docs", "plans", "zz.md"))
_mp_git(_d, "checkout", "-q", "extra.py")
os.makedirs(os.path.dirname(_stage))
with open(_stage, "w", encoding="utf-8") as _f:
    json.dump({"feature": "demo", "stage": "Build"}, _f)
_rc, _o = _mp("build", _mp_qa_content("qa3", _qa), "--project", _d)
with open(_stage, encoding="utf-8") as _f:
    _sd = json.load(_f)
_mp_cases.append(("make_page: QA mode writes qa_page into an existing stage file and keeps its other keys",
                  _rc == 0 and _sd == {"feature": "demo", "stage": "Build", "qa_page": "docs/plans/qa3.html"}))

# The copy box must hold the exact phrase the design-loop gate accepts (#286).
_hk_spec = _ig_util.spec_from_file_location("hook_for_approval", HOOK)
_hk = _ig_util.module_from_spec(_hk_spec)
_hk_spec.loader.exec_module(_hk)
_gate = lambda t: bool(_hk.design_loop._LOOP_DESIGN_RE.search(t) or _hk.design_loop._LOOP_PLAN_RE.search(t))
_d = _mp_proj("appr", {"use": "defaults"})
_rc, _o = _mp("build", _mp_content("noappr", approval=None), "--project", _d)
_mp_cases.append(("make_page: a non-QA page with no approval field is refused with exit 2 naming approval",
                  _rc == 2 and "approval" in _o))
_rc, _o = _mp("build", _mp_content("badappr", approval="Guards audit"), "--project", _d)
_mp_cases.append(("make_page (#502): a design page whose approval line the gate rejects is refused (exit non-zero)",
                  _rc != 0 and "would not open the design-loop gate" in _o))
_rc, _o = _mp("build", _mp_content("forrepo", approval="Guards audit", forRepo="owner/other"), "--project", _d)
_mp_cases.append(("make_page (#309, #502): the same line builds with forRepo set, with a note that it moves no stage",
                  _rc == 0 and "moves no stage" in _o))
_ch = [["c1", "Which?", [["A", "Option A", 1, "one"], ["B", "Option B", 0, "two"]], ""]]
_ph = "Build plan approved: guards <audit> & more"
_rc1, _ = _mp("build", _mp_content("withch", approval=_ph, choices=_ch), "--project", _d)
_rc2, _ = _mp("build", _mp_content("noch", approval=_ph, choices=[]), "--project", _d)
_pw = {n: _mp_page_of(os.path.join(_d, "docs", "plans", n + ".html")) for n in ("withch", "noch")} if _rc1 == _rc2 == 0 else {}
_mp_cases.append(("make_page: the last to-do line carries the approval phrase, HTML-escaped",
                  bool(_pw) and all(pg["wrapup"]["todo"][-1] == 'Tap <b>Copy my reply</b> and send it: "Build plan approved: guards &lt;audit&gt; &amp; more", or say what to change.'
                                    for pg in _pw.values())))
# #600: a two-line approval, the design line then the build-plan line.
_two = "Design approved: combo\nBuild plan approved: combo"
_rc, _o = _mp("build", _mp_content("two", approval=_two, choices=_ch), "--project", _d)
_pg2 = _mp_page_of(os.path.join(_d, "docs", "plans", "two.html")) if _rc == 0 else None
_mp_cases.append(("make_page (#600): a two-line approval (design, then build plan) builds and the page holds both lines",
                  bool(_pg2) and _pg2["approval"] == _two and "Design approved: combo" in _pg2["wrapup"]["todo"][-1]
                  and "Build plan approved: combo" in _pg2["wrapup"]["todo"][-1]))
_rc, _o = _mp("build", _mp_content("twobad", approval="Design approved: combo\nGuards audit"), "--project", _d)
_mp_cases.append(("make_page (#600): a bad second approval line is refused and the message names it",
                  _rc != 0 and "'Guards audit'" in _o))
_rc, _o = _mp("build", _mp_content("tworev", approval="Build plan approved: combo\nDesign approved: combo"), "--project", _d)
_mp_cases.append(("make_page (#600): the two lines in the wrong order are refused", _rc != 0 and "Design approved" in _o))
_NODE = shutil.which("node") or "/opt/node22/bin/node"
_PWMOD = "/opt/node22/lib/node_modules"
_JS = (r"""const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();const out={};
for(const f of process.argv.slice(2)){const p=await b.newPage();await p.goto('file://'+f);
await p.evaluate(()=>{for(const n of new Set([...document.querySelectorAll('input[type=radio]')].map(r=>r.name))){const r=document.querySelector('input[name='+n+']');r.checked=true;r.dispatchEvent(new Event('input',{bubbles:true}));r.dispatchEvent(new Event('change',{bubbles:true}));}});
out[f]=await p.evaluate(()=>document.getElementById('out').textContent);}
console.log(JSON.stringify(out));await b.close();})();""")
if not (_pw and os.path.isfile(_NODE) and os.path.isdir(os.path.join(_PWMOD, "playwright"))):
    report("SKIP", "make_page: the copied text of a built page matches the gate (no node or node playwright here)")
else:
    _jsf = os.path.join(_mp_tmp, "copy.js")
    with open(_jsf, "w", encoding="utf-8") as _f:
        _f.write(_JS)
    _pgs = [os.path.join(_d, "docs", "plans", n + ".html") for n in ("withch", "noch")]
    _r = subprocess.run([_NODE, _jsf] + _pgs, capture_output=True, text=True, timeout=180,
                        env=dict(os.environ, NODE_PATH=_PWMOD, PLAYWRIGHT_BROWSERS_PATH=os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")))
    try:
        _cp = json.loads(_r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        _cp = None
    if _cp is None:
        report("SKIP", "make_page: the copied text of a built page matches the gate (browser did not run: %s)" % (_r.stderr.strip()[-200:] or "no output"))
    else:
        _w, _n = _cp[_pgs[0]], _cp[_pgs[1]]
        _mp_cases.append(("make_page: the copied text, with choices (approval then picks) and without (approval alone), matches the gate",
                          _w == _ph + " 1A" and _n == _ph and _gate(_w) and _gate(_n)))

# a multi-line change detail (QA "Needs your machine" step cards) keeps its line breaks in the browser (#596)
_nl = _mp_content("newlines")
with open(_nl, encoding="utf-8") as _f:
    _nlp = json.load(_f)
_nlp["changes"] = [["chg", "Needs your machine", "1 step", None, "T\nUNTESTED:\nFolder: /p, shell: bash\nCommand: git status", None, None]]
with open(_nl, "w", encoding="utf-8") as _f:
    json.dump(_nlp, _f)
_d = _mp_proj("newlines")
_mp("style", "--quick", "--project", _d)
_rc, _o = _mp("build", _nl, "--project", _d)
_NLJS = (r"""const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();const p=await b.newPage();
await p.goto('file://'+process.argv[2]);const r=await p.evaluate(()=>{const d=document.querySelector('.ci');d.open=true;const e=d.querySelector('.detail p');
return {ws:getComputedStyle(e).whiteSpace,t:e.innerText}});console.log(JSON.stringify(r));await b.close();})();""")
if not (_rc == 0 and os.path.isfile(_NODE) and os.path.isdir(os.path.join(_PWMOD, "playwright"))):
    report("SKIP", "make_page (#596): multi-line detail keeps its lines (no node/playwright or build failed)")
else:
    _nlf = os.path.join(_mp_tmp, "nl.js")
    with open(_nlf, "w", encoding="utf-8") as _f:
        _f.write(_NLJS)
    _r = subprocess.run([_NODE, _nlf, os.path.join(_d, "docs", "plans", "newlines.html")], capture_output=True, text=True, timeout=180,
                        env=dict(os.environ, NODE_PATH=_PWMOD, PLAYWRIGHT_BROWSERS_PATH=os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")))
    try:
        _nr = json.loads(_r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        _nr = None
    if _nr is None:
        report("SKIP", "make_page (#596): multi-line detail keeps its lines (browser did not run: %s)" % (_r.stderr.strip()[-200:] or "no output"))
    else:
        _mp_cases.append(("make_page (#596): a multi-line change detail renders each line on its own line",
                          _nr["ws"] == "pre-line" and "\nUNTESTED:\n" in _nr["t"]))

# a 40-character unbroken word in card text must not clip on a phone (#288); the old 1fr CSS must be caught
_LONGW = "HOUSE_RULES_AGENT_NAME_WITH_A_VERY_LONG_TAIL_X"
_lw = _mp_content("longword")
with open(_lw, encoding="utf-8") as _f:
    _lwp = json.load(_f)
_lwp["short"]["items"] = [["bulb", "Your name", "The idea", "", _LONGW, _LONGW]]
_lwp["changes"] = [["new", "A thing", "One line.", ["old " + _LONGW, _LONGW], "Detail " + _LONGW, None, None]]
with open(_lw, "w", encoding="utf-8") as _f:
    json.dump(_lwp, _f)
_d = _mp_proj("longword")
_mp("style", "--quick", "--project", _d)
_rc, _o = _mp("build", _lw, "--project", _d)
if "visual check did not run" in _o or "visual check" not in _o:
    report("SKIP", "make_page: a 40-character unbroken word does not clip a card (no usable Chromium/playwright: %s)" % _o.strip()[-200:])
else:
    _mp_cases.append(("make_page: a 40-character unbroken word in card text builds with no clipped card",
                      _rc == 0 and "clipped card" not in _o and "overflow none" in _o))
    _hp = os.path.join(_d, "docs", "plans", "longword.html")
    _old = re.sub(r"@media \(max-width:479px\)[^\n]*\n", "", open(_hp, encoding="utf-8").read()
                  .replace("minmax(0,1fr)", "1fr").replace("overflow-wrap:anywhere", "overflow-wrap:normal"))
    _hp2 = os.path.join(_d, "docs", "plans", "oldcss.html")
    with open(_hp2, "w", encoding="utf-8") as _f:
        _f.write(_old)
    _r = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, %r); import make_page; make_page.visual_check(sys.argv[1], {})" % HERE, _hp2],
                        capture_output=True, text=True, timeout=300)
    _mp_cases.append(("make_page: the same page with the old 1fr CSS is reported as a clipped card and fails the check",
                      'clipped card' in _r.stdout and _r.returncode == 2))
_d_out = _mp_proj("outside", _PS_STYLE)
_d_cwd = os.path.join(_mp_tmp, "cwdfolder")
os.makedirs(_d_cwd, exist_ok=True)
_r_out = subprocess.run([sys.executable, MAKE_PAGE, "build", _c1, "--project", _d_out], cwd=_d_cwd, capture_output=True, text=True, timeout=300)
_r_in = subprocess.run([sys.executable, MAKE_PAGE, "build", _c1, "--project", _d_out], cwd=_d_out, capture_output=True, text=True, timeout=300)
_mp_cases.append(("make_page (#331): a page written outside the folder it runs in prints the 'is outside' line",
                  _r_out.returncode == 0 and "is outside" in _r_out.stdout))
_mp_cases.append(("make_page (#331): a page written inside the folder it runs in prints no 'is outside' line",
                  _r_in.returncode == 0 and "is outside" not in _r_in.stdout))
# ---- summary pages (#339 part B) ----
_ds_start = os.path.join(HERE, "..", "templates", "decision-summary.page.json")
_ds_d = _mp_proj("dsum")
_mp("style", "--quick", "--project", _ds_d)
_rc, _o_ds = _mp("build", _ds_start, "--project", _ds_d)
_ds_h = open(os.path.join(_ds_d, "docs", "plans", "decision-summary.html"), encoding="utf-8").read() if _rc == 0 else ""
print("make_page build of the starter:\n" + _o_ds)
_mp_cases.append(("summary (#339): the starter builds and its row detail says 'Decided by', not 'Requires'",
                  _rc == 0 and "Decided by" in _ds_h and 'PAGE.kind === "summary"' in _ds_h and '"kind": "summary"' in _ds_h))
if "visual check did not run" in _o_ds:
    # Same as the other visual cases: a machine with no browser (the CI runner) skips, naming why.
    report("SKIP", "summary (#339): the starter builds clean in the phone-width visual check (%s)"
           % _o_ds.split("visual check did not run:", 1)[1].strip()[:200])
else:
    _mp_cases.append(("summary (#339): the starter builds clean in the phone-width visual check",
                      _rc == 0 and "visual check" in _o_ds and "clipped card" not in _o_ds))
_ds_bad = json.load(open(_ds_start, encoding="utf-8"))
_ds_bad["kind"] = "plan"
_ds_bp = os.path.join(_mp_tmp, "badkind.page.json")
json.dump(_ds_bad, open(_ds_bp, "w", encoding="utf-8"))
_rc, _o = _mp("build", _ds_bp, "--project", _ds_d)
_mp_cases.append(("summary (#339): 'kind': 'plan' makes make_page exit non-zero and names 'summary'", _rc != 0 and "summary" in _o))
_dp = _mp_page_of(os.path.join(_ds_d, "docs", "plans", "decision-summary.html"))
_ds_items = _dp["short"]["items"] if _dp else []
_mp_cases.append(("summary (#339): a list in creates is kept as a list and the template renders list items (<li>)",
                  isinstance(_ds_items[0][4], list) and "<ul class=\"cl\">" in _ds_h and "<li>${esc(x)}</li>" in _ds_h))
_mp_cases.append(("summary (#339): a row with a 3-string strip is kept and rendered with the flow strip",
                  len(_ds_items[0]) > 6 and len(_ds_items[0][6]) == 3 and "${strip ? flow(strip)" in _ds_h))
_rc, _o = _mp("build", _c1, "--project", _ds_d)
_nk_h = open(os.path.join(_ds_d, "docs", "plans", "basic.html"), encoding="utf-8").read() if _rc == 0 else ""
_mp_cases.append(("summary (#339): a content file with no kind has no kind in its PAGE and still carries the Requires label",
                  _rc == 0 and '"kind"' not in _nk_h.split("const PAGE", 1)[1].split("\n};", 1)[0] and 'ic("hand") + "Requires"' in _nk_h))
# A14: the node check runs `node -e <script> make_page <page> ...`, so require resolves from the folder the probe ran in
_nd = os.path.join(_mp_tmp, "fakenode")
os.makedirs(_nd)
_nlog = os.path.join(_mp_tmp, "node-args.bin")
with open(os.path.join(_nd, "node"), "w", encoding="utf-8") as _f:
    _f.write('#!/bin/sh\nprintf \'%s\\0\' "$@" > "$NODE_ARGS_LOG"\nexit 0\n')
os.chmod(os.path.join(_nd, "node"), 0o755)
_nprobe = "import importlib.util as u, make_page as m; u.find_spec = lambda n: None; m.visual_check('PAGE.html', {})"
if os.name == "nt":
    # Windows cannot run a #!/bin/sh script as `node`, and a .cmd wrapper cannot pass the long script argument
    # faithfully, so the probe records the arguments in a stand-in for subprocess.run instead.
    _nprobe = ("import importlib.util as u, os, shutil, subprocess, make_page as m\n"
               "u.find_spec = lambda n: None\n"
               "shutil.which = lambda n: 'node' if n == 'node' else None\n"
               "_run = subprocess.run\n"
               "def _fake(cmd, **k):\n"
               "    if cmd and cmd[0] == 'node':\n"
               "        open(os.environ['NODE_ARGS_LOG'], 'wb').write(b''.join(a.encode('utf-8') + b'\\0' for a in cmd[1:]))\n"
               "        return subprocess.CompletedProcess(cmd, 0, '', '')\n"
               "    return _run(cmd, **k)\n"
               "subprocess.run = _fake\n"
               "m.visual_check('PAGE.html', {})\n")
subprocess.run([sys.executable, "-c", _nprobe],
               env=dict(os.environ, PATH=_nd, NODE_ARGS_LOG=_nlog, PYTHONPATH=HERE), capture_output=True, text=True, timeout=60)
try:
    _nargs = open(_nlog, "rb").read().decode("utf-8").split("\0")
except OSError:
    _nargs = []
_mp_cases.append(("A14: the node check runs `node -e`, with the page path as the fifth word",
                  len(_nargs) > 4 and _nargs[0] == "-e" and _nargs[3] == "PAGE.html"))
# ---- page_criteria.py: a page checked against the seven basics (#542) ----
sys.path.insert(0, HERE)
import page_criteria as _pc


def _pcp(typ, drop=(), add="", body_extra=""):
    parts = {"summary": '<p data-basic="summary">A short summary of the page.</p>',
             "next": '<p data-basic="next">Next: tick the box.</p>',
             "pic": '<svg width="1" height="1"></svg>', "steps": '<ol><li>One step.</li></ol>',
             "check": '<input type="checkbox"> done',
             "exists": '<p data-basic="exists">It exists.</p>', "suggested": '<p data-basic="suggested">Do it.</p>',
             "done-when": '<p data-basic="done-when">When green.</p>', "unverified": '<p data-basic="unverified">Not run.</p>',
             "finding": '<p data-basic="finding">A finding.</p>'}
    want = {"proposal": ["exists", "suggested", "check"], "build-plan": ["done-when", "check"], "qa": ["unverified", "check"],
            "review": ["finding"], "art": []}[typ]
    keys = ["summary", "next", "pic"] + (["steps"] if typ != "art" else []) + want
    meta = '<meta name="house-rules-page" content="%s">' % typ
    return meta + "".join(parts[k] for k in keys if k not in drop) + add + body_extra


for _typ in _pc.TYPES:
    _mp_cases.append(("page_criteria (#542): a complete %s page passes" % _typ, _pc.check(_pcp(_typ)) == []))
for _name, _typ, _drop, _word in (("basic 1 summary", "art", ("summary",), "Basic 1"), ("basic 2 next", "art", ("next",), "Basic 2"),
                                  ("basic 3 picture", "art", ("pic",), "Basic 3"), ("basic 5 steps", "qa", ("steps",), "Basic 5"),
                                  ("basic 6 checklist", "qa", ("check",), "Basic 6"),
                                  ("extras exists", "proposal", ("exists",), "exists"), ("extras done-when", "build-plan", ("done-when",), "done-when"),
                                  ("extras unverified", "qa", ("unverified",), "unverified"), ("extras finding", "review", ("finding",), "finding")):
    _m = _pc.check(_pcp(_typ, drop=_drop))
    _mp_cases.append(("page_criteria (#542): a page missing %s fails and names it" % _name, len(_m) == 1 and _word in _m[0]))
_m = _pc.check(_pcp("qa", drop=("check",)).replace('<meta name="house-rules-page" content="qa">', ""))
_mp_cases.append(("page_criteria (#542): a page with no type and no checklist names both in one result",
                  len(_m) == 2 and "no known type" in _m[0] and "Basic 6 (checklist)" in _m[1]))
_m = _pc.check(_pcp("art", drop=("summary",), add='<p data-basic="summary">%s</p>' % ("w " * 41)))
_mp_cases.append(("page_criteria (#542): a 41-word summary fails basic 1", len(_m) == 1 and "Basic 1" in _m[0]))
_long = "alpha beta gamma delta epsilon zeta eta theta " + "w " * 60
_m = _pc.check(_pcp("art", add="<p>%s</p>" % _long))
_mp_cases.append(("page_criteria (#542): a block over 60 words fails basic 4 and names its first 8 words",
                  len(_m) == 1 and "Basic 4" in _m[0] and "alpha beta gamma delta epsilon zeta eta theta" in _m[0]))
_mp_cases.append(("page_criteria (#542): the same long block inside details does not fail basic 4",
                  _pc.check(_pcp("art", add="<details><summary>More</summary><p>%s</p></details>" % _long)) == []))
_mp_cases.append(("page_criteria (#542): a review page with you-act needs a checklist (basic 6)",
                  any("Basic 6" in x for x in _pc.check(_pcp("review", add='<p data-basic="you-act">Act</p>')))))
_mp_cases.append(("page_criteria (#542): a missing type names the five allowed values",
                  "proposal, build-plan, qa, review, art" in _pc.check("<p>x</p>")[0]))
_mp_cases.append(("page_criteria (#542): a builder-marked page passes unread",
                  _pc.check("<!doctype html>\n<!-- house-rules make_page 1.0 -->\n<p>nothing here</p>") == []))
_pc_f = os.path.join(_mp_tmp, "pc.html")
with open(_pc_f, "w", encoding="utf-8") as _f:
    _f.write(_pcp("art", drop=("pic",)))
_pc_r = subprocess.run([sys.executable, os.path.join(HERE, "page_criteria.py"), _pc_f], capture_output=True, text=True, timeout=60)
_pc_u = subprocess.run([sys.executable, os.path.join(HERE, "page_criteria.py"), _pc_f + ".nope"], capture_output=True, text=True, timeout=60)
_mp_cases.append(("page_criteria (#542): the command exits 1 naming the miss, and 2 for an unreadable file",
                  _pc_r.returncode == 1 and "Basic 3" in _pc_r.stdout and _pc_u.returncode == 2))
# ---- the lone-copy picture check (#557): a page opened alone must not have broken pictures ----
def _lone(name, pics):
    f = os.path.join(_mp_tmp, name + ".html")
    with open(f, "w", encoding="utf-8") as _f:
        _f.write(_pcp("art", add=pics))
    return subprocess.run([sys.executable, os.path.join(HERE, "page_criteria.py"), f, "--visual"], capture_output=True, text=True, timeout=300)


_ln_bad = _lone("lone-bad", '<img src="gone-pics/a.svg" alt="x">')
if "visual check did not run" in _ln_bad.stdout:
    report("SKIP", "page_criteria (#557): the lone-copy picture check (no usable browser: %s)"
           % _ln_bad.stdout.split("visual check did not run:", 1)[1].strip()[:200])
else:
    _ln_ok = _lone("lone-data", '<img alt="x" src="data:image/svg+xml;utf8,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 width=%272%27 height=%272%27%3E%3Crect width=%272%27 height=%272%27/%3E%3C/svg%3E">')
    _ln_none = _lone("lone-nosrc", '<img alt="later">')
    _mp_cases.append(("page_criteria (#557): a page with img src=gone-pics/a.svg and no such folder fails and names that src",
                      _ln_bad.returncode == 2 and "gone-pics/a.svg" in _ln_bad.stdout))
    _mp_cases.append(("page_criteria (#557): a page with an embedded data: picture passes the lone-copy check",
                      _ln_ok.returncode == 0 and "broken pictures 0" in _ln_ok.stdout))
    _mp_cases.append(("page_criteria (#557): a page with an img that has no src passes the lone-copy check",
                      _ln_none.returncode == 0 and "broken pictures 0" in _ln_none.stdout))

# ---- #559: sendcheck embeds a page's broken pictures in place, never denies ----
def _sp_send(page):
    return run_hook("sendcheck", json.dumps({"tool_name": "SendUserFile", "tool_input": {"file_path": page}}), env=dict(os.environ))[1]


_sp_proj = _mp_proj("sendfix", {"use": "defaults"})
_sp_plans = os.path.join(_sp_proj, "docs", "plans")
os.makedirs(os.path.join(_sp_plans, "fix-pics"), exist_ok=True)
with open(os.path.join(_sp_plans, "fix-pics", "a.svg"), "w") as _f:
    _f.write("<svg xmlns='http://www.w3.org/2000/svg' width='4' height='4'><rect width='4' height='4'/></svg>")
_sp_src = _mp_content("fix", [["chg", "Pic", "Looks new.", None, "Detail.", None, None, {"visual": True},
                               {"src": "fix-pics/a.svg", "alt": "a", "caption": "c"}]])
_sp_fix = os.path.join(_sp_plans, "fix.html")
with open(_sp_fix, "w", encoding="utf-8") as _f:
    _f.write(_pcp("art", add='<img src="fix-pics/a.svg" alt="x">'))
_sp_nosrc = os.path.join(_sp_plans, "nosrc.html")
with open(_sp_nosrc, "w", encoding="utf-8") as _f:
    _f.write(_pcp("art", add='<img src="gone-pics/a.svg" alt="x">'))
_sp_o1 = _sp_send(_sp_nosrc)
if "picture check did not run" in _sp_o1:
    report("SKIP", "sendcheck (#559): no usable browser: %s" % _sp_o1[:200])
else:
    _sp_o2 = _sp_send(_sp_fix)
    _sp_after = open(_sp_fix, encoding="utf-8").read()
    _mp_cases.append(("sendcheck (#559): a page with a -pics/ link is repaired in place with the picture embedded, allowed",
                      "deny" not in _sp_o2 and "data:image/svg" in _sp_after and "fix-pics/a.svg" not in _sp_after))
    if "re-check did not run" in _sp_o2:  # no browser: the repair still happened, only the note differs
        report("SKIP", "sendcheck (#559): the 'was repaired' note (no browser): %s" % _sp_o2[:200])
    else:
        _mp_cases.append(("sendcheck (#559): the repair is announced with a 'was repaired' note", "was repaired" in _sp_o2))
    _mp_cases.append(("sendcheck (#559): a picture whose file is missing is named with the reason, send allowed",
                      "gone-pics/a.svg (file not found)" in _sp_o1 and "could not be repaired" in _sp_o1 and "deny" not in _sp_o1))
    _mp_cases.append(("sendcheck (#559): a non-page file gets no note and no denial",
                      _sp_send(os.path.join(_sp_plans, "x.txt")) == ""))
    _sp_clean = _sp_send(_sp_fix)
    if "did not run" in _sp_clean:  # no browser at all: the hook says so on every send, even for a clean page
        report("SKIP", "sendcheck (#559): a clean page gets no note (no browser): %s" % _sp_clean[:200])
    else:
        _mp_cases.append(("sendcheck (#559): a clean page gets no note and no denial", _sp_clean == ""))
# ---- #557 static check: picture sources not built into the page are named, with no browser needed ----
_sb = __import__("make_page").static_broken_pictures
_mp_cases.append(("static picture check (#557): a PAGE data block holding a -pics/ src and no <img> at load is named",
                  _sb('<script>const PAGE = {"c":[{"src": "x-pics/a.png", "alt": "a"}]};</script>') == ["x-pics/a.png"]))
_mp_cases.append(("static picture check (#557): only data: pictures pass",
                  _sb('<img src="data:image/png;base64,AAAA"><script>var P={src:"data:image/svg+xml;utf8,x"}</script>') == []))
_mp_cases.append(("static picture check (#557): an in-page # source, a font stylesheet link and a font url do not count; an http image and css image url do",
                  _sb('<img src="#a"><link href="https://fonts.googleapis.com/css2?family=X" rel="stylesheet">'
                      '<style>@font-face{src:url(https://f.example/x.woff2)}b{background:url(/img/b.png)}</style>'
                      '<img src="https://e.com/p.jpg">') == ["https://e.com/p.jpg", "/img/b.png"]))
_sd_src = os.path.join(ROOT, "docs", "plans")  # read only; the copy lives in the OS temp dir, outside the repo
_sd_root = tempfile.mkdtemp(prefix="realqa-")
try:
    _sd_name = "2026-10-19-restructure-step-1-qa"
    _sd_tmp = os.path.join(_sd_root, "docs", "plans")
    os.makedirs(_sd_tmp)
    shutil.copyfile(os.path.join(_sd_src, _sd_name + ".html"), os.path.join(_sd_tmp, _sd_name + ".html"))
    shutil.copytree(os.path.join(_sd_src, _sd_name + "-pics"), os.path.join(_sd_tmp, _sd_name + "-pics"))
    _sd_page = os.path.join(_sd_tmp, _sd_name + ".html")
    _sd_before = open(_sd_page, encoding="utf-8", newline="").read()
    _sd_out = _sp_send(_sd_page)
    _sd_txt = open(_sd_page, encoding="utf-8", newline="").read()
    _sd_left = len(_sb(_sd_txt))
    _sd_mask = lambda t: re.sub(r"data:[a-z/+]+;base64,[A-Za-z0-9+/=]+", "DATA", t)
    _sd_masked_before = _sd_before
    for _u in _sb(_sd_before):  # the source text itself is what changed
        _sd_masked_before = re.sub(r"(?<![\w./-])" + re.escape(_u), "DATA", _sd_masked_before)  # same rule as the handler: a longer path naming it is text
    _sd_after = subprocess.run([sys.executable, os.path.join(HERE, "page_criteria.py"), _sd_page, "--visual"], capture_output=True, text=True, timeout=300).stdout
    _mp_cases.append(("static picture check (#557): REAL DATA, sendcheck repairs a copy of the finished QA page in place; no unbuilt picture is left, only the sources changed",
                      _sd_left == 0 and "broken picture when the page is opened alone" not in _sd_after
                      and _sd_mask(_sd_txt) == _sd_masked_before and len(_sd_txt.splitlines()) == len(_sd_before.splitlines())))
    if "re-check did not run" in _sd_out:
        report("SKIP", "static picture check (#557): the 'was repaired' note (no browser): %s" % _sd_out[:200])
    else:
        _mp_cases.append(("static picture check (#557): REAL DATA, the repair is announced with a 'was repaired' note", "was repaired" in _sd_out))
finally:
    shutil.rmtree(_sd_root, ignore_errors=True)
# ---- starters: one optional content skeleton per page type (#544) ----
_mp_cases.append(("starters (#544): make_page's type list equals page_criteria's", tuple(__import__("make_page").PAGE_TYPES) == tuple(_pc.TYPES)))
_sp = _mp_proj("starts", {"use": "defaults"})
_mp_git(_sp, "init", "-q", "-b", "main")
for _n in ("a.py",):
    with open(os.path.join(_sp, _n), "w", encoding="utf-8") as _f:
        _f.write("a\n")
_mp_git(_sp, "add", "-A")
_mp_git(_sp, "commit", "-q", "-m", "base")
_GAPS = {"review": ["Type review: the page has no finding; add at least one element marked data-basic=\"finding\"."]}  # item 4: the template has no finding element
for _typ in _pc.TYPES:
    _sf = os.path.join(_mp_tmp, "st-" + _typ + ".page.json")
    _rc1, _o1 = _mp("start", _typ, "--out", _sf)
    _rc1b, _ = _mp("start", _typ, "--out", _sf)  # a second start must not overwrite
    with open(_sf, encoding="utf-8") as _f:
        _raw = _f.read()
    _left = len(re.findall(r"<replace:", _raw))
    _raw = _raw.replace("<replace: base branch, such as origin/main>", "main").replace("<feature>", "demo")
    _raw = re.sub(r"<replace:[^>]*>", "x", _raw)
    with open(_sf, "w", encoding="utf-8") as _f:
        _f.write(_raw)
    if _typ == "qa":  # the QA gate (#596): the fixture carries a real current stamp for the starter's feature "x"
        _mp_stamp(_sp, os.path.join(_sp, "docs", "qa", "x"))
    _rc2, _o2 = _mp("build", _sf, "--project", _sp)
    _bh =os.path.join(_sp, "docs", "plans", "st-" + _typ + ".html")
    _bt = open(_bh, encoding="utf-8").read() if os.path.isfile(_bh) else ""
    _stripped = re.sub(r"<!-- house-rules make_page[^>]*-->", "", _bt)
    _msgs = _pc.check(_stripped)
    _mp_cases.append(("starters (#544): %s starts with placeholders, will not overwrite, builds, and carries the meta tag" % _typ,
                      _rc1 == 0 and "make_page.py build" in _o1 and _left > 0 and _rc1b == 2 and _rc2 == 0
                      and '<meta name="house-rules-page" content="%s">' % _typ in _bt))
    _mp_cases.append(("starters (#544): the built %s page %s" % (_typ, "meets the basics" if _typ not in _GAPS else "misses exactly the documented gap"),
                      _bt != "" and _msgs == _GAPS.get(_typ, [])))
_rc, _o = _mp("start", "poster")
_mp_cases.append(("starters (#544): start with an unknown type dies naming the five types",
                  _rc == 2 and "proposal, build-plan, qa, review, art" in _o))
_bp = _mp_content("badtype")
with open(_bp, encoding="utf-8") as _f:
    _bj = json.load(_f)
_bj["pageType"] = "poster"
with open(_bp, "w", encoding="utf-8") as _f:
    json.dump(_bj, _f)
_rc, _o = _mp("build", _bp, "--project", _sp)
_mp_cases.append(("starters (#544): build with an unknown pageType dies naming the five types",
                  _rc == 2 and "proposal, build-plan, qa, review, art" in _o))
import urllib.parse
_svg = lambda s: {"src": "data:image/svg+xml," + urllib.parse.quote(s), "alt": "a", "caption": "c"}
_cb = _mp_content("svgbad", [["chg", "Broken picture", "Looks new.", None, "Detail.", None, None, {"visual": True},
                              _svg("<svg xmlns='http://www.w3.org/2000/svg'><text>a < b</text></svg>")]])
_rc, _o = _mp("build", _cb, "--project", _d)
_cg = _mp_content("svggood", [["chg", "Good picture", "Looks new.", None, "Detail.", None, None, {"visual": True},
                               _svg("<svg xmlns='http://www.w3.org/2000/svg'><text>a &lt; b</text></svg>")]])
_rc2, _o2 = _mp("build", _cg, "--project", _d)
_mp_cases.append(("make_page (#612): an svg picture with a raw angle bracket makes the build refuse, naming the item; a well-formed one builds",
                  _rc == 2 and "Broken picture" in _o and _rc2 == 0))
# ---- review stamp (#594) ----
_rv_out = os.path.join(_sp, "docs", "plans", "rv.html")
_rc0, _ = _mp("build", _c1, "--project", _sp, "--out", _rv_out)
with open(_rv_out, encoding="utf-8", newline="") as _f:
    _rv0 = _f.read()
_rc1, _ = _mp("build", _c1, "--project", _sp, "--out", _rv_out, "--reviewed", "open-risks", "--rounds", "2")
with open(_rv_out, encoding="utf-8", newline="") as _f:
    _rv1 = _f.read()
_rv_m = re.search(r'^<meta name="house-rules-reviewed" content="([0-9a-f]{64});open-risks;2">\n', _rv1, re.M)
_mp_cases.append(("stamp (#594): build without --reviewed writes no stamp", _rc0 == 0 and "house-rules-reviewed" not in _rv0))
_mp_cases.append(("stamp (#594): build with --reviewed writes a stamp whose hash is the sha256 of the page without that line",
                  _rc1 == 0 and bool(_rv_m) and _rv_m.group(1) == __import__("hashlib").sha256(
                      _rv1.replace(_rv_m.group(0), "", 1).encode("utf-8")).hexdigest()
                  ))
_mp_cases.append(("stamp (#594): the written stamp checks as current, an edit makes it stale",
                  _pc.stamp_problem(_rv1) == "" and "stale" in _pc.stamp_problem(_rv1 + "<p>x</p>")))
_rc2, _o2 = _mp("build", _c1, "--project", _sp, "--out", _rv_out, "--reviewed", "clean", "--rounds", "3")
_mp_cases.append(("stamp (#594): --rounds 3 is refused", _rc2 == 2 and "cap is 2" in _o2))
# ---- build plan needs an Acceptance tests item (#595) ----
_ap = _mp_proj("acc-plan", {"use": "defaults"})
_apc = _mp_content("acc-plan1")
_apj = json.load(open(_apc, encoding="utf-8"))
_apj["pageType"] = "build-plan"
json.dump(_apj, open(_apc, "w", encoding="utf-8"))
_rc, _o = _mp("build", _apc, "--project", _ap)
_mp_cases.append(("acceptance (#595): a build plan with no Acceptance item is refused, naming the rule",
                  _rc == 2 and "needs an Acceptance tests item: one test per design item" in _o))
_apj["changes"].append(["chg", "Acceptance tests", "One per item.", None, "", None, None])
json.dump(_apj, open(_apc, "w", encoding="utf-8"))
_rc, _o = _mp("build", _apc, "--project", _ap)
_mp_cases.append(("acceptance (#595): an Acceptance item with empty detail is refused", _rc == 2))
_apj["changes"][-1][4] = "Run each design item and see it work."
json.dump(_apj, open(_apc, "w", encoding="utf-8"))
_rc, _o = _mp("build", _apc, "--project", _ap)
_mp_cases.append(("acceptance (#595): a build plan with a filled Acceptance item builds", _rc == 0))
for _t, _ok in _mp_cases:
    report("PASS" if _ok else "FAIL", _t)
shutil.rmtree(_mp_tmp, True)


finish()
