#!/usr/bin/env python3
"""style.py — the house-style hook handlers and the /house-style CLI, in one stdlib-only file.

run.sh resolves a working interpreter and execs this with the event name as argv[1]; the hook
payload arrives on stdin. The same file is also the CLI: `style.py list`, `use`, `show`, `css`,
`validate`, `refresh`, `gallery`. Hook events and subcommands share one namespace on purpose —
they read the same themes through the same resolver, so the theme a hook injects and the theme
the CLI prints can never disagree.

STDLIB ONLY. No third-party imports, nothing beyond CPython 3.8+. Same constraint as hook.py,
for the same reason: the thing that decides how every artifact looks must not itself be able to
fail on a missing dependency.

JSON OUTPUT: every hook payload is emitted with json.dumps(obj, separators=(",", ":")) — no
space after the colon — because verify_style.py asserts on the literal serialized bytes.

Failure-mode contract, per event, matching what each hook event actually permits:
  - style      (SessionStart) fails LOUD, not closed: emits a systemMessage, exits 0. There is
               nothing to block at session start, but silence would mean an unstyled session
               that nobody was told about.
  - styleguard (PreToolUse)   fails CLOSED and loud: stderr, exit 2. This is the last moment
               before a page goes public; an unreadable payload is not a reason to wave it past.
  - styled     (PostToolUse)  never obstructs. The write already happened.
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
THEMES_DIR = os.path.join(HERE, "..", "themes")
TEMPLATES_DIR = os.path.join(HERE, "..", "templates")

# Quarry is the fallback because it is the palette templates/step-card.html already ships with:
# falling back to it changes nothing that was already correct.
FALLBACK = "quarry"

COLOUR_TOKENS = (
    "bg", "card", "ink", "muted", "line", "accent", "accent-ink",
    "code-bg", "warn-bg", "warn-ink", "warn-line",
)
FONT_ROLES = ("display", "body", "mono")
FONT_KEYS = ("family", "googleFontsUrl", "stack", "systemStack", "weights")
SCALE_KEYS = ("base", "ratio", "lineHeight")
SHAPE_KEYS = ("radius", "border", "shadow", "space", "measure")
VOICE_KEYS = ("density", "headingStyle", "useEyebrow", "useLede", "prefer", "proseTone")
IDENTITY_KEYS = ("name", "label", "summary", "for", "defaultScheme", "sources")

_NAME_RE = re.compile(r"^[a-z0-9-]+$")

# The marker a themed page carries. styleguard stays silent when it finds this and asks when it
# does not, so the shape of it is load-bearing, not a comment.
MARKER_PREFIX = "house-style:"
_MARKER_RE = re.compile(r"house-style:\s*([a-z0-9-]+)")


def emit(obj):
    sys.stdout.write(json.dumps(obj, separators=(",", ":")))


def read_payload():
    try:
        return sys.stdin.buffer.read().decode("utf-8", "replace").strip()
    except Exception:
        return ""


def _read_text(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read()


# ---------------------------------------------------------------------------------------
# loading and validation
# ---------------------------------------------------------------------------------------


def theme_path(name):
    return os.path.normpath(os.path.join(THEMES_DIR, name + ".json"))


def load_theme(name):
    return json.loads(_read_text(theme_path(name)))


def all_theme_names():
    try:
        names = [
            f[:-5] for f in os.listdir(THEMES_DIR)
            if f.endswith(".json") and not f.startswith(".")
        ]
    except Exception:
        return []
    return sorted(names)


def validate(theme, name_hint=None):
    """Return a list of problems. Empty list means the theme is well-formed.

    Every field is required. There is no 'optional with a default' here - a default is a
    decision made outside the theme file, and the theme file is where the decisions live.
    """
    p = []

    for k in IDENTITY_KEYS:
        if k not in theme:
            p.append(f"missing identity key: {k}")
    name = theme.get("name", "")
    if not _NAME_RE.match(str(name)):
        p.append(f"name must match [a-z0-9-]+, got {name!r}")
    if name_hint is not None and name != name_hint:
        p.append(f"name {name!r} does not match filename {name_hint!r}")
    if theme.get("defaultScheme") not in ("light", "dark"):
        p.append("defaultScheme must be 'light' or 'dark'")
    if not isinstance(theme.get("sources"), list) or not theme.get("sources"):
        p.append("sources must be a non-empty list")
    else:
        for i, s in enumerate(theme["sources"]):
            for k in ("what", "url", "licence"):
                if not isinstance(s, dict) or not s.get(k):
                    p.append(f"sources[{i}] missing {k}")

    fonts = theme.get("fonts") or {}
    for role in FONT_ROLES:
        f = fonts.get(role)
        if not isinstance(f, dict):
            p.append(f"fonts.{role} missing")
            continue
        for k in FONT_KEYS:
            if k not in f:
                p.append(f"fonts.{role}.{k} missing")
        url = f.get("googleFontsUrl", "")
        # Not a style preference. Artifacts run under a CSP that blocks every stylesheet host
        # except fonts.googleapis.com, with no visible error - a theme pointing elsewhere would
        # silently render in a fallback face and nobody would be told why.
        if not str(url).startswith("https://fonts.googleapis.com/"):
            p.append(f"fonts.{role}.googleFontsUrl must start https://fonts.googleapis.com/")
        # step-card.html and any offline surface load no webfont at all. A theme with no system
        # stack has nothing to be on those surfaces.
        if not str(f.get("systemStack", "")).strip():
            p.append(f"fonts.{role}.systemStack must be non-empty")
        if "webfont" in str(f.get("systemStack", "")).lower():
            p.append(f"fonts.{role}.systemStack must not name a webfont")
        w = f.get("weights")
        if not isinstance(w, list) or not w or not all(isinstance(x, int) for x in w):
            p.append(f"fonts.{role}.weights must be a non-empty list of integers")

    colour = theme.get("colour") or {}
    for scheme in ("light", "dark"):
        c = colour.get(scheme)
        if not isinstance(c, dict):
            p.append(f"colour.{scheme} missing")
            continue
        for t in COLOUR_TOKENS:
            v = c.get(t)
            if not isinstance(v, str) or not re.match(r"^#[0-9a-fA-F]{6}$", v):
                p.append(f"colour.{scheme}.{t} must be a #rrggbb hex colour, got {v!r}")
        extra = set(c) - set(COLOUR_TOKENS)
        if extra:
            p.append(f"colour.{scheme} has unknown tokens: {sorted(extra)}")

    scale = theme.get("scale") or {}
    for k in SCALE_KEYS:
        if k not in scale:
            p.append(f"scale.{k} missing")
    if not isinstance(scale.get("ratio"), (int, float)) or not (1 < float(scale.get("ratio", 0)) < 2):
        p.append("scale.ratio must be a number between 1 and 2")

    shape = theme.get("shape") or {}
    for k in SHAPE_KEYS:
        if not str(shape.get(k, "")).strip():
            p.append(f"shape.{k} missing")

    voice = theme.get("voice") or {}
    for k in VOICE_KEYS:
        if k not in voice:
            p.append(f"voice.{k} missing")
    if voice.get("density") not in ("generous", "balanced", "tight"):
        p.append("voice.density must be generous, balanced or tight")
    if voice.get("headingStyle") not in ("sentence", "title"):
        p.append("voice.headingStyle must be sentence or title")
    if voice.get("prefer") not in ("prose", "table", "card"):
        p.append("voice.prefer must be prose, table or card")
    for k in ("useEyebrow", "useLede"):
        if not isinstance(voice.get(k), bool):
            p.append(f"voice.{k} must be a boolean")
    # proseTone is the half of this system that is not CSS. A theme without it would let the
    # same prose sit under three skins, which is a paint job rather than authorship.
    if not str(voice.get("proseTone", "")).strip():
        p.append("voice.proseTone must be non-empty")

    return p


# ---------------------------------------------------------------------------------------
# active-theme resolution — stateless, checked fresh on every call
# ---------------------------------------------------------------------------------------


def _pin_from(path):
    try:
        data = json.loads(_read_text(path))
    except Exception:
        return None
    name = data.get("theme")
    if isinstance(name, str) and _NAME_RE.match(name):
        return name
    return None


def pin_paths():
    """Project pin first, then the machine-wide one. Order is the resolution order."""
    home = os.path.expanduser("~")
    return [
        os.path.join(os.getcwd(), ".claude", "style.json"),
        os.path.join(home, ".claude", "house-style", "active.json"),
    ]


def resolve_theme():
    """Return (theme_dict, name, origin). Never raises; always yields a usable theme."""
    for path in pin_paths():
        name = _pin_from(path)
        if name:
            try:
                return load_theme(name), name, path
            except Exception:
                # A pin naming a theme that no longer exists is a stale pin, not a crash.
                continue
    try:
        return load_theme(FALLBACK), FALLBACK, "fallback"
    except Exception:
        return None, None, "none"


# ---------------------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------------------


def scale_steps(theme):
    """Derive --step--1 .. --step-4 from base and ratio.

    Derived, never stored: a stored ladder drifts from its own ratio the first time somebody
    nudges one number.
    """
    ratio = float(theme["scale"]["ratio"])
    out = []
    for step in range(-1, 5):
        out.append((f"--step-{'-1' if step == -1 else step}", round(ratio ** step, 4)))
    return out


def font_url(theme, system=False):
    """One combined Google Fonts URL for the whole theme, or '' in system-only mode."""
    if system:
        return ""
    families = []
    for role in FONT_ROLES:
        f = theme["fonts"][role]
        url = f["googleFontsUrl"]
        m = re.search(r"[?&]family=([^&]+)", url)
        if m:
            families.append(m.group(1))
    if not families:
        return ""
    return "https://fonts.googleapis.com/css2?" + "&".join(
        "family=" + f for f in families
    ) + "&display=swap"


def render_css(theme, system=False):
    """Emit the token block: bare :root for light, dark repeated under both the media query
    and the explicit [data-theme] selector so the viewer's choice wins in both directions."""
    name = theme["name"]
    stack_key = "systemStack" if system else "stack"
    light, dark = theme["colour"]["light"], theme["colour"]["dark"]
    L = []
    L.append(f"/* {MARKER_PREFIX} {name} */")
    url = font_url(theme, system)
    if url:
        L.append(f"@import url('{url}');")
    L.append(":root {")
    L.append("  color-scheme: light dark;")
    for role in FONT_ROLES:
        L.append(f"  --font-{role}: {theme['fonts'][role][stack_key]};")
    L.append(f"  --base: {theme['scale']['base']};")
    L.append(f"  --line-height: {theme['scale']['lineHeight']};")
    for var, val in scale_steps(theme):
        L.append(f"  {var}: {val}rem;")
    for k in SHAPE_KEYS:
        L.append(f"  --{k}: {theme['shape'][k]};")
    for t in COLOUR_TOKENS:
        L.append(f"  --{t}: {light[t]};")
    L.append("}")
    dark_block = "\n".join(f"    --{t}: {dark[t]};" for t in COLOUR_TOKENS)
    L.append("@media (prefers-color-scheme: dark) {")
    L.append('  :root:not([data-theme="light"]) {')
    L.append(dark_block)
    L.append("  }")
    L.append("}")
    L.append(':root[data-theme="dark"] {')
    L.append("\n".join(f"  --{t}: {dark[t]};" for t in COLOUR_TOKENS))
    L.append("}")
    L.append(':root[data-theme="light"] {')
    L.append("\n".join(f"  --{t}: {light[t]};" for t in COLOUR_TOKENS))
    L.append("}")
    return "\n".join(L) + "\n"


