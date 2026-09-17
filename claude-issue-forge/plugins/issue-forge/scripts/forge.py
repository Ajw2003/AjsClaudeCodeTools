#!/usr/bin/env python3
"""forge.py — the scan/draft/create engine behind the issue-forge plugin. STDLIB ONLY.

Always two phases, always in this order, invoked by Claude (or the user via
/issue-forge:forge) - never by the hook:

  Phase A - `--dry-run` (default; read-only against GitHub, no confirmation needed):
    1. Parse each configured backlog file (docs/architecture-backlog.md, docs/rules-backlog.md
       by default) by splitting on "\\n## " and keeping only sections whose text contains a
       "**Status:** open" line. Each kept section is one candidate: title = the heading text,
       body = the section text through the next "---".
    2. Parse each docs/sessions/*.md ledger (skipping -brief.md companions) for its
       "## Actions taken after the visible reply" table; a non-empty table is ONE candidate per
       ledger (not one per row), titled "Review N action(s) taken after the visible reply —
       session <id>".
    3. For each candidate, compute a stable slug from its source file + heading, then check
       `gh issue list --repo <owner/repo> --state all --search "issue-forge:source=<slug>"` to
       skip anything already forged. That search string embedded in the issue body is the whole
       dedup mechanism - no local state file to go stale.
    4. Print surviving candidates as a numbered list (title, proposed labels, drafted body) for
       Claude to show the user in chat.

  Phase B - `--create <slug1,slug2,...>` (only ever run after the user names which ones, in
    chat - see rules/issue-forge.md's hard rule): runs `gh issue create` once per named slug.

See rules/issue-forge.md for the confirmation rule this file's two-phase split exists to enforce,
and docs/offshoots-plan.md at the repo root for the plan this was built against.
"""

import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

DEFAULT_BACKLOG_FILES = ("docs/architecture-backlog.md", "docs/rules-backlog.md")
DEFAULT_SESSIONS_DIR = "docs/sessions"

_STATUS_RE = re.compile(r"\*\*Status:\*\*\s*open(?:,\s*`([a-z][a-z -]*)`)?", re.IGNORECASE)
_LABEL_PARA_RE = re.compile(
    r"\*\*([A-Za-z][A-Za-z /'-]*?)\.\*\*\s*(.*?)(?=\n\*\*[A-Za-z][A-Za-z /'-]*?\.\*\*|\Z)",
    re.DOTALL,
)

_STRENGTH_LABELS = {
    "strong": "strength:strong",
    "worth-exploring": "strength:worth-exploring",
    "worth exploring": "strength:worth-exploring",
    "speculative": "strength:speculative",
}


class Candidate(object):
    def __init__(self, source, heading, title, body, labels, kind):
        self.source = source
        self.heading = heading
        self.title = title
        self.body = body
        self.labels = labels
        self.kind = kind  # "architecture-backlog" | "rules-backlog" | "session-ledger"
        self.slug = make_slug(source, heading)

    def issue_title(self):
        return self.title

    def issue_body(self):
        return render_body(self)


def make_slug(source, heading):
    base = os.path.basename(source)
    base = re.sub(r"\.[a-z0-9]+$", "", base, flags=re.IGNORECASE)
    heading_slug = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")
    slug = re.sub(r"[^a-z0-9]+", "-", (base + "-" + heading_slug).lower()).strip("-")
    return slug[:80]


def _labeled_paragraphs(text):
    """Map bold-labeled paragraph markers ("**The friction.** ...") to their body text."""
    out = {}
    for m in _LABEL_PARA_RE.finditer(text):
        label = m.group(1).strip().lower()
        out[label] = m.group(2).strip()
    return out


def _backlog_label_for(kind):
    return "source:architecture-backlog" if kind == "architecture-backlog" else "source:rules-backlog"


