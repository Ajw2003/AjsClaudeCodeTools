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
ARTIFACTS = os.path.join(ROOT, "docs", "artifacts")
MANIFEST = os.path.join(ARTIFACTS, "manifest.json")

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


SKIPPED = 0


def skip(title, why):
    global STEP, SKIPPED
    STEP += 1
    SKIPPED += 1
    print(f"{STEP:2d}. SKIP  {title}")
    print(f"          {why}")


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
COMMANDS_IMPLEMENTED = set(style.COMMANDS)
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
# The axes come from style.VARIETY_AXES, not a copy of it. install enforces the same rule from
# the same list, so the suite and the gate cannot disagree about what "distinct" means.
for axis, get in style.VARIETY_AXES:
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
    # Count-agnostic: "N/N themes valid" holds however many ship. Asserting "3/3" made this
    # check fail the moment a fourth theme was added, which is a suite that breaks on correct
    # changes - exactly the drift the runtime check count elsewhere exists to avoid.
    (["validate"], f"{len(NAMES)}/{len(NAMES)} themes valid"),
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

    # The card's palette IS quarry. That is not a coincidence to be re-noticed later - the theme
    # was authored from this file so adopting it renamed nothing. Assert it, or the two drift
    # apart the first time either is nudged and nobody finds out.
    def _block(pat):
        m = _re.search(pat + r"\s*\{(.*?)\}", sc, _re.S)
        return dict(_re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})", m.group(1))) if m else {}

    q = LOADED.get("quarry")
    if q:
        for scheme, pat in (("light", r":root"),
                            ("dark", r':root:not\(\[data-theme="light"\]\)')):
            got = _block(pat)
            want = q["colour"][scheme]
            diff = [k for k, v in want.items() if k in got and got[k].lower() != v.lower()]
            absent = [k for k in want if k not in got]
            report("PASS" if not diff and not absent else "FAIL",
                   f"step-card.html's {scheme} palette matches the quarry theme exactly")
            for k in diff:
                print(f"          {k}: card {got[k]} vs quarry {want[k]}")
            if absent:
                print(f"          in quarry but not the card: {absent}")

    report("PASS" if style.MARKER_PREFIX in sc else "FAIL",
           "step-card.html carries the marker, so publishing it raises no prompt")

# --- the constraint export --------------------------------------------------------------
# The builder page re-checks in JS what validate() checks here. It must not re-STATE it: these
# assertions are what make the export the single source, so a token added to COLOUR_TOKENS
# reaches the builder or this fails.
C = style.constraints()
for key, want in (
    ("colourTokens", list(style.COLOUR_TOKENS)),
    ("fontRoles", list(style.FONT_ROLES)),
    ("fontKeys", list(style.FONT_KEYS)),
    ("scaleKeys", list(style.SCALE_KEYS)),
    ("shapeKeys", list(style.SHAPE_KEYS)),
    ("voiceKeys", list(style.VOICE_KEYS)),
    ("identityKeys", list(style.IDENTITY_KEYS)),
):
    report("PASS" if C.get(key) == want else "FAIL",
           f"constraints() exports {key} matching the module constant")

report("PASS" if C.get("marker") == style.MARKER_PREFIX else "FAIL",
       "constraints() exports the marker the styleguard hook looks for")
report("PASS" if C.get("varietyAxes") == [n for n, _ in style.VARIETY_AXES] else "FAIL",
       "constraints() exports the same variety axes install enforces")
report("PASS" if C.get("fontUrlPrefix") == "https://fonts.googleapis.com/" else "FAIL",
       "constraints() exports the only font host the CSP allows")

# Every enum in the export must be the set validate() actually accepts - proven by feeding a
# value outside it and requiring a complaint, rather than by reading both lists.
for field, path in (("defaultScheme", ("defaultScheme",)),
                    ("density", ("voice", "density")),
                    ("headingStyle", ("voice", "headingStyle")),
                    ("prefer", ("voice", "prefer"))):
    t = json.loads(json.dumps(LOADED[NAMES[0]]))
    node = t
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = "definitely-not-a-valid-value"
    rejected = any(field in p for p in style.validate(t, NAMES[0]))
    report("PASS" if rejected and C["enums"].get(field) else "FAIL",
           f"the {field} enum is exported and validate() enforces it")