def summarise(theme):
    """The compact block injected at SessionStart. Kept short deliberately - it is re-paid on
    every session and on every subagent spawn, so it names the theme and its decisions and
    points at the file for anything more."""
    v, s, sh = theme["voice"], theme["scale"], theme["shape"]
    f = theme["fonts"]
    return (
        f"Active house style: {theme['label']} ({theme['name']}) - {theme['summary']}\n"
        f"  Fonts   display {f['display']['family']} / body {f['body']['family']} / "
        f"mono {f['mono']['family']}\n"
        f"  Colour  accent {theme['colour'][theme['defaultScheme']]['accent']}, "
        f"authored {theme['defaultScheme']}-first\n"
        f"  Shape   radius {sh['radius']}, border {sh['border']}, measure {sh['measure']}, "
        f"scale {s['base']}/{s['ratio']}\n"
        f"  Voice   {v['density']}, prefers {v['prefer']}, "
        f"eyebrow {'yes' if v['useEyebrow'] else 'no'}, lede {'yes' if v['useLede'] else 'no'}\n"
        f"  Write like this: {v['proseTone']}"
    )


# ---------------------------------------------------------------------------------------
# style — SessionStart. Fails loud, not closed: there is nothing to block, but an unstyled
# session that nobody was told about is worse than a noisy one.
# ---------------------------------------------------------------------------------------

