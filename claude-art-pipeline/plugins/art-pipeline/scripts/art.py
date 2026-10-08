#!/usr/bin/env python3
"""art.py - the per-asset plan -> build -> verify -> iterate ledger. Stdlib only, shares artlib.

  art.py new <slug> --kind prop|character|creature|set
  art.py status [slug]        art.py next <slug>
  art.py record <slug> --verdict pass|fail [--sheet PNG --seen TEXT] [--approved-by-user]
                [--first-look-pass REASON]
  art.py skip <slug> --reason TEXT        art.py advance <slug>
Stages: brief concept spec model rig clips engine done. Every refusal: one line on stderr, exit 1."""

import argparse
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artlib as L  # noqa: E402

ME = 'python "%s"' % os.path.abspath(__file__)
INFO = {  # stage -> (produces, gate)
    "brief": ("docs/art/BRIEF.md from references/style-bible-template.md", "USER APPROVAL: ask the user, then record --approved-by-user"),
    "concept": ("one concept sheet PNG per asset, drawn by code", "USER APPROVAL of the design, then record --approved-by-user"),
    "spec": ("one JSON spec entry: sizes, materials with hex, budgets", "LOOK: sheet and JSON numbers agree"),
    "model": ("mesh + textures from a blueprint script. Then: python3 scripts/render_views.py <model> --out <dir>; "
              "python3 scripts/review_sheet.py --concept <concept.png> --views <dir> --title <Name> --out <sheet.png>",
              "LOOK: open the sheet with Read; silhouette, proportion, colour, budget vs the concept"),
    "rig": ("armature, skin weights, a test pose", "LOOK: posed views bend without tearing"),
    "clips": ("keyframed clips + stills/MP4", "LOOK: feet do not slide, the pose reads as the action"),
    "engine": ("importer rules, animator, capture in the engine", "LOOK: a capture taken in the engine"),
}


class Refuse(Exception):
    pass


def need(ok, msg):
    if not ok:
        raise Refuse(msg)


def na(kind, stage):
    return stage in ("rig", "clips") and kind in L.NA_KINDS


def last(a, stage):
    h = [r for r in a["history"] if r["stage"] == stage]
    return h[-1] if h else None


def looks(a, stage):
    return [r for r in a["history"] if r["stage"] == stage and L.is_look(r)]


def rel(root, p):
    return os.path.relpath(os.path.abspath(p), root).replace(os.sep, "/")


def table(root, cfg):
    slugs = L.list_assets(root, cfg)
    if not slugs:
        return "no assets (art.py new <slug> --kind K)"
    rows = [("slug", "kind", "stage", "last", "looks", "skips")]
    for s in slugs:
        try:
            a = L.load_asset(root, cfg, s)
        except Exception as exc:
            rows.append((s, "?", "UNREADABLE: %s" % exc, "", "", ""))
            continue
        ls = a["history"][-1]["stage"] if a["history"] else a["stage"]
        lr = last(a, ls)
        rows.append((s, a["kind"], a["stage"], lr["verdict"] if lr else "-",
                     str(len(looks(a, ls))), str(len(L.reported(a)))))
    w = [max(len(r[i]) for r in rows) for i in range(6)]
    return "\n".join("  ".join(c.ljust(w[i]) for i, c in enumerate(r)).rstrip() for r in rows)


def check_sheet(root, cfg, gitdir, a, stage, sheet, seen_txt):
    """Look-gate evidence; returns the session id to stamp on the record."""
    need(sheet, "stage %s is a look gate: --sheet <png> is required" % stage)
    need(len((seen_txt or "").strip()) >= L.MIN_SEEN, "--seen must be >= %d chars (say what you saw)" % L.MIN_SEEN)
    sp = os.path.join(root, sheet)
    need(os.path.isfile(sp), "sheet %s does not exist" % sheet)
    outs = [f for pat in cfg["stage_outputs"].get(stage, [])
            for f in glob.glob(os.path.join(root, pat.format(slug=a["slug"])), recursive=True) if os.path.isfile(f)]
    if outs:
        newest = max(outs, key=os.path.getmtime)
        need(os.path.getmtime(sp) >= os.path.getmtime(newest), "sheet %s is older than %s - re-render it" % (sheet, rel(root, newest)))
    sid, seen = L.newest_session(gitdir)
    need(L.norm(sp) in seen, "sheet %s was not opened (Read) this session" % sheet)
    return sid


def advance_to_next(a):
    a["stage"] = L.STAGES[L.STAGES.index(a["stage"]) + 1]
    while na(a["kind"], a["stage"]):
        a["history"].append({"stage": a["stage"], "verdict": "n/a", "sheet": "", "seen": "",
                             "reason": "not applicable to kind %s" % a["kind"], "date": L.now()})
        a["stage"] = L.STAGES[L.STAGES.index(a["stage"]) + 1]