def parse_backlog_file(path, text, kind):
    """Split on "\\n## ", keep sections containing "**Status:** open"."""
    candidates = []
    # A leading "\n" is prepended so the very first "## " section (if the file has no preamble
    # before it) still splits the same way as every later one.
    chunks = ("\n" + text).split("\n## ")[1:]
    for chunk in chunks:
        m = _STATUS_RE.search(chunk)
        if not m:
            continue
        lines = chunk.split("\n", 1)
        heading = lines[0].strip()
        rest = lines[1] if len(lines) > 1 else ""
        cut = rest.find("\n---")
        body_text = rest[:cut] if cut != -1 else rest
        body_text = body_text.strip()

        paras = _labeled_paragraphs(body_text)
        friction = paras.get("the friction") or paras.get("the defect") or ""
        evidence = paras.get("evidence") or ""
        proposed = (
            paras.get("what would change")
            or paras.get("what the rule should say")
            or ""
        )

        labels = [_backlog_label_for(kind)]
        strength_key = (m.group(1) or "").strip().lower()
        if strength_key in _STRENGTH_LABELS and kind == "architecture-backlog":
            labels.append(_STRENGTH_LABELS[strength_key])

        candidates.append(
            Candidate(
                source=path,
                heading=heading,
                title=heading,
                body={
                    "context": friction or body_text,
                    "why": evidence,
                    "proposed": proposed,
                },
                labels=labels,
                kind=kind,
            )
        )
    return candidates


_LEDGER_ACTIONS_HEADING = "## Actions taken after the visible reply"
_LEDGER_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-(.+)$")


def parse_ledger_file(path, text):
    """One candidate per ledger, only if its flagged-actions table has data rows."""
    idx = text.find(_LEDGER_ACTIONS_HEADING)
    if idx == -1:
        return []
    rest = text[idx + len(_LEDGER_ACTIONS_HEADING):]
    next_heading = rest.find("\n## ")
    section = rest[:next_heading] if next_heading != -1 else rest

    table_lines = [ln for ln in section.splitlines() if ln.strip().startswith("|")]
    # First table line is the header row, second is the "|---|---|...|" separator; anything
    # after that is a data row. Fewer than 3 lines means no data rows at all.
    data_rows = table_lines[2:] if len(table_lines) > 2 else []
    if not data_rows:
        return []

    base = os.path.basename(path)
    base = re.sub(r"\.md$", "", base, flags=re.IGNORECASE)
    m = _LEDGER_ID_RE.match(base)
    session_id = m.group(1) if m else base

    heading = "session-ledger-actions-%s" % session_id
    title = "Review %d action(s) taken after the visible reply — session %s" % (
        len(data_rows),
        session_id,
    )
    table_text = "\n".join(table_lines[:2] + data_rows)

    return [
        Candidate(
            source=path,
            heading=heading,
            title=title,
            body={
                "context": table_text,
                "why": "",
                "proposed": "review the flagged actions above",
            },
            labels=["source:session-ledger"],
            kind="session-ledger",
        )
    ]


ISSUE_BODY_TEMPLATE = """<!-- issue-forge:source={slug} -->

## Context
{context}

## Why it matters
{why}

## Proposed change / acceptance criteria
- [ ] {proposed}

## Source
- `{source}` — {heading}
"""


def render_body(candidate):
    why = candidate.body["why"] or "(not stated in the source entry)"
    proposed = candidate.body["proposed"] or "review the source entry above"
    return ISSUE_BODY_TEMPLATE.format(
        slug=candidate.slug,
        context=candidate.body["context"] or "(no context extracted from the source entry)",
        why=why,
        proposed=proposed,
        source=candidate.source,
        heading=candidate.heading,
    )


def collect_candidates(backlog_files, sessions_dir, read_file=None, listdir=None):
    read_file = read_file or _read_file
    listdir = listdir or os.listdir

    candidates = []
    for path in backlog_files:
        try:
            text = read_file(path)
        except (IOError, OSError):
            continue
        kind = "rules-backlog" if "rules-backlog" in os.path.basename(path) else "architecture-backlog"
        candidates.extend(parse_backlog_file(path, text, kind))

    try:
        names = sorted(listdir(sessions_dir))
    except (IOError, OSError):
        names = []
    for name in names:
        if not name.endswith(".md") or name.endswith("-brief.md"):
            continue
        path = sessions_dir.rstrip("/\\") + "/" + name
        try:
            text = read_file(path)
        except (IOError, OSError):
            continue
        candidates.extend(parse_ledger_file(path, text))

    return candidates