STYLE_RULE = (
    "House style, authorship: before you build anything visual - an artifact, an HTML page, "
    "an SVG, a chart, a slide - name the active theme in one line and offer the other two as "
    "alternates, then build in whichever the user picks. Do not invent a palette or pick a "
    "font that is not in the active theme. Render the theme's tokens into the page and stamp "
    "the marker comment /* house-style: <name> */ so the publish check knows the page was "
    "styled deliberately. Write the page's prose in the theme's voice, not only its colours."
)


def event_style():
    try:
        theme, name, origin = resolve_theme()
        if theme is None:
            emit({
                "systemMessage": "house-style plugin: no theme could be loaded. Artifacts "
                                 "will be built unstyled this session."
            })
            return 0
        others = [n for n in all_theme_names() if n != name]
        text = (
            summarise(theme)
            + f"\n  Also available: {', '.join(others) if others else '(none)'}"
            + f"\n  Pinned by: {origin}\n\n"
            + STYLE_RULE
        )
        emit({
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": text,
            }
        })
    except Exception:
        emit({
            "systemMessage": "house-style plugin: internal error. No house style was loaded "
                             "into this session."
        })
    return 0


# ---------------------------------------------------------------------------------------
# styleguard — PreToolUse on Artifact. Fails closed: this is the last moment before a page
# goes public, and an unreadable payload is not a reason to wave it past.
# ---------------------------------------------------------------------------------------

