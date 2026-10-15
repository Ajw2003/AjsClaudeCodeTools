#!/usr/bin/env python3
"""make_page.py - builds a handover page from content JSON, the project's style file and the template.

    make_page.py build <content.json> [--out docs/plans/<name>.html] [--project <root>]
    make_page.py style --quick
    make_page.py style --draft [--from <tokens.json>] [--project <root>]

Content JSON has the same keys as the template's PAGE block (title, eyebrow, approval,
short, changes, choices, wrapup). A Changes item may carry `{"visual": true}` as a trailing object
element (any position after the detail); it marks a visual change. The template ignores it. In a
project whose style file says `"pictures": "required"`, such an item must also carry a picture
(`{src, alt, caption}`) or a compare (`{before, after, caption}`) object, or the build refuses.

The project style file is `docs/page-style.json` (see docs/plans/page-style/plunderspell.page-style.json).
`{"use": "defaults"}` means the template's own look. One palette is applied in every theme the file
allows; when `themes` has one entry the page is forced to that theme.

Exit codes: 0 built, 2 refused or bad input, 3 no style file (two options are printed).

STDLIB ONLY, Python 3.8+. Never installs anything.
"""

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(HERE, ".."))
TEMPLATE = os.path.join(PLUGIN, "templates", "handover-page.html")
STYLE_REL = os.path.join("docs", "page-style.json")
DRAFT_REL = os.path.join("docs", "page-style.draft.json")
CMD_DRAFT = "make_page.py style --draft"
CMD_QUICK = "make_page.py style --quick"
HEX = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")


def die(msg, code=2):
    print("make_page: " + msg, file=sys.stderr)
    sys.exit(code)


