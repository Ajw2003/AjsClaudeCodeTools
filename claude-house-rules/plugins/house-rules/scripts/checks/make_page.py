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


def _mp_content(name, extra_changes=None, text="Plain.", approval="Build plan approved: demo thing", choices=None):
    page = {"title": "T " + name, "eyebrow": "e", "approval": approval,
            "short": {"lead": text, "hint": "h", "key": [["We", ""]], "items": [["bulb", "Idea", "The idea", "", "c", "r"]]},
            "changes": [["new", "A thing", "One line.", None, "Detail.", None, None]] + (extra_changes or []),
            "wrapup": {"summary": "s", "changing": "c", "blocking": "b", "next": "n", "todo": ["t"]}}
    if approval is None:
        del page["approval"]
    if choices is not None:
        page["choices"] = choices
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
                                {"src": "data:image/png;base64,AAAA", "alt": "a", "caption": "c"}]])
_rc, _o = _mp("build", _cv2, "--project", _d)
_mp_cases.append(("make_page: the same visual item with a picture builds", _rc == 0))

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
_rc, _o = _mp("build", _mp_qa_content("qa2", dict(_qa, unverified=[])), "--project", _d)
_mp_cases.append(("make_page: QA mode with an empty unverified list is refused with exit 2",
                  _rc == 2 and "unverified" in _o))
os.makedirs(os.path.dirname(_stage))
with open(_stage, "w", encoding="utf-8") as _f:
    json.dump({"feature": "demo", "stage": "Build"}, _f)
_rc, _o = _mp("build", _mp_qa_content("qa3", _qa), "--project", _d)
with open(_stage, encoding="utf-8") as _f:
    _sd = json.load(_f)
_mp_cases.append(("make_page: QA mode writes qa_page into an existing stage file and keeps its other keys",
                  _rc == 0 and _sd == {"feature": "demo", "stage": "Build", "qa_page": "docs/plans/qa3.html"}))
_rc, _o = _mp("build", _mp_qa_content("qa4", dict(_qa, base="HEAD")), "--project", _d)
_mp_cases.append(("make_page (#415): a QA page counted against a base that already holds the feature (0 changed files) is refused, naming the fix",
                  _rc == 2 and "counted 0 changed files" in _o))

# The Ophan fixture (#412): the real Ophan QA page's content, with no evidence list, over a diff that
# changes an animation, a model, gameplay code and a screenshot. It must be refused.
import struct as _oph_struct
import zlib as _oph_zlib


def _oph_png():
    def chunk(t, b):
        c = t + b
        return _oph_struct.pack(">I", len(b)) + c + _oph_struct.pack(">I", _oph_zlib.crc32(c) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", _oph_struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", _oph_zlib.compress(b"\x00\xff\x00\x00")) + chunk(b"IEND", b""))


_oph_d = _mp_proj("ophan", {"use": "defaults"})
_mp_git(_oph_d, "init", "-q", "-b", "main")
with open(os.path.join(_oph_d, "placeholder.txt"), "w", encoding="utf-8") as _f:
    _f.write("base\n")
_mp_git(_oph_d, "add", "-A")
_mp_git(_oph_d, "commit", "-q", "-m", "base")
for _n, _t in (("Assets/Models/ArtBible/Enemies/Fear/TheOphanOfHours/TheOphanOfHours.controller", b"%YAML 1.1\n"),
               ("Assets/_Project/Scripts/Runtime/Raid/Ophan/OphanHunt.cs", b"class OphanHunt { }\n"),
               ("Assets/Models/ArtBible/Animations/TheOphanOfHours_Generic.fbx", b"fbx\n"),
               ("docs/generated/ophan-418/solo-beam.png", _oph_png())):
    _p = os.path.join(_oph_d, *_n.split("/"))
    os.makedirs(os.path.dirname(_p), exist_ok=True)
    with open(_p, "wb") as _f:
        _f.write(_t)
_mp_git(_oph_d, "add", "-A")
_mp_git(_oph_d, "commit", "-q", "-m", "ophan")
_oph_qa = {"feature": "the Ophan in the sky", "base": "main",
           "unverified": ["Nobody has played it by hand yet."], "files": {}}
_oph_c = _mp_qa_content("ophan", _oph_qa)
with open(_oph_c, encoding="utf-8") as _f:
    _oph_pg = json.load(_f)
_oph_pg["short"]["items"] = [
    ["check", "The beam's look", "It no longer floods your own view", "done",
     "On the target's own screen the beam fades out over its last 25 m. Screenshot: docs/generated/ophan-418/staging-beam-host.png.",
     "Nothing from you."],
    ["check", "The wings spread", "The wings open fully", "done",
     "Review sheet: docs/art/anim/fear/ophan_spread.png.", "Nothing from you."],
    ["check", "The take", "The lift looks right", "done",
     "Screenshot: staging-lift-host.png.", "Nothing from you."]]
with open(_oph_c, "w", encoding="utf-8") as _f:
    json.dump(_oph_pg, _f)
_rc, _o = _mp("build", _oph_c, "--project", _oph_d)
_mp_cases.append(("make_page (#412): the Ophan QA page's content, with no evidence for its animation, model and gameplay changes, is refused",
                  _rc == 2))

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
_mp_cases.append(("make_page (#309): an approval that isn't a design-loop phrase builds, with a note that it moves no stage",
                  _rc == 0 and "moves no stage" in _o))
_ch = [["c1", "Which?", [["A", "Option A", 1, "one"], ["B", "Option B", 0, "two"]], ""]]
_ph = "Build plan approved: guards <audit> & more"
_rc1, _ = _mp("build", _mp_content("withch", approval=_ph, choices=_ch), "--project", _d)
_rc2, _ = _mp("build", _mp_content("noch", approval=_ph, choices=[]), "--project", _d)
_pw = {n: _mp_page_of(os.path.join(_d, "docs", "plans", n + ".html")) for n in ("withch", "noch")} if _rc1 == _rc2 == 0 else {}
_mp_cases.append(("make_page: the last to-do line carries the approval phrase, HTML-escaped",
                  bool(_pw) and all(pg["wrapup"]["todo"][-1] == 'Tap <b>Copy my reply</b> and send it: "Build plan approved: guards &lt;audit&gt; &amp; more", or say what to change.'
                                    for pg in _pw.values())))
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
for _t, _ok in _mp_cases:
    report("PASS" if _ok else "FAIL", _t)
shutil.rmtree(_mp_tmp, True)


finish()