_FILE_PATH_RE = re.compile(r'"file_path"\s*:\s*"([^"]*)"')
_VISUAL_EXT_RE = re.compile(r"\.(html?|svg|css)$", re.IGNORECASE)


def _extract_file_path(payload):
    m = _FILE_PATH_RE.search(payload)
    return m.group(1) if m else None


def marker_in(text):
    m = _MARKER_RE.search(text)
    return m.group(1) if m else None


def event_styleguard():
    try:
        payload = read_payload()
    except Exception:
        sys.stderr.write("house-style styleguard: could not read the hook payload from stdin.\n")
        sys.stderr.write("Blocking this publish rather than shipping an unchecked page.\n")
        return 2

    if not payload:
        return 0

    try:
        # The same three-tier ladder guard uses, for the same reason. Tier 1: the payload
        # parses and names a file - judge that file. Tier 2: it does not parse, but a
        # file_path can still be pulled out of it - judge that, exactly as this hook behaved
        # before the parse existed. Tier 3: neither - we were asked to check a publish and
        # cannot tell what is being published, so block rather than wave it through. The
        # middle tier is what stops a payload whose shape shifts slightly from being either
        # ignored or blocked outright.
        file_path = None
        parsed = None
        try:
            parsed = json.loads(payload)
        except Exception:
            parsed = None
        if isinstance(parsed, dict):
            ti = parsed.get("tool_input")
            if isinstance(ti, dict):
                file_path = ti.get("file_path") or ti.get("url")
            if not file_path:
                file_path = parsed.get("file_path")
            # A parsed payload naming no file is an Artifact action that is not a publish -
            # a list, a read, a comment. There is no page to judge and prompting is noise.
            if not file_path:
                return 0
        else:
            file_path = _extract_file_path(payload)
            if not file_path:
                sys.stderr.write(
                    "house-style styleguard: the hook payload could not be parsed and names "
                    "no file. Blocking rather than publishing an unchecked page.\n"
                )
                return 2
        if not isinstance(file_path, str) or not file_path:
            return 0
        base = re.split(r"[\\/]", file_path)[-1]
        if not _VISUAL_EXT_RE.search(base):
            return 0
        try:
            body = _read_text(file_path)
        except Exception:
            # The publish names a file we cannot read. Say so and let the user decide.
            emit({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": (
                        f"house-style: about to publish {base}, but the file could not be read "
                        "to check it carries a house theme."
                    ),
                }
            })
            return 0

        stamped = marker_in(body)
        theme, name, _origin = resolve_theme()
        known = all_theme_names()

        # Silent when compliant. A hook that fires on a correct publish cannot end quietly -
        # the turn continues and the only thing left to say is that nothing needed saying,
        # which is the house rule against announcing your own compliance, broken by the hook
        # that enforces it. Same trade the handover hook already makes.
        if stamped and stamped in known:
            return 0

        others = [n for n in known if n != name][:2]
        alt = ", ".join(others) if others else "(no alternates)"
        if stamped:
            why = f"it is stamped with an unknown theme ({stamped})"
        else:
            why = "it carries no house-style marker"
        emit({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": (
                    f"house-style: {base} is about to be published and {why}, so it was not "
                    f"built from a house theme.\n\n"
                    f"  Active theme: {name or 'none'}"
                    + (f" - {theme['summary']}" if theme else "")
                    + f"\n  Alternates:   {alt}\n\n"
                    "Approve to publish it as-is, or reject and Claude will rebuild it on a "
                    "theme you choose."
                ),
            }
        })
        return 0
    except Exception:
        sys.stderr.write(
            "house-style styleguard: internal error, blocking rather than publishing an "
            "unchecked page.\n"
        )
        return 2