# --- install, the gate ------------------------------------------------------------------
def _install(theme, extra=None):
    e = dict(os.environ)
    proc = subprocess.run(
        [sys.executable, STYLE, "install", "-"] + (extra or []),
        input=json.dumps(theme).encode("utf-8"),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=e,
    )
    return (proc.returncode,
            proc.stdout.decode("utf-8", "replace"),
            proc.stderr.decode("utf-8", "replace"))

code, out, err = _install({"name": "broken", "label": "B"})
report("PASS" if code != 0 and "Refusing to install" in err else "FAIL",
       "install refuses an invalid theme and says what is wrong")

base = json.loads(json.dumps(LOADED[NAMES[0]]))
base["name"] = "verify-clone"
base["label"] = "Verify Clone"
code, out, err = _install(base)
report("PASS" if code != 0 and "not distinct enough" in err else "FAIL",
       "install refuses a theme that collides on the variety axes")
report("PASS" if not os.path.exists(style.theme_path("verify-clone")) else "FAIL",
       "a refused install writes no file")

code, out, err = _install(base, ["--force"])
wrote = os.path.exists(style.theme_path("verify-clone"))
report("PASS" if code == 0 and wrote else "FAIL",
       "install --force writes a deliberate collision, and says which axes collided")
if wrote:
    try:
        back = style.load_theme("verify-clone")
        differing = sorted(k for k in set(back) | set(base) if back.get(k) != base.get(k))
        report("PASS" if not differing else "FAIL",
               "an installed theme round-trips byte-for-byte through the format")
        report("PASS" if not style.validate(back, "verify-clone") else "FAIL",
               "an installed theme validates when loaded back")
        code, out, err = _install(base)
        report("PASS" if code != 0 and "already exists" in err else "FAIL",
               "install refuses to clobber an existing theme without --force")
    finally:
        os.remove(style.theme_path("verify-clone"))

# --- the builder ------------------------------------------------------------------------
tmp = tempfile.mkdtemp(prefix="house-style-builder-")
try:
    b = os.path.join(tmp, "b.html")
    code, out, err = run_cli(["builder", "--offline", b])
    ok = code == 0 and os.path.exists(b)
    report("PASS" if ok else "FAIL", "the builder generates with no network at all")
    if ok:
        html = read(b)
        left = [p for p in ("__TITLE__", "__FONTS__", "__DATA__", "__CONSTRAINTS__",
                            "__FAMILIES__", "__THEMES__") if p in html]
        report("PASS" if not left else "FAIL", "every builder placeholder was substituted")
        if left:
            print(f"          left behind: {left}")

        import re as _re2
        # fonts.google.com is the specimen page a theme records in sources[] as provenance -
        # a string written into JSON, never fetched. The two that ARE loaded are googleapis
        # (the stylesheet) and gstatic (the font files), and they are the only two the CSP
        # admits. Checked separately below that the provenance host is never a load.
        ALLOWED = ("fonts.googleapis.com", "fonts.gstatic.com", "fonts.google.com")
        urls = [u for u in _re2.findall(r'https?://[^"\'\s)]+', html)
                if not any(a in u for a in ALLOWED)]
        report("PASS" if not urls else "FAIL",
               "the builder references no host outside the artifact CSP allowlist")
        for u in urls:
            print(f"          {u}")

        loads = _re2.findall(r'(?:href|src)\s*=\s*["\']?(https?://[^"\'\s>]+)', html)
        bad_loads = [u for u in loads
                     if "fonts.googleapis.com" not in u and "fonts.gstatic.com" not in u]
        report("PASS" if not bad_loads else "FAIL",
               "every resource the builder actually loads comes from an allowed host")
        for u in bad_loads:
            print(f"          {u}")

        # Offline is exactly when the floor matters: a font picker with nothing in it is not a
        # builder, so the curated families must be there when the catalogue is not.
        report("PASS" if len(style.FALLBACK_FAMILIES) >= 40 else "FAIL",
               f"a curated font floor ships ({len(style.FALLBACK_FAMILIES)} families)")
        fam_ok = all(any(f["category"] == c for f in style.FALLBACK_FAMILIES)
                     for c in ("serif", "sans-serif", "monospace"))
        report("PASS" if fam_ok else "FAIL",
               "the font floor covers every role: serif, sans-serif and monospace")
        first = style.FALLBACK_FAMILIES[0]["family"].replace(" ", "+")
        report("PASS" if first in html or "families" in html else "FAIL",
               "the builder page carries a populated font list when offline")

        report("PASS" if 'claude.use("db")' in html else "FAIL",
               "the builder reaches db through claude.use, the documented accessor")
        for step in ("identity", "type", "colour", "shape", "voice", "save"):
            c = html.count(f'data-step="{step}"')
            report("PASS" if c == 1 else "FAIL",
                   f"the builder renders exactly one {step} step (found {c})")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# --- the colour deriver -------------------------------------------------------------------