def plugin_version():
    try:
        with open(os.path.join(PLUGIN, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
            return json.load(f)["version"]
    except (OSError, ValueError, KeyError) as e:
        die("cannot read the plugin version from .claude-plugin/plugin.json: %s" % e)


def load_json(path, what):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except OSError as e:
        die("cannot read %s %s: %s" % (what, path, e))
    except ValueError as e:
        die("%s %s is not valid JSON: %s" % (what, path, e))


def norm(c):
    c = c.strip().lower()
    if len(c) == 4:
        c = "#" + "".join(ch * 2 for ch in c[1:])
    return c


def mix(fg, bg, t):
    a, b = norm(fg), norm(bg)
    out = "#"
    for i in (1, 3, 5):
        x, y = int(a[i:i + 2], 16), int(b[i:i + 2], 16)
        out += "%02X" % round(x * t + y * (1 - t))
    return out


def walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)


def strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from strings(v)


def has_look(style):
    """True when the style file says more than {"use": "defaults"}."""
    return style.get("use") != "defaults" and any(k not in ("use", "name", "drafted_from") for k in style)


def role_color(style, role):
    r = (style.get("roles") or {}).get(role)
    return r.get("color") if isinstance(r, dict) else r


def check_reserved(page, style):
    reserved = {}
    for r in style.get("reserved") or []:
        c = r.get("color") if isinstance(r, dict) else r
        if c:
            reserved[norm(c)] = r.get("rule", "reserved") if isinstance(r, dict) else "reserved"
    for role in ("you_act", "accent", "blocking", "done"):
        c = role_color(style, role)
        if c and norm(c) in reserved:
            die("style file role '%s' uses the reserved colour %s (%s)" % (role, c, reserved[norm(c)]))
    for key, c in (style.get("colors") or {}).items():
        if isinstance(c, str) and norm(c) in reserved:
            die("style file colour '%s' uses the reserved colour %s (%s)" % (key, c, reserved[norm(c)]))
    if reserved:
        for s in strings(page):
            for m in HEX.findall(s):
                if norm(m) in reserved:
                    die("PAGE colour %s is reserved (%s), found in: %s" % (m, reserved[norm(m)], s[:60]))


def is_pic(x):
    return isinstance(x, dict) and (x.get("src") or x.get("before"))


def check_pictures(page, style):
    if style.get("pictures") != "required":
        return
    for item in page.get("changes") or []:
        if not isinstance(item, list):
            continue
        visual = any(isinstance(x, dict) and x.get("visual") for x in item)
        if visual and not any(is_pic(x) for x in item):
            name = item[1] if len(item) > 1 else "?"
            die("Changes item '%s' is marked visual but has no picture or compare, and this project's "
                "style file says pictures are required" % name)


def copy_pictures(page, content_dir, project, out_html):
    base = os.path.splitext(os.path.basename(out_html))[0]
    pics_dir = os.path.join(os.path.dirname(out_html), base + "-pics")
    used = {}
    for d in walk(page):
        src = d.get("src")
        if not isinstance(src, str) or re.match(r"^(data:|https?:|//|#)", src):
            continue
        found = None
        for root in (project, content_dir):
            p = src if os.path.isabs(src) else os.path.join(root, src)
            if os.path.isfile(p):
                found = p
                break
        if not found:
            die("picture not found: %s (looked under %s and %s)" % (src, project, content_dir))
        key = os.path.abspath(found)
        if key not in used:
            name = os.path.basename(found)
            stem, ext = os.path.splitext(name)
            n = 1
            while name in used.values():
                n += 1
                name = "%s-%d%s" % (stem, n, ext)
            os.makedirs(pics_dir, exist_ok=True)
            shutil.copyfile(found, os.path.join(pics_dir, name))
            used[key] = name
        d["src"] = base + "-pics/" + used[key]
    return len(used)


def style_css(style):
    colors = style.get("colors") or {}
    bg = colors.get("background")
    v = []
    for var, key in (("bg", "background"), ("card", "surface"), ("fg", "text"),
                     ("muted", "text_muted"), ("line", "line")):
        if colors.get(key):
            v.append("--%s:%s" % (var, colors[key]))
    for var, role in (("you", "you_act"), ("accent", "accent"), ("gap", "blocking"), ("ok", "done")):
        c = role_color(style, role)
        if c:
            v.append("--%s:%s" % (var, c))
            if bg:
                v.append("--%s-soft:%s" % (var, mix(c, bg, 0.15)))
    fonts = style.get("fonts") or {}
    if fonts.get("display"):
        v.append('--display:"%s",Georgia,serif' % fonts["display"])
    if fonts.get("body"):
        v.append('--body:"%s",Georgia,serif' % fonts["body"])
    if fonts.get("label"):
        v.append('--label:"%s",ui-monospace,monospace' % fonts["label"])
    themes = style.get("themes") or []
    scheme = ""
    if len(themes) == 1:
        scheme = ";color-scheme:%s" % themes[0]
    decl = ";".join(v) + scheme
    css = ["/* house-rules make_page: project style from docs/page-style.json */"]
    if len(themes) == 1:
        css.append(":root,:root[data-theme],:root:not([data-theme=\"light\"]){%s}" % decl)
        css.append("@media (prefers-color-scheme: light){:root{%s}}" % decl)
        css.append("@media (prefers-color-scheme: dark){:root{%s}}" % decl)
    else:
        css.append(":root,:root[data-theme]{%s}" % decl)
    if (style.get("shape") or {}).get("corner_radius") == 0:
        css.append("*{border-radius:0!important}")
    lab = style.get("labels") or {}
    sel = (".eyebrow,.tag,.crh,.more,.stepper button,.flow small,.files h4,.rec,.key,.why summary,"
           ".status,#cc-count,.g,.st .nm small,.row>span:first-child")
    rules = []
    if lab.get("family") and fonts.get(lab["family"]):
        rules.append("font-family:var(--%s)!important" % lab["family"])
    if lab.get("case") == "upper":
        rules.append("text-transform:uppercase")
    if lab.get("letter_spacing"):
        rules.append("letter-spacing:%s" % lab["letter_spacing"])
    if rules:
        css.append("%s{%s;font-size:.68rem}" % (sel, ";".join(rules)))
    ic = style.get("icons") or {}
    if ic.get("frame") == "sigil":
        ring = ic.get("ring") or colors.get("line") or "currentColor"
        css.append(".g span.c,.st .c,.wu .c{border-radius:50%%!important;background:transparent!important;"
                   "border:1.5px solid %s;position:relative}" % ring)
        css.append(".g span.c::after,.st .c::after,.wu .c::after{content:\"\";position:absolute;inset:4px;"
                   "border-radius:50%!important;border:1px dashed currentColor;opacity:.9}")
        if ic.get("glyph_stroke"):
            css.append(".g span.c .ico,.wu .c .ico{stroke-width:%s}" % ic["glyph_stroke"])
        css.append(".g.you span.c,.st.you .c{color:var(--you)}.g.done span.c{color:var(--ok)}"
                   ".g:not(.you):not(.done) span.c{color:var(--accent)}")
    out = "<style>\n" + "\n".join(css) + "\n</style>\n"
    families = [fonts[k] for k in ("display", "body", "label") if fonts.get(k)]
    # shortcut: asks Google Fonts for 400 and 700, which a single-weight family lacks; set fonts.load then
    load = fonts.get("load") or (families and "https://fonts.googleapis.com/css2?%s&display=swap" % "&".join(
        "family=%s:wght@400;700" % f.replace(" ", "+") for f in dict.fromkeys(families)))
    if load:
        out = '<link rel="stylesheet" href="%s">\n' % load + out
    return out


def run_git(project, *a):
    try:
        r = subprocess.run(["git", "-C", project] + list(a), capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        die("git did not run in %s: %s" % (project, e))
    if r.returncode:
        die("git %s failed in %s: %s" % (" ".join(a), project, (r.stderr or r.stdout).strip()))
    return r.stdout


def apply_qa(page, project):
    """QA mode: add the git-counted Files changed item and the Still unverified item."""
    qa = page["qa"]
    if not isinstance(qa, dict):
        die("content 'qa' must be an object with feature, base, unverified and files")
    for k in ("feature", "base"):
        if not qa.get(k):
            die("QA mode needs qa.%s in the content file; add it" % k)
    unv = qa.get("unverified")
    if not isinstance(unv, list) or not unv:
        die("QA mode needs qa.unverified, a non-empty list of what is not yet proven; a QA page that "
            "claims everything is proven is refused, so list what you did not check")
    plan = qa.get("files") or {}
    base = qa["base"]
    rows, seen, tot_a, tot_r = [], set(), 0, 0
    for line in run_git(project, "diff", "--numstat", base + "...HEAD").splitlines():
        a, r, f = line.split("\t", 2)
        a, r = (int(a), int(r)) if a != "-" else (0, 0)
        tot_a, tot_r = tot_a + a, tot_r + r
        seen.add(f)
        est = plan.get(f)
        part = ["Plan estimate: %s" % est[2], est[0], est[1]] if est else ["Not in the plan", 0, 0]
        rows.append([f, a, r, [part]])
    for f, est in plan.items():
        if f not in seen:
            rows.append([f, 0, 0, [["Planned but not changed: %s" % est[2], est[0], est[1]]]])
    page.setdefault("changes", []).append(
        ["chg", "Files changed, counted from git against %s" % base,
         "%d files, +%d −%d" % (len(seen), tot_a, tot_r),
         None, "The added and removed counts come from git (git diff --numstat %s...HEAD); the estimates "
         "beside them come from the plan." % base, None, rows])
    page["changes"].append(["keep", "Still unverified", "%d things not yet proven" % len(unv), None,
                            " ".join(u if u.rstrip()[-1:] in ".!?" else u.rstrip() + "." for u in unv), None, None])
    page.setdefault("choices", [])  # a QA page usually has none, and the template maps over the list
    page["approval"] = "QA passed: %s" % qa["feature"]
    page.pop("replyPrefix", None)
    page.pop("reply", None)


def load_gate_patterns():
    """The design-loop gate's own regexes, loaded from hook.py beside this script, not copied.
    hook.py only runs main() under __main__, so importing it by path has no side effects
    (verify.py loads it the same way)."""
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hook.py")
    spec = importlib.util.spec_from_file_location("hook_for_make_page", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._LOOP_DESIGN_RE, mod._LOOP_PLAN_RE, mod._LOOP_QA_RE


def is_qa_approval(page):
    return "qa" in page or str(page.get("approval", "")).startswith("QA passed")


def check_approval(page):
    """The copy box holds the approval phrase (plus picks); it must be text the gate accepts."""
    appr = page.get("approval")
    if not isinstance(appr, str) or not appr.strip():
        die("content needs an 'approval' field: the exact phrase the design-loop gate accepts, such as "
            "\"Build plan approved: <feature>\" or \"Design approved: <feature>\" (a QA page gets \"QA passed: <feature>\")")
    if appr != appr.strip() or "\n" in appr:
        die("approval must be one line with no spaces at either end")
    design, plan, qa = load_gate_patterns()
    qa_page = is_qa_approval(page)
    pats = [qa] if qa_page else [design, plan]
    want = "QA passed: <feature>" if qa_page else "Design approved: <feature> or Build plan approved: <feature>"
    for text in (appr, appr + " 1A"):
        if not any(p.search(text) for p in pats):
            die("approval %r would not open the design-loop gate (checked %r); write it as %s" % (appr, text, want))


def apply_approval_todo(page):
    """Make the wrap-up's last to-do line say the phrase the copy box holds."""
    import html
    appr = html.escape(page["approval"], quote=False)
    if is_qa_approval(page):
        feature = appr.split(":", 1)[1].strip()
        line = ('Tap <b>Copy my reply</b> and send it: "%s", or send "QA failed: %s" with what to change.'
                % (appr, feature))
    else:
        line = 'Tap <b>Copy my reply</b> and send it: "%s", or say what to change.' % appr
    wrap = page.setdefault("wrapup", {})
    todo = wrap.get("todo")
    if not isinstance(todo, list) or not todo:
        wrap["todo"] = [line]
    else:
        todo[-1] = line


def record_qa_page(project, out):
    common = os.path.abspath(os.path.join(project, run_git(project, "rev-parse", "--git-common-dir").strip()))
    stage = os.path.join(os.path.dirname(common), ".claude", "house-rules-loop.json")
    if not os.path.isfile(stage):
        print("make_page: QA page not recorded because no feature is in progress (no %s)" % stage)
        return
    try:
        with open(stage, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("not a JSON object")
    except (OSError, ValueError) as e:
        print("make_page: QA page not recorded: %s is unreadable (%s); left untouched" % (stage, e))
        return
    data["qa_page"] = os.path.relpath(out, project).replace(os.sep, "/")
    with open(stage, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print("make_page: recorded qa_page %s in %s" % (data["qa_page"], stage))


def build(args):
    project = os.path.abspath(args.project or os.getcwd())
    style_path = os.path.join(project, STYLE_REL)
    if not os.path.isfile(style_path):
        print("make_page: this project has no page style file (%s)." % style_path)
        print("Pick one, then run the build again:")
        print("  1. %s   (create one from the project's own style, for aj to approve)" % CMD_DRAFT)
        print("  2. %s   (write {\"use\": \"defaults\"} so you are never asked again)" % CMD_QUICK)
        sys.exit(3)
    style = load_json(style_path, "style file")
    page = load_json(args.content, "content")
    if not isinstance(page, dict):
        die("content %s must be a JSON object" % args.content)
    if "qa" in page:
        apply_qa(page, project)
    check_approval(page)
    apply_approval_todo(page)
    check_reserved(page, style)
    check_pictures(page, style)
    stem = os.path.basename(args.content)
    for suffix in (".page.json", ".json"):
        if stem.endswith(suffix):
            stem = stem[:-len(suffix)]
            break
    out = os.path.abspath(args.out or os.path.join(project, "docs", "plans", stem + ".html"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    npics = copy_pictures(page, os.path.dirname(os.path.abspath(args.content)), project, out)
    with open(TEMPLATE, encoding="utf-8") as f:
        html = f.read()
    m = re.search(r"^const PAGE = \{.*?^\};\n", html, re.S | re.M)
    if not m:
        die("the template has no 'const PAGE = {...};' block: %s" % TEMPLATE)
    js = json.dumps(page, ensure_ascii=False, indent=2).replace("</", "<\\/")
    html = html[:m.start()] + "const PAGE = " + js + ";\n" + html[m.end():]
    title = str(page.get("title", ""))
    esc = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html = re.sub(r"<title>.*?</title>", lambda _: "<title>%s</title>" % esc, html, count=1, flags=re.S)
    if has_look(style):
        block = style_css(style)
        if "fonts.googleapis.com" in block:  # the project's fonts replace the template's default ones
            html = re.sub(r'<link rel="stylesheet" href="https://fonts\.googleapis\.com/[^"]*">\n', "", html, count=1)
        i = html.index("<svg width=\"0\"") if "<svg width=\"0\"" in html else html.index("<script>")
        html = html[:i] + block + html[i:]
    html = "<!doctype html>\n<!-- house-rules make_page %s -->\n" % plugin_version() + html
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    print("make_page: wrote %s (%d picture(s) copied)" % (out, npics))
    visual_check(out, style)
    if "qa" in page:
        record_qa_page(project, out)


# ---- step 2: visual check -------------------------------------------------------------------

NODE_JS = r"""
const { chromium } = require('playwright');
(async () => {
  const [file, themes] = [process.argv[2], JSON.parse(process.argv[3])];
  const b = await chromium.launch();
  let bad = 0;
  for (const t of themes) {
    const p = await b.newPage({ viewport: { width: 375, height: 800 }, colorScheme: t });
    const errs = []; p.on('pageerror', e => errs.push(String(e)));
    await p.goto('file://' + file); await p.waitForTimeout(300);
    const w = await p.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
    console.log(`visual check ${t}: page errors ${errs.length}, overflow ${w[0] > w[1] ? 'YES ' + w[0] + '>' + w[1] : 'none'}`);
    errs.forEach(e => console.log('  error: ' + e));
    if (errs.length || w[0] > w[1]) bad = 1;
  }
  await b.close(); process.exit(bad);
})().catch(e => { console.log('LAUNCHFAIL ' + e.message.split('\n')[0]); process.exit(9); });
"""

PY_CHECK = r"""
import sys, json
from playwright.sync_api import sync_playwright
file, themes = sys.argv[1], json.loads(sys.argv[2])
bad = 0
with sync_playwright() as pw:
    try:
        b = pw.chromium.launch()
    except Exception as e:
        print("LAUNCHFAIL " + str(e).split("\n")[0]); sys.exit(9)
    for t in themes:
        p = b.new_page(viewport={"width": 375, "height": 800}, color_scheme=t)
        errs = []
        p.on("pageerror", lambda e: errs.append(str(e)))
        p.goto("file://" + file); p.wait_for_timeout(300)
        w = p.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
        print("visual check %s: page errors %d, overflow %s" % (t, len(errs), ("YES %d>%d" % (w[0], w[1])) if w[0] > w[1] else "none"))
        for e in errs: print("  error: " + e)
        if errs or w[0] > w[1]: bad = 1
    b.close()
sys.exit(bad)
"""


def visual_check(out, style):
    themes = style.get("themes") or ["light", "dark"]
    arg = json.dumps(themes)
    reasons = []
    runs = []
    try:
        import importlib.util
        if importlib.util.find_spec("playwright"):
            runs.append(("python playwright", [sys.executable, "-c", PY_CHECK, out, arg]))
        else:
            reasons.append("python playwright is not installed")
    except (ImportError, ValueError) as e:
        reasons.append("python playwright check failed: %s" % e)
    node = shutil.which("node")
    if not node:
        reasons.append("node is not installed")
    else:
        try:
            r = subprocess.run([node, "-e", "require.resolve('playwright')"], capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as e:
            r = None
            reasons.append("node playwright probe failed: %s" % e)
        if r is not None:
            if r.returncode == 0:
                fd, js = tempfile.mkstemp(suffix=".js")
                with os.fdopen(fd, "w") as f:
                    f.write(NODE_JS)
                runs.append(("node playwright", [node, js, out, arg]))
            else:
                reasons.append("node has no playwright module")
    for label, cmd in runs:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        except (OSError, subprocess.SubprocessError) as e:
            reasons.append("%s did not run: %s" % (label, e))
            continue
        if "LAUNCHFAIL" in r.stdout:
            reasons.append("%s found no usable Chromium (%s)" % (label, r.stdout.split("LAUNCHFAIL", 1)[1].strip()))
            continue
        print(r.stdout.rstrip())
        if r.returncode:
            print("make_page: visual check found problems (see above); the page was still written")
        return
    print("visual check did not run: " + "; ".join(reasons))


# ---- style subcommand -----------------------------------------------------------------------

def style_cmd(args):
    project = os.path.abspath(args.project or os.getcwd())
    if args.quick:
        p = os.path.join(project, STYLE_REL)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write('{"use": "defaults"}\n')
        print("make_page: wrote %s" % p)
        return
    if not args.draft:
        die("style needs --quick or --draft")
    src = args.from_tokens
    if not src:
        found = sorted(glob.glob(os.path.join(project, "**", "design-system", "**", "tokens.json"), recursive=True))
        if not found:
            die("no design-system tokens.json found under %s; pass --from <tokens.json>" % project)
        src = found[0]
    tokens = load_json(src, "tokens file")
    draft, guesses = draft_style(tokens, project, src)
    p = os.path.join(project, DRAFT_REL)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(draft, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(json.dumps(draft, indent=2, ensure_ascii=False))
    print("\nmake_page: wrote draft to %s (docs/page-style.json is untouched)." % p)
    print("aj: confirm this role mapping, it is a best guess:")
    for g in guesses:
        print("  - " + g)
    print("To approve, copy the draft to %s after any edits." % os.path.join(project, STYLE_REL))


def draft_style(tokens, project, src):
    dark, usage = {}, {}
    for t in (tokens.get("color") or {}).get("tokens") or []:
        v = t.get("value")
        c = v.get("dark") if isinstance(v, dict) else v
        if isinstance(c, str) and t.get("name"):
            dark[t["name"]] = c
            usage[t["name"]] = str(t.get("usage") or "").lower()

    # Design systems often name colours for what they are (PlunderSpell's "bone-black", "verdigris")
    # and say what they're for only in the usage note, so a word is matched against both.
    # A token's own name beats a mention in another token's usage note, and a shade of a colour
    # already taken ("verdigris-lo" beside "verdigris") never fills a second role.
    def pick(*words, skip=()):
        def free(n):
            return n not in skip and not any(n.startswith(s + "-") for s in skip)
        for w in words:
            for n, c in dark.items():
                if free(n) and w in n.lower():
                    return n, c
            for n, c in dark.items():
                if free(n) and w in usage[n]:
                    return n, c
        return None, None

    guesses, colors, roles = [], {}, {}
    for key, words in (("background", ("background", "bg", "ground", "canvas")),
                       ("surface", ("surface", "card", "panel")),
                       ("text", ("text", "foreground", "fg", "ink")),
                       ("text_muted", ("muted", "dim", "secondary")),
                       ("line", ("line", "border", "divider", "hairline"))):
        n, c = pick(*words)
        if c:
            colors[key] = c
            guesses.append("%s <- token '%s' (%s)" % (key, n, c))
        else:
            guesses.append("%s: no token matched, left out" % key)
    # A colour the project keeps for one meaning is reserved, and never offered as a page role.
    reserved = [{"color": dark[n], "token": n, "rule": "its usage note keeps it for one meaning; aj to confirm"}
                for n in dark if re.search(r"nothing but|no other (ui )?element may|never used", usage[n])]
    used = {r["token"] for r in reserved}
    for r in reserved:
        guesses.append("reserved <- token '%s' (%s)" % (r["token"], r["color"]))
    for role, words in (("you_act", ("interact", "action", "success", "primary")),
                        ("blocking", ("danger", "alarm", "error", "warn")),
                        ("accent", ("accent", "brand", "voice", "secondary")),
                        ("done", ("done", "muted", "dim"))):
        # done may share a colour with muted text; the other roles each need their own.
        n, c = pick(*words, skip=used if role != "done" else {r["token"] for r in reserved})
        if c:
            used.add(n)
            roles[role] = {"color": c, "why": "drafted from token '%s'; aj to confirm" % n}
            guesses.append("role %s <- token '%s' (%s)" % (role, n, c))
        else:
            guesses.append("role %s: no token matched, left out" % role)
    fam = (tokens.get("type") or {}).get("families") or {}
    fonts = {}
    items = fam.items() if isinstance(fam, dict) else [((f.get("name") or f.get("role")), f) for f in fam if isinstance(f, dict)]
    for k, v in items:
        name = v if isinstance(v, str) else (v.get("family") or v.get("value") or v.get("name"))
        if isinstance(name, str) and k:
            name = name.split(",")[0].strip().strip("'\"")
            kl = str(k).lower()
            slot = "display" if ("display" in kl or "head" in kl) else "label" if ("mono" in kl or "label" in kl) \
                else "body" if "body" in kl else None
            if slot and slot not in fonts:
                fonts[slot] = name
                guesses.append("font %s <- '%s' (%s)" % (slot, name, k))
    shape = {}
    radii = (tokens.get("radius") or {}).get("tokens") or []
    vals = [t.get("value") for t in radii if isinstance(t, dict)]
    if vals and all(str(v).strip() in ("0", "0px", "none") for v in vals):
        shape["corner_radius"] = 0
        guesses.append("shape: every radius token is 0, so square corners")
    draft = {"name": os.path.basename(project),
             "drafted_from": os.path.relpath(src, project) if src.startswith(project) else src,
             "themes": ["dark"], "colors": colors, "roles": roles,
             "reserved": [{"color": r["color"], "rule": r["rule"]} for r in reserved], "fonts": fonts,
             "shape": shape, "pictures": "optional"}
    guesses.append("themes: dark (the tokens file read here is the dark column); pictures: optional")
    return draft, guesses


def main(argv=None):
    ap = argparse.ArgumentParser(prog="make_page.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("content")
    b.add_argument("--out")
    b.add_argument("--project")
    s = sub.add_parser("style")
    s.add_argument("--quick", action="store_true")
    s.add_argument("--draft", action="store_true")
    s.add_argument("--from", dest="from_tokens")
    s.add_argument("--project")
    args = ap.parse_args(argv)
    if args.cmd == "build":
        build(args)
    else:
        style_cmd(args)


if __name__ == "__main__":
    main()