def run(root, gitdir, cfg, a):
    cmd = a.cmd
    if cmd == "new":
        need(re.fullmatch(r"[a-z0-9][a-z0-9_-]*", a.slug), "slug must be lowercase letters, digits, - or _")
        need(not os.path.exists(L.asset_file(root, cfg, a.slug)), "asset %s already exists" % a.slug)
        print(L.save_asset(root, cfg, {"slug": a.slug, "kind": a.kind, "stage": "brief", "history": []}))
        return
    if cmd == "status" and not a.slug:
        print(table(root, cfg))
        return
    asset = L.load_asset(root, cfg, a.slug)
    st = asset["stage"]
    if cmd == "status":
        print("%s (%s) at %s" % (asset["slug"], asset["kind"], st))
        for r in asset["history"]:
            print("  %-8s %-8s %s" % (r["stage"], r["verdict"], (r.get("reason") or r.get("seen") or "")[:80]))
        return
    if cmd == "next":
        if st == "done":
            print("%s is done." % a.slug)
            return
        prod, gate = INFO[st]
        print("stage: %s\nproduces: %s\ngate: %s" % (st, prod, gate))
        if st == "engine":
            cap = cfg["engine_capture"]
            print("capture (%s): %s" % (cfg["engine"], cap.replace("{slug}", a.slug) if cap else
                  "no engine adapter configured (set engine_capture in .art-pipeline.json); capture by hand and label it UNTESTED"))
        extra = " --approved-by-user" if st in L.APPROVAL else " --sheet <png> --seen \"<what you saw, >= 40 chars>\""
        print("record: %s record %s --verdict pass|fail%s" % (ME, a.slug, extra))
        print("or skip: %s skip %s --reason \"...\"   then: %s advance %s" % (ME, a.slug, ME, a.slug))
        return
    need(st != "done", "%s is already done" % a.slug)
    if cmd == "skip":
        need(a.reason.strip(), "--reason must not be empty")
        asset["history"].append({"stage": st, "verdict": "skipped", "sheet": "", "seen": "", "reason": a.reason, "date": L.now()})
        L.save_asset(root, cfg, asset)
        print("%s/%s SKIPPED (reported at every Stop): %s" % (a.slug, st, a.reason))
        return
    if cmd == "advance":
        lr = last(asset, st)
        need(lr is not None, "stage %s has no record yet" % st)
        need(lr["verdict"] in ("pass", "skipped", "n/a"), "stage %s last record is %s; needs pass or a skip" % (st, lr["verdict"]))
        advance_to_next(asset)
        L.save_asset(root, cfg, asset)
        print("%s -> %s" % (a.slug, asset["stage"]))
        return
    # record
    rec = {"stage": st, "verdict": a.verdict, "sheet": "", "seen": a.seen or "", "reason": "", "date": L.now()}
    if st in L.APPROVAL:
        need(a.verdict == "fail" or a.approved_by_user,
             "stage %s is a user-approval gate: pass needs --approved-by-user, else skip with a reason" % st)
        rec["approval"] = True
        if a.sheet:
            need(os.path.isfile(os.path.join(root, a.sheet)), "sheet %s does not exist" % a.sheet)
            rec["sheet"] = rel(root, a.sheet)
            rec["session"] = L.newest_session(gitdir)[0]
    else:
        rec["sheet"] = rel(root, a.sheet) if a.sheet else ""
        rec["session"] = check_sheet(root, cfg, gitdir, asset, st, rec["sheet"], a.seen)
        if a.verdict == "pass":
            have = len(looks(asset, st)) + 1
            if have < cfg["min_looks"]:
                need(a.first_look_pass, "stage %s needs %d looks before a pass (this would be look %d): record a fail, fix, look again - or --first-look-pass \"<reason>\"" % (st, cfg["min_looks"], have))
                rec["first_look_pass"], rec["reason"] = True, a.first_look_pass
    asset["history"].append(rec)
    L.save_asset(root, cfg, asset)
    print("%s/%s %s recorded%s" % (a.slug, st, a.verdict, " (FIRST-LOOK-PASS, reported)" if rec.get("first_look_pass") else ""))


def main(argv):
    ap = argparse.ArgumentParser(prog="art.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("new")
    p.add_argument("slug")
    p.add_argument("--kind", required=True, choices=L.KINDS)
    sub.add_parser("status").add_argument("slug", nargs="?")
    sub.add_parser("next").add_argument("slug")
    p = sub.add_parser("record")
    p.add_argument("slug")
    p.add_argument("--verdict", required=True, choices=["pass", "fail"])
    p.add_argument("--sheet")
    p.add_argument("--seen")
    p.add_argument("--approved-by-user", action="store_true")
    p.add_argument("--first-look-pass")
    p = sub.add_parser("skip")
    p.add_argument("slug")
    p.add_argument("--reason", required=True)
    sub.add_parser("advance").add_argument("slug")
    a = ap.parse_args(argv[1:])
    info = L.repo_info(os.getcwd())
    if not info:
        print("art.py: not inside a git repo", file=sys.stderr)
        return 2
    try:
        run(info[0], info[1], L.load_config(info[0]), a)
    except (Refuse, ValueError) as exc:
        print("art.py: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