# ---------------------------------------------------------------------------------------
# styled — PostToolUse on Write. Never obstructs; the write already happened.
# ---------------------------------------------------------------------------------------

STYLED_NOTE = (
    "House style: you just wrote a visual file with no house-style marker. Render the active "
    "theme's tokens into it and stamp the marker comment /* house-style: <name> */, or say why "
    "this file is deliberately unthemed. This is a reminder to you; the user was not prompted "
    "and does not need to do anything."
)

_OUTSIDE_PATTERNS = (
    re.compile(r"[\\/]+\.claude[\\/]+plans[\\/]+", re.IGNORECASE),
    re.compile(r"AppData[\\/]+Local[\\/]+Temp[\\/]+", re.IGNORECASE),
    re.compile(r'(^|[\\/:"])(tmp|temp)[\\/]+', re.IGNORECASE),
    re.compile(r"scratchpad", re.IGNORECASE),
)


def event_styled():
    try:
        payload = read_payload()
        if not payload:
            return 0
        file_path = _extract_file_path(payload)
        if not file_path:
            return 0
        base = re.split(r"[\\/]", file_path)[-1]
        if not _VISUAL_EXT_RE.search(base):
            return 0
        # Scratch pages are not deliverables; house-rules' artifact hook already owns the
        # question of whether they should be in the project at all.
        if any(p.search(file_path) for p in _OUTSIDE_PATTERNS):
            return 0
        try:
            body = _read_text(file_path)
        except Exception:
            return 0
        if marker_in(body):
            return 0
        emit({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": STYLED_NOTE,
            }
        })
    except Exception:
        emit({
            "systemMessage": "house-style plugin: the theming reminder hit an error and is "
                             "offline for this call."
        })
    return 0


# ---------------------------------------------------------------------------------------
# the live catalogue — fetched here, in Python, never by the page
#
# An artifact runs under a CSP that blocks fetch/XHR to every host without exception, so a
# gallery page cannot call these APIs itself. Fetching happens at command time and the result
# is inlined into the page this file generates. Everything below falls through cache to the
# three shipped themes and never raises: a catalogue is an expansion, not a dependency.
# ---------------------------------------------------------------------------------------

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".claude", "house-style", "cache")

SOURCES = {
    "fonts": (
        "https://api.fontsource.org/v1/fonts",
        "Fontsource catalogue (MIT); fonts themselves OFL/Apache/UFL",
    ),
    "opencolor": (
        "https://raw.githubusercontent.com/yeun/open-color/master/open-color.json",
        "Open Color (MIT)",
    ),
    "schemes": (
        "https://raw.githubusercontent.com/tinted-theming/schemes/spec-0.11/base16/nord.yaml",
        "tinted-theming schemes (MIT)",
    ),
}


def _cache_file(key):
    return os.path.join(CACHE_DIR, key + ".json")


def fetch(key, timeout=10):
    """Fetch one source, cache it, and return (data, origin).

    origin is 'network', 'cache' or 'unavailable'. Never raises - a catalogue that cannot be
    reached must degrade to the shipped themes, not take the command down with it.
    """
    url, _licence = SOURCES[key]
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "house-style/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
        try:
            data = json.loads(raw)
        except Exception:
            data = {"raw": raw}
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(_cache_file(key), "w", encoding="utf-8") as f:
                json.dump({"fetched": _now(), "url": url, "data": data}, f)
        except Exception:
            pass  # an uncacheable fetch is still a good fetch
        return data, "network"
    except Exception:
        pass
    try:
        with open(_cache_file(key), "r", encoding="utf-8") as f:
            return json.load(f).get("data"), "cache"
    except Exception:
        return None, "unavailable"


def _now():
    import datetime
    return datetime.datetime.now().isoformat(timespec="seconds")


