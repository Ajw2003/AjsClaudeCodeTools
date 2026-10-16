#!/usr/bin/env python3
"""Draws the three audit diagrams as SVG files next to this script, in diagrams/.

    python3 docs/audits/2026-10-16-plugin-audit/make_diagrams.py

The numbers are the ones counted in the five findings files in this folder; change them here and
rerun if a recount changes them. Each SVG carries its own light and dark colours, so it reads in
both themes when shown through an <img> tag.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "diagrams")

STYLE = """<style>
  .bg{fill:#ffffff} .ink{fill:#1f2328} .mute{fill:#59636e} .line{stroke:#8c959f}
  .box{fill:#f6f8fa;stroke:#8c959f} .hot{fill:#ffebe9;stroke:#cf222e} .warm{fill:#fff8c5;stroke:#9a6700}
  .cool{fill:#ddf4ff;stroke:#0969da} .ok{fill:#dafbe1;stroke:#1a7f37} .bar{fill:#cf222e} .bar2{fill:#9a6700}
  text{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif}
  @media (prefers-color-scheme: dark){
    .bg{fill:#0d1117} .ink{fill:#e6edf3} .mute{fill:#9198a1} .line{stroke:#6e7681}
    .box{fill:#161b22;stroke:#6e7681} .hot{fill:#3c1618;stroke:#f85149} .warm{fill:#2e2a12;stroke:#d29922}
    .cool{fill:#0c2d4a;stroke:#4493f8} .ok{fill:#0f2e1a;stroke:#3fb950} .bar{fill:#f85149} .bar2{fill:#d29922}
  }
</style>"""


def svg(w, h, body, title):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" role="img" aria-label="%s">%s'
            '<rect class="bg" width="%d" height="%d"/>%s</svg>\n' % (w, h, title, STYLE, w, h, body))


def text(x, y, s, cls="ink", size=14, anchor="start", weight="normal"):
    s = s.replace("&", "&amp;").replace("<", "&lt;")
    return ('<text x="%d" y="%d" class="%s" font-size="%d" text-anchor="%s" font-weight="%s">%s</text>'
            % (x, y, cls, size, anchor, weight, s))


def box(x, y, w, h, cls="box"):
    return '<rect x="%d" y="%d" width="%d" height="%d" rx="8" class="%s" stroke-width="1.5"/>' % (x, y, w, h, cls)


def today():
    """Where the plugin's 30 entry points sit today: one file, state spread over five places."""
    events = [
        ("SessionStart", 7, "inject, showrule, profile, standards, docstiers, versioncheck, issuelist"),
        ("UserPromptSubmit", 3, "scope, userpromptaudit, worktreesweep"),
        ("PreToolUse", 6, "guard, guardwrite, guardgithub, agentcap, commitgate, pagecheck"),
        ("PostToolUse", 8, "artifact, branchnudge, runnable, harvest, delegate, audit, autosave, promptran"),
        ("Stop", 1, "handover (8 checkpoint rows)"),
        ("Subagent start / stop", 4, "announce, subagentrules, verdict, subagentcommit"),
        ("Permission / failure", 2, "prompttimer, promptran"),
    ]
    b = text(20, 32, "Today: 30 entry points, one 8,365-line file, state in five places", size=18, weight="bold")
    y = 60
    for name, n, members in events:
        b += box(20, y, 520, 44)
        b += text(32, y + 19, "%s (%d)" % (name, n), size=14, weight="bold")
        b += text(32, y + 36, members, "mute", 11)
        b += '<line x1="540" y1="%d" x2="600" y2="230" class="line" stroke-width="1.2"/>' % (y + 22)
        y += 52
    b += box(600, 180, 150, 100, "hot")
    b += text(675, 215, "hook.py", size=16, anchor="middle", weight="bold")
    b += text(675, 236, "8,365 lines", "mute", 12, "middle")
    b += text(675, 254, "284 functions", "mute", 12, "middle")
    b += text(675, 272, "35 on/off switches", "mute", 12, "middle")
    stores = [
        ("Temp folder", "outdated marker, asked keys, page blocks"),
        (".git folder", "issues, autosave, waiting list, agents"),
        ("repo .claude/", "design-loop stage file"),
        ("~/.claude", "installed plugins, memory"),
        ("GitHub", "issues, labels, version, autosave refs"),
    ]
    y = 70
    for name, what in stores:
        b += '<line x1="750" y1="230" x2="800" y2="%d" class="line" stroke-width="1.2"/>' % (y + 20)
        b += box(800, y, 280, 44, "warm")
        b += text(812, y + 19, name, size=13, weight="bold")
        b += text(812, y + 36, what, "mute", 11)
        y += 58
    b += text(20, 448, "Tested by verify.py: 9,747 lines, 832 checks, each one starts hook.py as its own process.",
              "mute", 13)
    return svg(1100, 470, b, "Today's plugin structure")


def contradictions():
    """Counted findings per kind, from the five findings files."""
    rows = [
        ("Rule against rule", 28, "bar"),
        ("Doc against code", 20, "bar"),
        ("Code logic against code logic", 15, "bar"),
        ("Doc against doc", 8, "bar"),
        ("Script against script", 3, "bar"),
        ("Stale file:line citations", 10, "bar2"),
        ("Duplicated rule text", 9, "bar2"),
        ("Entry points silent without Python", 20, "bar2"),
        ("Shipped lines naming one person (15 files)", 62, "bar2"),
    ]
    scale = 9  # pixels per finding, so the longest bar (62) fits beside its label
    b = text(20, 32, "What the audit found, counted", size=18, weight="bold")
    b += text(20, 52, "Red: one part says the opposite of another. Amber: drift, silence or personal data.", "mute", 12)
    y = 76
    for name, n, cls in rows:
        b += text(20, y + 16, name, size=13)
        b += '<rect x="330" y="%d" width="%d" height="22" rx="3" class="%s"/>' % (y, n * scale, cls)
        b += text(338 + n * scale, y + 16, str(n), size=13, weight="bold")
        y += 34
    return svg(1000, y + 20, b, "Audit findings counted by kind")


def proposed():
    """One shared core, five sub-plugins on top, each optional."""
    b = text(20, 32, "Proposed: a shared core and six optional sub-plugins", size=18, weight="bold")
    b += box(220, 320, 660, 112, "ok")
    b += text(550, 346, "house-rules core", size=16, anchor="middle", weight="bold")
    b += text(550, 368, "project boundaries: which repo each message belongs to, state kept per repo,",
              "mute", 12, "middle")
    b += text(550, 386, "other repos' work becomes an issue there; one config (userConfig), one state store,",
              "mute", 12, "middle")
    b += text(550, 404, "git and transcript helpers, one source per rule; every failure says so", "mute", 12,
              "middle")
    subs = [
        ("Safe git", "guard, overwrite guard,\ncredit check,\nprompt timer"),
        ("Design loop", "stages, approvals,\npages, QA, after-PR\nchecks, visuals"),
        ("Session triage", "clean a transcript,\nthen file issues\nfrom it"),
        ("Writing", "one clarity checker,\neditor helper,\nplain docs"),
        ("Delegation", "helpers, cap,\naudit, worktree\nautosave"),
        ("Docs", "doc tiers, harvest,\ndoc-ref, archivist"),
    ]
    x = 20
    for name, what in subs:
        b += box(x, 90, 166, 130, "cool")
        b += text(x + 83, 118, name, size=15, anchor="middle", weight="bold")
        for i, line in enumerate(what.split("\n")):
            b += text(x + 83, 144 + 18 * i, line, "mute", 12, "middle")
        b += '<line x1="%d" y1="220" x2="%d" y2="320" class="line" stroke-width="1.5"/>' % (x + 83, 260 + (x - 20) * 580 // 900)
        x += 178
    b += text(20, 70, "Each sub-plugin installs on its own and talks to the others only through the core.", "mute", 13)
    b += text(20, 460, "Goes: the self-updater, the hardcoded identity, the old step-card template, text-drift tests.",
              "mute", 13)
    return svg(1100, 480, b, "Proposed plugin structure")


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (("today", today), ("findings", contradictions), ("proposed", proposed)):
        path = os.path.join(OUT, name + ".svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(fn())
        print("wrote", path)


if __name__ == "__main__":
    main()
