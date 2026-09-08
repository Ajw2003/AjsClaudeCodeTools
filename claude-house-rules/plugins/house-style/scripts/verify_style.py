#!/usr/bin/env python3
"""verify_style.py — proves the house-style themes and hooks do what they claim.

Run it yourself, any time, on any machine:

    python claude-house-rules/plugins/house-style/scripts/verify_style.py

It validates every shipped theme, feeds real hook payloads to style.py's handlers, and asserts
on the JSON decision returned. Exit code 0 = all passed, 1 = something failed. Every case
tested is printed alongside its result.

STDLIB ONLY, and NO NETWORK. Every check here runs offline. A suite that needed the internet
would fail on exactly the machines the fallback exists for.

The check count is never hardcoded — it is computed at runtime, so it cannot drift out from
under an added case.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
STYLE = os.path.join(HERE, "style.py")
RUN = os.path.join(HERE, "run.sh")
PLUGIN = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
THEMES = os.path.join(PLUGIN, "themes")
HOOKS_JSON = os.path.join(PLUGIN, "hooks", "hooks.json")
SCHEMA = os.path.join(THEMES, "schema.md")
TOKENS = os.path.join(PLUGIN, "templates", "tokens.css")
GALLERY = os.path.join(PLUGIN, "templates", "gallery.html")
COMMAND = os.path.join(PLUGIN, "commands", "house-style.md")
MARKETPLACE = os.path.join(ROOT, ".claude-plugin", "marketplace.json")
CLAUDEMD = os.path.join(ROOT, "CLAUDE.md")
STEPCARD = os.path.join(ROOT, "claude-house-rules", "plugins", "house-rules",
                        "templates", "step-card.html")

SH = (
    r"C:\Program Files\Git\bin\sh.exe"
    if os.path.exists(r"C:\Program Files\Git\bin\sh.exe")
    else (shutil.which("sh") or "sh")
)

sys.path.insert(0, HERE)
import style  # noqa: E402

STEP = 0
FAILURES = 0


def report(result, title):
    global STEP, FAILURES
    STEP += 1
    if result == "FAIL":
        FAILURES += 1
    print(f"{STEP:2d}. {result}  {title}")


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def run_hook(event, payload="", env=None):
    e = dict(os.environ) if env is None else env
    proc = subprocess.run(
        [sys.executable, STYLE, event],
        input=payload.encode("utf-8"),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=e,
    )
    return (proc.returncode,
            proc.stdout.decode("utf-8", "replace"),
            proc.stderr.decode("utf-8", "replace"))


def run_cli(args, env=None, cwd=None):
    e = dict(os.environ) if env is None else env
    proc = subprocess.run(
        [sys.executable, STYLE] + args,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=e, cwd=cwd,
    )
    return (proc.returncode,
            proc.stdout.decode("utf-8", "replace"),
            proc.stderr.decode("utf-8", "replace"))


def run_shell(args, payload="", env=None):
    e = dict(os.environ) if env is None else env
    proc = subprocess.run(
        [SH] + args, input=payload.encode("utf-8"),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=e,
    )
    return (proc.returncode,
            proc.stdout.decode("utf-8", "replace"),
            proc.stderr.decode("utf-8", "replace"))


def artifact_payload(path):
    return json.dumps({"session_id": "verify", "tool_name": "Artifact",
                       "tool_input": {"file_path": path}})


def write_payload(path):
    return json.dumps({"session_id": "verify", "tool_name": "Write",
                       "tool_input": {"file_path": path}})


NAMES = style.all_theme_names()
LOADED = {}
for _n in NAMES:
    try:
        LOADED[_n] = style.load_theme(_n)
    except Exception:
        LOADED[_n] = None

print()
print("house-style - verification (Python)")
print("===================================")
print(f"Interpreter: {sys.executable}")
print(f"style.py:    {STYLE}")
print(f"themes:      {THEMES}")
print()
print("No check here touches the network. The catalogue is an expansion; the shipped themes")
print("are the floor, and the floor has to hold with the cable unplugged.")
print()

# --- themes are present and valid -----------------------------------------------------
report("PASS" if len(NAMES) >= 3 else "FAIL",
       f"at least three themes ship with the plugin (found {len(NAMES)})")
print(f"          themes: {', '.join(NAMES) or '(none)'}")

for n in NAMES:
    t = LOADED[n]
    if t is None:
        report("FAIL", f"theme {n} loads as JSON")
        continue
    problems = style.validate(t, n)
    report("PASS" if not problems else "FAIL", f"theme {n} validates against the schema")
    for p in problems:
        print(f"          {p}")

report("PASS" if style.FALLBACK in NAMES else "FAIL",
       f"the fallback theme ({style.FALLBACK}) is one of the shipped themes")

# --- the variety rule -----------------------------------------------------------------
# Themes are edited one at a time, each edit individually reasonable, and three distinct looks
# quietly converge into three tints of whichever was touched last. This cannot prove taste; it
# proves nobody made the choice meaningless.
for axis, get in (
    ("accent", lambda t: t["colour"][t["defaultScheme"]]["accent"]),
    ("body font", lambda t: t["fonts"]["body"]["family"]),
    ("display font", lambda t: t["fonts"]["display"]["family"]),
    ("radius", lambda t: t["shape"]["radius"]),
    ("scale ratio", lambda t: t["scale"]["ratio"]),
    ("measure", lambda t: t["shape"]["measure"]),
    ("prose tone", lambda t: t["voice"]["proseTone"]),
):
    vals = [get(LOADED[n]) for n in NAMES if LOADED[n]]
    uniq = len(set(map(str, vals)))
    report("PASS" if uniq == len(vals) else "FAIL",
           f"no two themes share a {axis}")
    print(f"          {uniq} distinct across {len(vals)} themes")

# --- the CSP rule ---------------------------------------------------------------------
# Artifacts load stylesheets from fonts.googleapis.com and nowhere else, with no visible error.
# A theme pointing elsewhere would render in a fallback face and nobody would be told why.
bad = []
for n in NAMES:
    t = LOADED[n]
    if not t:
        continue
    for role in style.FONT_ROLES:
        u = t["fonts"][role].get("googleFontsUrl", "")
        if not str(u).startswith("https://fonts.googleapis.com/"):
            bad.append(f"{n}.{role} -> {u}")
report("PASS" if not bad else "FAIL",
       "every font URL points at fonts.googleapis.com, the only allowed stylesheet host")
for b in bad:
    print(f"          {b}")

# Some surfaces load no webfont at all. A theme with no system stack has nothing to be there.
bad = []
for n in NAMES:
    t = LOADED[n]
    if not t:
        continue
    for role in style.FONT_ROLES:
        ss = t["fonts"][role].get("systemStack", "")
        if not str(ss).strip() or t["fonts"][role]["family"] in ss:
            bad.append(f"{n}.{role}")
report("PASS" if not bad else "FAIL",
       "every theme has a webfont-free system stack for the offline surfaces")
for b in bad:
    print(f"          {b} has an empty system stack, or names its own webfont in it")

# --- rendered CSS ---------------------------------------------------------------------
for n in NAMES:
    t = LOADED[n]
    if not t:
        continue
    css = style.render_css(t)
    ok = (
        css.startswith(f"/* {style.MARKER_PREFIX} {n} */")
        and ":root {" in css
        and "@media (prefers-color-scheme: dark)" in css
        and ':root:not([data-theme="light"])' in css
        and ':root[data-theme="dark"]' in css
        and ':root[data-theme="light"]' in css
    )
    report("PASS" if ok else "FAIL",
           f"{n} renders a marker plus all three theme-state blocks")

# Every token must be defined on bare :root. A token defined only inside a media block is
# undefined in the other two states, and the page silently borrows the host's ground.
for n in NAMES:
    t = LOADED[n]
    if not t:
        continue
    root = style.render_css(t).split(":root {", 1)[1].split("}", 1)[0]
    missing = [tok for tok in style.COLOUR_TOKENS if f"--{tok}:" not in root]
    report("PASS" if not missing else "FAIL",
           f"{n} defines every colour token on bare :root")
    if missing:
        print(f"          missing: {missing}")

for n in NAMES:
    t = LOADED[n]
    if not t:
        continue
    css = style.render_css(t, system=True)
    report("PASS" if "fonts.googleapis.com" not in css and "@import" not in css else "FAIL",
           f"{n} --system renders with no external reference at all")

# The derived ladder must actually follow the ratio it claims.
for n in NAMES:
    t = LOADED[n]
    if not t:
        continue
    steps = dict(style.scale_steps(t))
    r = float(t["scale"]["ratio"])
    ok = abs(steps["--step-0"] - 1.0) < 1e-6 and abs(steps["--step-1"] - r) < 1e-3
    report("PASS" if ok else "FAIL", f"{n}'s type scale is derived from its own ratio")

# --- style (SessionStart) -------------------------------------------------------------
code, out, err = run_hook("style", "{}")
ok = code == 0 and '"hookEventName":"SessionStart"' in out and '"additionalContext"' in out
report("PASS" if ok else "FAIL", "style emits SessionStart additionalContext and exits 0")
print(f"          exit {code}, {len(out)} bytes")

report("PASS" if '"hookSpecificOutput":{"hookEventName"' in out else "FAIL",
       "style emits compact JSON (no space after the colon)")

try:
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
except Exception:
    ctx = ""
active = style.resolve_theme()[1]
report("PASS" if active and active in ctx else "FAIL",
       "the injected context names the active theme")
report("PASS" if LOADED.get(active) and LOADED[active]["voice"]["proseTone"] in ctx else "FAIL",
       "the injected context carries the theme's prose voice, not only its colours")
for other in NAMES:
    if other != active:
        report("PASS" if other in ctx else "FAIL",
               f"the injected context offers {other} as an alternate")

report("PASS" if "marker" in ctx and style.MARKER_PREFIX in ctx else "FAIL",
       "the injected rule tells Claude to stamp the marker the publish check looks for")

# The block is re-paid every session and on every subagent spawn, so its size is a real cost.
report("PASS" if len(ctx) < 2000 else "FAIL",
       f"the injected block stays compact ({len(ctx)} chars, budget 2000)")

# --- styleguard (PreToolUse) — the three-tier ladder ----------------------------------
tmp = tempfile.mkdtemp(prefix="house-style-verify-")
good = os.path.join(tmp, "good.html")
plain = os.path.join(tmp, "plain.html")
unknown = os.path.join(tmp, "unknown.html")
notvisual = os.path.join(tmp, "notes.md")
with open(good, "w", encoding="utf-8") as f:
    f.write(f"<style>/* {style.MARKER_PREFIX} {NAMES[0]} */</style>")
with open(plain, "w", encoding="utf-8") as f:
    f.write("<style>body{color:red}</style>")
with open(unknown, "w", encoding="utf-8") as f:
    f.write(f"<style>/* {style.MARKER_PREFIX} neon-vaporwave */</style>")
with open(notvisual, "w", encoding="utf-8") as f:
    f.write("# notes")

# Silent when compliant. A hook that fires on a correct publish cannot end quietly - the turn
# continues, and the only thing left to say is that nothing needed saying. Same trade the
# handover hook already makes.
code, out, err = run_hook("styleguard", artifact_payload(good))
report("PASS" if code == 0 and out == "" else "FAIL",
       "styleguard stays SILENT on a page carrying a known marker")
print(f"          exit {code}, stdout {len(out)} bytes")

code, out, err = run_hook("styleguard", artifact_payload(plain))
ok = code == 0 and '"permissionDecision":"ask"' in out
report("PASS" if ok else "FAIL", "styleguard ASKS on a page with no marker")

if ok:
    reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
    report("PASS" if active in reason else "FAIL",
           "the ask names the active theme")
    report("PASS" if any(n in reason for n in NAMES if n != active) else "FAIL",
           "the ask offers alternates to rebuild on")

code, out, err = run_hook("styleguard", artifact_payload(unknown))
ok = code == 0 and '"permissionDecision":"ask"' in out and "neon-vaporwave" in out
report("PASS" if ok else "FAIL",
       "styleguard ASKS on a page stamped with an unknown theme, and names it")

code, out, err = run_hook("styleguard", artifact_payload(notvisual))
report("PASS" if code == 0 and out == "" else "FAIL",
       "styleguard ignores a non-visual file")

code, out, err = run_hook("styleguard", json.dumps(
    {"tool_name": "Artifact", "tool_input": {"action": "list"}}))
report("PASS" if code == 0 and out == "" else "FAIL",
       "styleguard ignores an Artifact action that publishes nothing")

# Tier 2: payload does not parse, but a file_path is still in there - behave as before.
code, out, err = run_hook("styleguard", f'garbage "file_path":"{plain}" garbage')
report("PASS" if code == 0 and '"permissionDecision":"ask"' in out else "FAIL",
       "styleguard tier 2: unparseable payload with a file_path is still judged")

# Tier 3: fails CLOSED. This is the last moment before a page goes public.
code, out, err = run_hook("styleguard", "not json, names no file at all")
report("PASS" if code == 2 else "FAIL",
       "styleguard tier 3: an unreadable payload naming no file BLOCKS (exit 2)")
print(f"          exit {code}, stderr: {err.strip()[:80]}")

code, out, err = run_hook("styleguard", "")
report("PASS" if code == 0 else "FAIL",
       "styleguard exits 0 on an empty payload (the harness, not a publish)")

# --- styled (PostToolUse) -------------------------------------------------------------
code, out, err = run_hook("styled", write_payload(plain))
report("PASS" if code == 0 and out == "" else "FAIL",
       "styled ignores a scratch-directory write (house-rules' artifact hook owns those)")

inproj = os.path.join(ROOT, "_verify_style_tmp.html")
try:
    with open(inproj, "w", encoding="utf-8") as f:
        f.write("<style>body{}</style>")
    code, out, err = run_hook("styled", write_payload(inproj))
    ok = code == 0 and '"hookEventName":"PostToolUse"' in out
    report("PASS" if ok else "FAIL", "styled reminds on an unthemed in-project visual file")

    with open(inproj, "w", encoding="utf-8") as f:
        f.write(f"<style>/* {style.MARKER_PREFIX} {NAMES[0]} */</style>")
    code, out, err = run_hook("styled", write_payload(inproj))
    report("PASS" if code == 0 and out == "" else "FAIL",
           "styled stays silent once the file carries a marker")
finally:
    if os.path.exists(inproj):
        os.remove(inproj)

code, out, err = run_hook("styled", write_payload(os.path.join(ROOT, "README.md")))
report("PASS" if code == 0 and out == "" else "FAIL",
       "styled ignores a non-visual in-project write")

# Every non-blocking handler must exit 0 on every failure path. styled runs on PostToolUse,
# which cannot block, and style runs at SessionStart, where a non-zero exit helps nobody.
for ev in ("style", "styled"):
    codes = [
        run_hook(ev, "")[0],
        run_hook(ev, "{")[0],
        run_hook(ev, "null")[0],
        run_hook(ev, json.dumps({"tool_input": {"file_path": "/nonexistent/x.html"}}))[0],
    ]
    report("PASS" if all(c == 0 for c in codes) else "FAIL",
           f"{ev} exits 0 on every failure path (got {codes})")

# Hook events and CLI subcommands share one namespace, so a renamed hook event must not be
# read as a hook failure - on PreToolUse a non-zero exit for a typo is a blocked tool call.
report("PASS" if run_hook("nonsense-event")[0] == 0 else "FAIL",
       "an unknown event name is a no-op, not an error")
report("PASS" if run_cli(["use", "no-such-theme"])[0] != 0 else "FAIL",
       "...but a real CLI failure still exits non-zero")

shutil.rmtree(tmp, ignore_errors=True)

# --- resolution order -----------------------------------------------------------------
tmp = tempfile.mkdtemp(prefix="house-style-pin-")
try:
    os.makedirs(os.path.join(tmp, ".claude"))
    pinned = [n for n in NAMES if n != style.FALLBACK][0]
    with open(os.path.join(tmp, ".claude", "style.json"), "w", encoding="utf-8") as f:
        json.dump({"theme": pinned}, f)
    code, out, err = run_cli(["show"], cwd=tmp)
    report("PASS" if code == 0 and pinned in out else "FAIL",
           f"a project pin (.claude/style.json) selects the theme ({pinned})")

    # A pin naming a theme that no longer exists is a stale pin, not a crash.
    with open(os.path.join(tmp, ".claude", "style.json"), "w", encoding="utf-8") as f:
        json.dump({"theme": "deleted-long-ago"}, f)
    code, out, err = run_cli(["show"], cwd=tmp)
    report("PASS" if code == 0 and style.FALLBACK in out else "FAIL",
           "a stale pin falls through to the fallback rather than failing")

    with open(os.path.join(tmp, ".claude", "style.json"), "w", encoding="utf-8") as f:
        f.write("{ not json at all")
    code, out, err = run_cli(["show"], cwd=tmp)
    report("PASS" if code == 0 else "FAIL", "a corrupt pin file does not take the CLI down")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# --- CLI ------------------------------------------------------------------------------
for args, want in (
    (["list"], NAMES[0]),
    (["validate"], "3/3"),
    (["css", NAMES[0]], "--accent"),
    (["show"], "Active house style"),
):
    code, out, err = run_cli(args)
    report("PASS" if code == 0 and want in out else "FAIL",
           f"style.py {' '.join(args)} works offline")

code, out, err = run_cli(["use", "no-such-theme"])
report("PASS" if code != 0 else "FAIL",
       "style.py use rejects a theme that does not exist")

# --- gallery generation, offline ------------------------------------------------------
tmp = tempfile.mkdtemp(prefix="house-style-gallery-")
try:
    g = os.path.join(tmp, "g.html")
    code, out, err = run_cli(["gallery", "--offline", g])
    ok = code == 0 and os.path.exists(g)
    report("PASS" if ok else "FAIL", "the gallery generates with no network at all")
    if ok:
        html = read(g)
        left = [p for p in ("__TITLE__", "__FONTS__", "__CARDS__", "__META__", "__DATA__")
                if p in html]
        report("PASS" if not left else "FAIL",
               "every gallery placeholder was substituted")
        if left:
            print(f"          left behind: {left}")
        # One specimen per theme, exactly. Substitution runs over the whole file, so a
        # placeholder named inside a comment would fill in too and every card would appear
        # twice - once in the page and once in the comment.
        for n in NAMES:
            c = html.count(f'id="stage-{n}"')
            report("PASS" if c == 1 else "FAIL",
                   f"the gallery renders exactly one {n} specimen (found {c})")
        import re as _re
        urls = [u for u in _re.findall(r'https?://[^"\'\s)]+', html)
                if "fonts.googleapis.com" not in u and "fonts.gstatic.com" not in u]
        report("PASS" if not urls else "FAIL",
               "the gallery references no host outside the artifact CSP allowlist")
        for u in urls:
            print(f"          {u}")
        report("PASS" if 'claude.use("db")' in html else "FAIL",
               "the gallery reaches db through claude.use, the documented accessor")
        report("PASS" if "/house-style use " in html else "FAIL",
               "the gallery shows the terminal command, so it works with no db at all")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# --- run.sh, the shim -----------------------------------------------------------------
env = dict(os.environ)
env["PATH"] = ""
env["HOUSE_STYLE_PYTHON"] = ""
code, out, err = run_shell([RUN, "styleguard"], "{}", env)
report("PASS" if code == 2 else "FAIL",
       "run.sh with no interpreter BLOCKS for styleguard (fails closed)")
code, out, err = run_shell([RUN, "style"], "{}", env)
report("PASS" if code == 0 and "systemMessage" in out else "FAIL",
       "run.sh with no interpreter still SPEAKS for style (fails loud, not closed)")
code, out, err = run_shell([RUN, "styled"], "{}", env)
report("PASS" if code == 0 and out == "" else "FAIL",
       "run.sh with no interpreter is silent for styled (cannot block anyway)")

env = dict(os.environ)
env["HOUSE_STYLE_PYTHON"] = "definitely-not-a-real-interpreter"
code, out, err = run_shell([RUN, "style"], "{}", env)
report("PASS" if code == 0 and "hookSpecificOutput" in out else "FAIL",
       "a bogus HOUSE_STYLE_PYTHON is probed and rejected, not trusted blindly")

# --- registration and drift -----------------------------------------------------------
hooks = json.loads(read(HOOKS_JSON))
registered = set()
commands = []
for event, entries in hooks["hooks"].items():
    for entry in entries:
        for h in entry["hooks"]:
            commands.append(h["command"])
            registered.add(h["command"].rsplit(" ", 1)[-1])

report("PASS" if registered == set(style.EVENTS) else "FAIL",
       "hooks.json registers exactly the events style.py implements")
print(f"          registered {sorted(registered)} / implemented {sorted(style.EVENTS)}")

report("PASS" if all("run.sh" in c for c in commands) else "FAIL",
       "nothing but run.sh is registered on any event")

report("PASS" if all("${CLAUDE_PLUGIN_ROOT}" in c for c in commands) else "FAIL",
       "every hook command is rooted at ${CLAUDE_PLUGIN_ROOT}")

# The CLAUDE.md table is the documentation of record for these hooks. Both directions, so a
# hook added without a row and a row left behind after a hook is removed both fail.
md = read(CLAUDEMD)
in_md = {e for e in style.EVENTS if f"`{e}`" in md}
report("PASS" if in_md == set(style.EVENTS) else "FAIL",
       "CLAUDE.md documents every house-style hook event")
print(f"          documented {sorted(in_md)} / registered {sorted(registered)}")

# hook.py's reminder strings restate rules; these restate the schema. Same drift risk, so the
# same check: if the marker shape changes in one place it has to change in all of them.
for path, label in ((TOKENS, "templates/tokens.css"),
                    (COMMAND, "commands/house-style.md"),
                    (SCHEMA, "themes/schema.md")):
    report("PASS" if style.MARKER_PREFIX in read(path) else "FAIL",
           f"{label} states the marker the styleguard hook actually looks for")

report("PASS" if all(t in read(SCHEMA) for t in style.COLOUR_TOKENS) else "FAIL",
       "themes/schema.md lists every colour token style.py requires")

# --- the step card must stay self-contained -------------------------------------------
# It is opened off disk on a machine mid-install, which may have no network at all. This
# plugin exists to put fonts on pages; the one page it must never touch is that one.
if os.path.exists(STEPCARD):
    sc = read(STEPCARD)
    import re as _re
    ext = _re.findall(r'(?:href|src)="(https?://[^"]+)', sc)
    report("PASS" if not ext else "FAIL",
           "step-card.html still loads no external stylesheet, font or script")
    for u in ext:
        print(f"          {u}")
    report("PASS" if all(f"--{t}" in sc for t in
                         ("bg", "card", "ink", "muted", "line", "accent")) else "FAIL",
           "step-card.html still uses the shared token names, so it stays themeable")

# --- marketplace ----------------------------------------------------------------------
mk = json.loads(read(MARKETPLACE))
names = [p["name"] for p in mk["plugins"]]
report("PASS" if "house-style" in names else "FAIL",
       "the marketplace lists house-style alongside house-rules")
print(f"          plugins: {names}")
entry = next((p for p in mk["plugins"] if p["name"] == "house-style"), None)
report("PASS" if entry and os.path.isdir(os.path.join(ROOT, entry["source"])) else "FAIL",
       "the marketplace source path for house-style resolves to a real directory")
report("PASS" if "Currently one plugin" not in json.dumps(mk) else "FAIL",
       "the marketplace description no longer claims there is only one plugin")

print()
if FAILURES:
    print(f"RESULT: FAIL - {FAILURES} of {STEP} checks failed")
else:
    print(f"RESULT: PASS - all {STEP} checks passed")
print()
sys.exit(0 if FAILURES == 0 else 1)