# The builder's whole promise is "pick two colours and the rest is derived". If the derivation
# can produce an unreadable pair, the promise is false and nothing else in the page saves it.
# Contrast is meant to be a property of the output, so it is asserted on the output.
#
# The deriver is JS, so this needs node. It is extracted from the GENERATED page rather than
# from the template, so what is tested is what ships. Where node is missing the check skips
# loudly rather than quietly not existing.
NODE = shutil.which("node")
tmp = tempfile.mkdtemp(prefix="house-style-derive-")
try:
    b = os.path.join(tmp, "b.html")
    code, out, err = run_cli(["builder", "--offline", b])
    html = read(b) if code == 0 and os.path.exists(b) else ""
    marker = "/* ---------------------------------------------------------------------------\n   state"
    if not html or "function h2r(" not in html or marker not in html:
        report("FAIL", "the deriver can be located in the generated builder")
    elif not NODE:
        skip("the derived palette meets its contrast targets",
             "node is not on PATH, so the JS deriver could not be executed here")
    else:
        js = html[html.index("function h2r("):html.index(marker)]
        with open(os.path.join(tmp, "d.mjs"), "w", encoding="utf-8") as f:
            f.write(js + "\nexport { derive, contrast, rgb2hsl, solveOn };\n")

        # A SWEEP, not a case list. The hand-picked cases this replaces all happened to sit
        # outside the band where the derivation was broken: a ground anywhere between roughly
        # 12% and 75% lightness cannot reach a 12:1 ink at any hue (#787878 tops out at 4.76
        # against black), and the old solveOn answered an unreachable target with the value it
        # was initialised with - so ink, muted and the user's chosen accent all silently became
        # #ffffff. The nearest case in the list scraped past at 12.8:1 and hid the whole band.
        # Sweeping the full range is what makes that class of bug impossible to miss again.
        runner = """
import { derive, contrast, rgb2hsl, solveOn } from "./d.mjs";
const REQ = [
  ["ink on bg", (c) => contrast(c.ink, c.bg), 7.0],
  ["muted on bg", (c) => contrast(c.muted, c.bg), 4.5],
  ["accent on bg", (c) => contrast(c.accent, c.bg), 4.5],
  ["accent-ink on accent", (c) => contrast(c["accent-ink"], c.accent), 4.5],
  ["ink on card", (c) => contrast(c.ink, c.card), 7.0],
  ["warn-ink on warn-bg", (c) => contrast(c["warn-ink"], c["warn-bg"]), 4.5],
  ["ink vs muted", (c) => contrast(c.ink, c.muted), 1.6],
];
function hsl(h, s, l) {
  const f = (n) => { const k=(n+h*12)%12, a=s*Math.min(l,1-l);
    return Math.round((l - a*Math.max(-1,Math.min(k-3,Math.min(9-k,1))))*255); };
  return "#" + [f(0),f(8),f(4)].map(v=>v.toString(16).padStart(2,"0")).join("");
}
let n = 0, bad = [], kept = 0, keptTotal = 0, pairs = 0;
const hues = [0, 0.08, 0.17, 0.33, 0.5, 0.66, 0.83];
const sats = [0, 0.15, 0.45, 0.85];
const accents = ["#0f766e", "#2f6f4f", "#5b3df5", "#b3261e", "#e2643c", "#767676"];
for (const h of hues) for (const s of sats)
  for (let L = 0.02; L <= 0.98; L += 0.05) {
    const ground = hsl(h, s, L);
    for (const acc of accents) {
      pairs++;
      const d = derive(ground, acc);
      for (const scheme of ["light", "dark"]) {
        const c = d[scheme];
        for (const [label, fn, min] of REQ) {
          n++; const r = fn(c);
          if (r < min) bad.push(ground+"/"+acc+"/"+scheme+": "+label+" "+r.toFixed(2)+" < "+min);
        }
        if (c.ink === c.muted) bad.push(ground+"/"+acc+"/"+scheme+": ink === muted");
        // The warn tokens lean toward the ground but must stay recognisably amber. An
        // unclamped nudge toward a blue ground reached 0.19 - chartreuse - which reads as a
        // highlighter pen, not a warning, and warning is the one job the token has.
        const wh = rgb2hsl(c["warn-bg"])[0];
        if (wh < 0.05 || wh > 0.13) {
          bad.push(ground+"/"+acc+"/"+scheme+": warn hue "+wh.toFixed(3)+" left the amber band");
        }
        const dh = Math.abs(rgb2hsl(c.accent)[0] - rgb2hsl(acc)[0]);
        const spin = Math.min(dh, 1 - dh) * 360;
        if (spin > 12 && rgb2hsl(acc)[1] > 0.1) {
          bad.push(ground+"/"+acc+"/"+scheme+": accent hue moved "+spin.toFixed(0)+"deg");
        }
        if (scheme === "light" && contrast(acc, c.bg) >= 4.5) {
          keptTotal++;
          if (c.accent.toLowerCase() === acc.toLowerCase()) kept++;
          else bad.push(ground+"/"+acc+": accent passed but was changed to "+c.accent);
        }
      }
    }
  }
const rep = derive("#787878", "#0f766e");
console.log(JSON.stringify({
  bad: bad.slice(0, 12), nbad: bad.length, n: n, pairs: pairs,
  kept: kept, keptTotal: keptTotal,
  unreachableIsNull: solveOn("#787878", 0.5, 0.2, 12) === null,
  reportedAccent: rep.light.accent,
  reportedBg: rep.light.bg,
  reportedInk: rep.light.ink,
  reportedMoved: rep.notes.light.accentMoved
}));
"""
        with open(os.path.join(tmp, "run.mjs"), "w", encoding="utf-8") as f:
            f.write(runner)
        proc = subprocess.run([NODE, os.path.join(tmp, "run.mjs")], cwd=tmp,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            report("FAIL", "the deriver runs without error")
            print(f"          {proc.stderr.decode('utf-8', 'replace').strip()[:300]}")
        else:
            res = json.loads(proc.stdout.decode("utf-8", "replace"))

            report("PASS" if not res["nbad"] else "FAIL",
                   f"every derived palette meets every contrast target "
                   f"({res['n']} assertions over {res['pairs']} ground/accent pairs, "
                   f"both schemes, grounds swept 2%-98% lightness)")
            for line in res["bad"]:
                print(f"          {line}")
            if res["nbad"] > len(res["bad"]):
                print(f"          ... and {res['nbad'] - len(res['bad'])} more")

            # The defect itself: a search that cannot find an answer must say so rather than
            # returning the value it started with.
            report("PASS" if res["unreachableIsNull"] else "FAIL",
                   "solveOn returns null for an unreachable target, never a silent fallback")

            # An accent that already reads on the ground must survive untouched - otherwise
            # "pick an accent" quietly means "suggest an accent".
            report("PASS" if res["kept"] == res["keptTotal"] and res["keptTotal"] else "FAIL",
                   f"an accent that already passes is preserved, not adjusted "
                   f"({res['kept']}/{res['keptTotal']})")

            # The exact case that was reported: a mid-grey ground threw the teal away.
            teal_ok = res["reportedAccent"].lower() == "#0f766e"
            report("PASS" if teal_ok else "FAIL",
                   "the reported case keeps its accent: ground #787878 + accent #0f766e")
            print(f"          bg {res['reportedBg']}  ink {res['reportedInk']}  "
                  f"accent {res['reportedAccent']}  (moved: {res['reportedMoved']})")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# --- the committed artefacts ------------------------------------------------------------
# docs/artifacts/ holds the generated gallery and builder pages so they outlive the session
# that made them. A generated file in version control drifts from its generator: add a theme,
# forget to regenerate, and the committed page describes a world that no longer exists - which
# is worse than no page, because it looks authoritative. These checks are what stop that.
#
# Structural, not byte-exact, on purpose: both pages embed a generation timestamp and the live
# font catalogue, so regenerating never reproduces the same bytes and a byte comparison would
# fail for reasons that mean nothing.
if os.path.isdir(ARTIFACTS):
    manifest = json.loads(read(MANIFEST))
    listed = {a["file"]: a for a in manifest.get("artifacts", [])}
    on_disk = sorted(f for f in os.listdir(ARTIFACTS) if f.endswith(".html"))

    # Both directions, like the CLAUDE.md hook table: a page nobody recorded and a record with
    # no page are both failures.
    report("PASS" if set(listed) == set(on_disk) else "FAIL",
           "every committed artefact is in the manifest, and every manifest entry has a file")
    print(f"          manifest {sorted(listed)} / on disk {on_disk}")

    for f, entry in sorted(listed.items()):
        for key in ("title", "url", "command", "published", "what"):
            if not entry.get(key):
                report("FAIL", f"{f}'s manifest entry records {key}")
        report("PASS" if entry.get("command") in COMMANDS_IMPLEMENTED else "FAIL",
               f"{f} records a real style.py subcommand ({entry.get('command')})")
        report("PASS" if str(entry.get("url", "")).startswith(
                   "https://claude.ai/code/artifact/") else "FAIL",
               f"{f} records where it is published")

    for f in on_disk:
        page = read(os.path.join(ARTIFACTS, f))

        # THE staleness check. Add a theme without regenerating and this fails.
        missing = [n for n in NAMES if n not in page]
        report("PASS" if not missing else "FAIL",
               f"{f} names every theme that ships (regenerate it if this fails)")
        if missing:
            print(f"          not mentioned: {missing}  -> "
                  f"style.py {listed.get(f, {}).get('command', '?')} docs/artifacts/{f}")

        # And the reverse: a page still advertising a theme that was deleted or renamed.
        import re as _re3
        stale = sorted({m for m in _re3.findall(r'id="stage-([a-z0-9-]+)"', page)
                        if m not in NAMES})
        report("PASS" if not stale else "FAIL",
               f"{f} names no theme that no longer exists")
        if stale:
            print(f"          stale: {stale}")

        # The same host rule the freshly generated pages are held to, applied to what shipped.
        ALLOWED_HOSTS = ("fonts.googleapis.com", "fonts.gstatic.com", "fonts.google.com")
        loads = _re3.findall(r'(?:href|src)\s*=\s*["\']?(https?://[^"\'\s>]+)', page)
        bad = [u for u in loads if not any(a in u for a in ALLOWED_HOSTS[:2])]
        report("PASS" if not bad else "FAIL",
               f"{f} loads no resource from outside the artifact CSP allowlist")
        for u in bad:
            print(f"          {u}")

    report("PASS" if os.path.isfile(os.path.join(ARTIFACTS, "README.md")) else "FAIL",
           "docs/artifacts explains that its HTML is generated, not hand-edited")
else:
    skip("the committed artefacts match the themes on disk",
         "docs/artifacts/ does not exist in this checkout")

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
tail = f" ({SKIPPED} skipped)" if SKIPPED else ""
if FAILURES:
    print(f"RESULT: FAIL - {FAILURES} of {STEP} checks failed{tail}")
else:
    print(f"RESULT: PASS - all {STEP - SKIPPED} checks passed{tail}")
print()
sys.exit(0 if FAILURES == 0 else 1)