def catalogue(timeout=10):
    """Everything the gallery knows about, shipped themes first.

    The shipped three are always present and always first. Fetched material is offered
    alongside them as raw ingredients - font families that pair with each theme's category -
    rather than as auto-composed themes, because a theme is a set of decisions and a
    generator that guesses at them produces near-misses nobody wants to pick.
    """
    shipped = []
    for n in all_theme_names():
        try:
            t = load_theme(n)
            if not validate(t, n):
                shipped.append(t)
        except Exception:
            continue
    fonts, forigin = fetch("fonts", timeout)
    families = []
    if isinstance(fonts, list):
        for f in fonts:
            try:
                if "latin" in (f.get("subsets") or []) and f.get("category"):
                    families.append({
                        "family": f["family"],
                        "category": f["category"],
                        "variable": bool(f.get("variable")),
                    })
            except Exception:
                continue
    return {
        "themes": shipped,
        "families": families,
        "familiesOrigin": forigin,
        "generated": _now(),
    }


# ---------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------


def cmd_list(argv):
    theme, active, _origin = resolve_theme()
    names = all_theme_names()
    if not names:
        print("No themes found.")
        return 1
    print()
    print(f"{'':2} {'NAME':10} {'BODY FONT':16} {'ACCENT':9} {'VOICE':10} FOR")
    for n in names:
        try:
            t = load_theme(n)
        except Exception:
            print(f"   {n:10} (unreadable)")
            continue
        mark = "*" if n == active else " "
        print(
            f" {mark} {t['name']:10} {t['fonts']['body']['family']:16} "
            f"{t['colour'][t['defaultScheme']]['accent']:9} {t['voice']['density']:10} {t['for']}"
        )
    print()
    print(f"  * = active.  Pin one with:  /house-style use <name>")
    print()
    return 0


def cmd_show(argv):
    name = argv[0] if argv else None
    if name:
        try:
            theme = load_theme(name)
        except Exception:
            print(f"No such theme: {name}", file=sys.stderr)
            return 1
        origin = "explicit"
    else:
        theme, name, origin = resolve_theme()
        if theme is None:
            print("No theme could be loaded.", file=sys.stderr)
            return 1
    print()
    print(summarise(theme))
    print()
    print(f"  Source of truth: {theme_path(theme['name'])}  (selected via {origin})")
    print()
    return 0


def cmd_css(argv):
    system = "--system" in argv
    rest = [a for a in argv if not a.startswith("-")]
    if rest:
        try:
            theme = load_theme(rest[0])
        except Exception:
            print(f"No such theme: {rest[0]}", file=sys.stderr)
            return 1
    else:
        theme, _n, _o = resolve_theme()
        if theme is None:
            print("No theme could be loaded.", file=sys.stderr)
            return 1
    sys.stdout.write(render_css(theme, system=system))
    return 0


def cmd_use(argv):
    if not argv:
        print("Usage: style.py use <name> [--global]", file=sys.stderr)
        return 1
    name = argv[0]
    if name not in all_theme_names():
        print(f"No such theme: {name}. Try: {', '.join(all_theme_names())}", file=sys.stderr)
        return 1
    is_global = "--global" in argv
    path = pin_paths()[1] if is_global else pin_paths()[0]
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"theme": name}, f, indent=2)
            f.write("\n")
    except Exception as e:
        print(f"Could not write the pin at {path}: {e}", file=sys.stderr)
        return 1
    scope = "this machine" if is_global else "this project"
    print(f"Active house style for {scope} is now {name}.")
    print(f"  Pin written to {path}")
    return 0


def cmd_validate(argv):
    names = argv or all_theme_names()
    bad = 0
    for n in names:
        try:
            t = load_theme(n)
        except Exception as e:
            print(f"FAIL  {n}: unreadable ({e})")
            bad += 1
            continue
        problems = validate(t, n)
        if problems:
            bad += 1
            print(f"FAIL  {n}")
            for p in problems:
                print(f"        {p}")
        else:
            print(f"PASS  {n}")
    print()
    print(f"{len(names) - bad}/{len(names)} themes valid.")
    return 1 if bad else 0


def cmd_refresh(argv):
    ok = True
    for key in SOURCES:
        data, origin = fetch(key)
        _url, licence = SOURCES[key]
        n = len(data) if isinstance(data, (list, dict)) else 0
        print(f"  {key:10} {origin:12} {n:5} entries   {licence}")
        if origin == "unavailable":
            ok = False
    print()
    print(f"  Cache: {CACHE_DIR}")
    if not ok:
        # Deliberately still exit 0. Offline is a normal state, and the three shipped themes
        # are unaffected by it.
        print("  Some sources were unreachable. The shipped themes are unaffected.")
    return 0


def cmd_catalogue(argv):
    """Emit the JSON the gallery page inlines. Printed, not fetched by the page."""
    sys.stdout.write(json.dumps(catalogue(), separators=(",", ":")))
    return 0