def _read_file(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


# ---------------------------------------------------------------------------------------
# gh dedup - the whole mechanism is a marker embedded in the issue body, searched for via
# `gh issue list --search`. run_gh is the one seam that shells out, so tests can stub it.
# ---------------------------------------------------------------------------------------


def run_gh(args, gh_cmd="gh"):
    proc = subprocess.run(
        [gh_cmd] + list(args),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode(
        "utf-8", "replace"
    )


def already_forged(slug, repo, gh_cmd="gh", runner=None):
    runner = runner or run_gh
    rc, out, err = runner(
        [
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "all",
            "--search",
            "issue-forge:source=%s" % slug,
            "--json",
            "number",
        ],
        gh_cmd,
    )
    if rc != 0:
        # A dedup check that can't run is not proof of absence - fail toward "treat as not
        # forged yet" is wrong (would duplicate); fail toward "treat as already forged" is also
        # wrong (would hide a real candidate). Surface the failure instead of guessing.
        sys.stderr.write(
            "forge.py: gh issue list failed for slug %s (rc=%s): %s\n" % (slug, rc, err.strip())
        )
        return None
    try:
        data = json.loads(out) if out.strip() else []
    except ValueError:
        sys.stderr.write("forge.py: could not parse gh issue list output for slug %s\n" % slug)
        return None
    return bool(data)


def create_issue(candidate, repo, gh_cmd="gh", runner=None):
    runner = runner or run_gh
    args = [
        "issue",
        "create",
        "--repo",
        repo,
        "--title",
        candidate.issue_title(),
        "--body",
        candidate.issue_body(),
    ]
    for label in candidate.labels:
        args.extend(["--label", label])
    return runner(args, gh_cmd)


# ---------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------


def _default_backlog_files():
    raw = os.environ.get("ISSUE_FORGE_BACKLOG_FILES", "")
    if not raw.strip():
        return list(DEFAULT_BACKLOG_FILES)
    return [p.strip() for p in raw.split(os.pathsep) if p.strip()]


def _detect_repo():
    try:
        proc = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        url = proc.stdout.decode("utf-8", "replace").strip()
    except Exception:
        return None
    m = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$", url)
    return m.group(1) if m else None


def phase_a(args):
    backlog_files = args.backlog_files or _default_backlog_files()
    sessions_dir = args.sessions_dir or DEFAULT_SESSIONS_DIR
    repo = args.repo or _detect_repo()

    candidates = collect_candidates(backlog_files, sessions_dir)

    surviving = []
    for c in candidates:
        if not repo:
            surviving.append(c)
            continue
        forged = already_forged(c.slug, repo, gh_cmd=args.gh)
        if forged:
            continue
        surviving.append(c)

    print("issue-forge: %d candidate(s) found, %d surviving after dedup." % (
        len(candidates), len(surviving)
    ))
    if not repo:
        print("(no --repo given and no origin remote detected - dedup was skipped.)")
    print()
    for i, c in enumerate(surviving, 1):
        print("%d. [%s] %s" % (i, c.slug, c.issue_title()))
        print("   labels: %s" % ", ".join(c.labels))
        print("   ---")
        for line in c.issue_body().splitlines():
            print("   %s" % line)
        print()
    return surviving


def phase_b(args, slugs):
    backlog_files = args.backlog_files or _default_backlog_files()
    sessions_dir = args.sessions_dir or DEFAULT_SESSIONS_DIR
    repo = args.repo or _detect_repo()
    if not repo:
        print("forge.py: --create needs --repo (no origin remote could be detected).")
        return 1

    candidates = {c.slug: c for c in collect_candidates(backlog_files, sessions_dir)}
    wanted = [s.strip() for s in slugs.split(",") if s.strip()]
    unknown = [s for s in wanted if s not in candidates]
    if unknown:
        print("forge.py: unknown slug(s), not creating anything: %s" % ", ".join(unknown))
        return 1

    for slug in wanted:
        c = candidates[slug]
        rc, out, err = create_issue(c, repo, gh_cmd=args.gh)
        if rc == 0:
            print("created %s: %s" % (slug, out.strip()))
        else:
            print("FAILED to create %s: %s" % (slug, err.strip()))
    return 0


def build_parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true", help="Phase A: scan, dedup, draft (default)")
    p.add_argument("--create", metavar="SLUGS", help="Phase B: create issues for these comma-separated slugs")
    p.add_argument("--repo", help="owner/repo; defaults to the current checkout's origin remote")
    p.add_argument("--gh", default="gh", help="gh executable to invoke (default: gh)")
    p.add_argument("--backlog-files", nargs="*", help="override the configured backlog files")
    p.add_argument("--sessions-dir", help="override docs/sessions/")
    return p


def main(argv):
    args = build_parser().parse_args(argv[1:])
    if args.create:
        return phase_b(args, args.create)
    phase_a(args)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
