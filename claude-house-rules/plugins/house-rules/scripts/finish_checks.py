#!/usr/bin/env python3
"""finish_checks.py - the four finish-line checks of a design-loop feature (#647).

  finish_checks.py docs|pictures|tests|qa FEATURE

Exit 0 = pass, 1 = fail (the reason is printed), 2 = could not tell. Run from the project root.
docs      CHANGELOG.md and a docs/ page (not docs/qa/ or docs/plans/) changed since the merge base with origin/main
pictures  an image in docs/qa/<folder>/round-N/ (or shots/) newer than the newest changed visual file; or no visual file
          changed and `ledger.py status` says NEXT: done (a reviewer writes that round, never the builder)
tests     the plan's test_command from the steps record, 20-minute cap, exits with its code
qa        `acceptance.py check docs/qa/<folder>` exits 0 and the QA page file exists
STDLIB ONLY.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_page import qa_folder  # noqa: E402

IMG = (".png", ".jpg", ".jpeg", ".gif", ".webp")
VISUAL = (".css", ".svg") + IMG
IGNORED = ("docs/qa/", "docs/5-today/")


def run(*cmd):
    return subprocess.run(list(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)


def ignored(p):
    return (p.startswith(IGNORED) or p in ("CHANGELOG.md", ".claude/house-rules-loop.json")
            or p.startswith("docs/plans/"))  # plan-page mock-ups are not the product's visuals


def changed():
    """Changed paths since the merge base with origin/main, plus untracked ones; exits 2 when it cannot tell."""
    mb = run("git", "merge-base", "HEAD", "origin/main")
    if mb.returncode:
        print("could not tell: no merge base with origin/main (%s)" % mb.stderr.strip())
        sys.exit(2)
    out = run("git", "diff", "--name-only", mb.stdout.strip()).stdout.split()
    out += run("git", "ls-files", "-o", "--exclude-standard").stdout.split()
    return sorted(set(out))


def is_visual(p):
    return not ignored(p) and (p.endswith(VISUAL) or (p.endswith(".html") and not p.startswith("docs/")))


def main(argv):
    if len(argv) != 2 or argv[0] not in ("docs", "pictures", "tests", "qa"):
        print("usage: finish_checks.py docs|pictures|tests|qa FEATURE")
        return 2
    which, feature = argv
    folder = os.path.join("docs", "qa", qa_folder(feature))
    if which == "docs":
        files = changed()
        pages = [p for p in files if p.startswith("docs/") and not p.startswith(("docs/qa/", "docs/plans/"))]
        ok = "CHANGELOG.md" in files and bool(pages)
        print("docs: CHANGELOG.md %s, docs pages changed: %s" % ("changed" if "CHANGELOG.md" in files else "NOT changed",
                                                                  ", ".join(pages) or "none"))
        return 0 if ok else 1
    if which == "pictures":
        vis = [p for p in changed() if is_visual(p) and os.path.isfile(p)]
        if not vis:
            r = run(sys.executable, os.path.join(HERE, "ledger.py"), "status", folder)
            if "NEXT: done" in r.stdout:
                print("pictures: no visual file changed and the ledger says NEXT: done")
                return 0
            print("pictures: no visual file changed, but the ledger does not say NEXT: done:\n" + r.stdout + r.stderr)
            return 1
        newest = max(os.path.getmtime(p) for p in vis)
        # shots/ is the old name; visual-loop writes round-N/ (and before/), so a shot is an image in either
        dirs = [os.path.join(folder, d) for d in (sorted(os.listdir(folder)) if os.path.isdir(folder) else [])
                if d == "shots" or d.startswith("round-")]
        new = [f for d in dirs if os.path.isdir(d) for f in os.listdir(d)
               if f.lower().endswith(IMG) and os.path.getmtime(os.path.join(d, f)) > newest]
        print("pictures: %d shot(s) newer than the newest changed visual file (%s)" % (len(new), max(vis, key=os.path.getmtime)))
        return 0 if new else 1
    if which == "tests":
        sys.path.insert(0, HERE)
        import ledger_note
        p, rec = ledger_note._find_rec(feature)
        if p is None:
            print("could not tell: " + rec)
            return 2
        cmd = rec.get("test_command") or ""
        if not cmd.strip():
            print("could not tell: the steps record has no test_command")
            return 2
        try:
            return subprocess.run(cmd, shell=True, timeout=1200).returncode
        except subprocess.TimeoutExpired:
            print("tests: test_command passed the 20-minute cap")
            return 1
    r = run(sys.executable, os.path.join(HERE, "acceptance.py"), "check", folder)
    try:  # make_page.py records the built QA page in the stage file (record_qa_page)
        with open(os.path.join(".claude", "house-rules-loop.json"), encoding="utf-8") as f:
            page = json.load(f).get("qa_page")
    except (OSError, ValueError):
        page = None
    page = page if page and os.path.isfile(page) else None
    print("qa: acceptance check exit %d, QA page %s" % (r.returncode, page or "missing") + (("\n" + r.stdout + r.stderr) if r.returncode else ""))
    return 0 if r.returncode == 0 and page else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