# ---------------------------------------------------------------------------------------
# gallery — the visual picker, generated here and published as an artifact
# ---------------------------------------------------------------------------------------


def _esc(t):
    return (
        str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _scoped_tokens(theme, scheme):
    """The theme's tokens as a flat declaration list, for scoping to one specimen."""
    c = theme["colour"][scheme]
    L = []
    for role in FONT_ROLES:
        L.append(f"--font-{role}: {theme['fonts'][role]['stack']};")
    L.append(f"--base: {theme['scale']['base']};")
    L.append(f"--line-height: {theme['scale']['lineHeight']};")
    for var, val in scale_steps(theme):
        L.append(f"{var}: {val}rem;")
    for k in SHAPE_KEYS:
        L.append(f"--{k}: {theme['shape'][k]};")
    for t in COLOUR_TOKENS:
        L.append(f"--{t}: {c[t]};")
    return "\n    ".join(L)


def _specimen_body(theme):
    """What each theme is shown saying. The prose is the theme's own proseTone rendered in
    its own body face, so the voice and the typeface are judged together - a specimen that
    showed the same lorem under three fonts would hide exactly the half that matters."""
    v = theme["voice"]
    name = theme["name"]
    parts = []
    if v["useEyebrow"]:
        parts.append(f'<p class="eyebrow">{_esc(theme["for"].split(",")[0])}</p>')
    parts.append(f'<h2>{_esc(theme["label"])}</h2>')
    if v["useLede"]:
        parts.append(f'<p class="sub">{_esc(theme["summary"])}</p>')
    parts.append(f'<p>{_esc(v["proseTone"])}</p>')

    if v["prefer"] == "table":
        rows = "".join(
            f"<tr><td>{_esc(k)}</td><td><code>{_esc(val)}</code></td></tr>"
            for k, val in (
                ("radius", theme["shape"]["radius"]),
                ("border", theme["shape"]["border"]),
                ("measure", theme["shape"]["measure"]),
                ("scale", f"{theme['scale']['base']} / {theme['scale']['ratio']}"),
            )
        )
        parts.append(
            '<div class="scroll-x"><table><thead><tr><th>Token</th><th>Value</th></tr>'
            f"</thead><tbody>{rows}</tbody></table></div>"
        )
    else:
        parts.append(
            f'<div class="card"><span class="pill">{_esc(theme["voice"]["density"])}</span>'
            f'<p style="margin:.7rem 0 0">{_esc(theme["for"])}</p></div>'
        )

    parts.append(
        f"<pre><code>python style.py use {_esc(name)}</code></pre>"
    )
    parts.append(
        '<p class="warn">Warning styling, shown so the whole token set is visible rather '
        "than only the parts a happy page uses.</p>"
    )
    sw = "".join(
        f'<li style="background:var(--{t})">{_esc(t)}</li>' for t in COLOUR_TOKENS
    )
    parts.append(f'<ul class="swatches">{sw}</ul>')
    return "\n      ".join(parts)


def render_gallery(cat):
    """Fill templates/gallery.html from a catalogue dict. Pure string work - no network."""
    shell = _read_text(os.path.join(TEMPLATES_DIR, "gallery.html"))
    themes = cat["themes"]

    css, cards = [], []
    for t in themes:
        n = t["name"]
        css.append(
            f'#stage-{n}[data-scheme="light"] {{\n    ' + _scoped_tokens(t, "light") + "\n  }"
        )
        css.append(
            f'#stage-{n}[data-scheme="dark"] {{\n    ' + _scoped_tokens(t, "dark") + "\n  }"
        )
        other = t["defaultScheme"]
        cards.append(
            f'  <section class="specimen">\n'
            f'    <div class="bar">\n'
            f'      <span class="nm">{_esc(t["label"])}</span>\n'
            f'      <span>{_esc(t["fonts"]["display"]["family"])} / '
            f'{_esc(t["fonts"]["body"]["family"])} / {_esc(t["fonts"]["mono"]["family"])}</span>\n'
            f'      <span class="sp"></span>\n'
            f'      <button data-scheme-toggle="{n}">{other}</button>\n'
            f'      <button class="pick" data-pick="{n}" aria-pressed="false">Use this</button>\n'
            f'    </div>\n'
            f'    <div class="stage" id="stage-{n}" data-scheme="{other}">\n'
            f'      <div class="inner">\n      {_specimen_body(t)}\n      </div>\n'
            f'    </div>\n'
            f'    <p id="said-{n}" class="note" hidden></p>\n'
            f'    <p class="note">Pin it with <code>/house-style use {n}</code>.</p>\n'
            f'  </section>'
        )

    fonts = []
    for t in themes:
        m = re.search(r"[?&]family=([^&]+)", font_url(t) or "")
        for role in FONT_ROLES:
            mm = re.search(r"[?&]family=([^&]+)", t["fonts"][role]["googleFontsUrl"])
            if mm and mm.group(1) not in fonts:
                fonts.append(mm.group(1))
    fonts_url = "https://fonts.googleapis.com/css2?" + "&".join(
        "family=" + f for f in fonts
    ) + "&display=swap"

    fam_n = len(cat.get("families") or [])
    origin = cat.get("familiesOrigin", "unavailable")
    meta = (
        f"Generated {cat['generated']}. {len(themes)} shipped themes. "
        f"Font catalogue: {fam_n} latin families from Fontsource ({origin}); "
        "fonts served from fonts.googleapis.com, the only stylesheet host an artifact may load."
    )

    data = json.dumps(
        {
            "themes": [
                {"name": t["name"], "label": t["label"], "summary": t["summary"]}
                for t in themes
            ],
            "generated": cat["generated"],
        },
        separators=(",", ":"),
    )

    out = shell
    out = out.replace("__TITLE__", "House Style")
    out = out.replace("__FONTS__", fonts_url)
    out = out.replace("__CARDS__", "\n".join(cards))
    out = out.replace("__META__", _esc(meta))
    out = out.replace("__DATA__", data)
    # The scoped per-theme token blocks go in just before the closing </style>.
    out = out.replace("</style>", "  " + "\n  ".join(css) + "\n</style>", 1)
    return out


def cmd_gallery(argv):
    positional = [a for a in argv if not a.startswith("-")]
    out = positional[0] if positional else "house-style-gallery.html"
    timeout = 0 if "--offline" in argv else 10
    cat = catalogue(timeout) if timeout else {
        "themes": [load_theme(n) for n in all_theme_names()],
        "families": [], "familiesOrigin": "skipped", "generated": _now(),
    }
    html = render_gallery(cat)
    try:
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(html)
    except Exception as e:
        print(f"Could not write {out}: {e}", file=sys.stderr)
        return 1
    print(f"Gallery written to {out}  ({len(html)} bytes, {len(cat['themes'])} themes)")
    print(f"  Font catalogue: {len(cat.get('families') or [])} families "
          f"({cat.get('familiesOrigin')})")
    print("  Publish it with the Artifact tool, capabilities {\"db\":{}}, dropping the")
    print("  <!doctype>/<html>/<head>/<body> wrappers. Then read choice/active for the pick.")
    return 0

COMMANDS = {
    "list": cmd_list,
    "show": cmd_show,
    "css": cmd_css,
    "use": cmd_use,
    "validate": cmd_validate,
    "refresh": cmd_refresh,
    "catalogue": cmd_catalogue,
    "gallery": cmd_gallery,
}

EVENTS = {
    "style": event_style,
    "styleguard": event_styleguard,
    "styled": event_styled,
}


def main(argv):
    word = argv[1] if len(argv) > 1 else ""
    handler = EVENTS.get(word)
    if handler is not None:
        try:
            return handler()
        except BaseException:
            # Last-resort net. Each handler already fails per its own event's contract; this
            # catches what escapes them, and it branches the same way.
            if word == "styleguard":
                sys.stderr.write(
                    "house-style styleguard: internal error, blocking rather than publishing "
                    "an unchecked page.\n"
                )
                return 2
            if word == "style":
                emit({
                    "systemMessage": "house-style plugin: internal error. No house style was "
                                     "loaded into this session."
                })
            return 0
    cmd = COMMANDS.get(word)
    if cmd is None:
        # Exit 0, not 1. Hook events and CLI subcommands share this one namespace, and the
        # dispatcher cannot tell which kind of caller it has. A renamed or mistyped hook event
        # exiting non-zero would be read as a hook failure - on PreToolUse that is a blocked
        # tool call for a typo. A human still sees the usage line on stderr, and the failures
        # that matter for scripting (`use` with an unknown theme, `validate` with a broken
        # theme) keep their non-zero exits.
        print(__doc__.strip().splitlines()[0], file=sys.stderr)
        print(f"Usage: style.py <{'|'.join(COMMANDS)}>", file=sys.stderr)
        return 0
    return cmd(argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
