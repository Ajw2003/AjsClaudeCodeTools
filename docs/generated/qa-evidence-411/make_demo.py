#!/usr/bin/env python3
"""Builds the evidence for the QA page of #411 (QA pages must prove each change with evidence for its type).

Usage: python3 make_demo.py <work dir> <PlunderSpell checkout with the Ophan staging commit fetched as FETCH_HEAD>

It makes a throwaway git repo shaped like the Ophan feature (pull request Ajw2003/PlunderSpell#445), using
the real committed clip and screenshots, then builds the Ophan QA page three ways: with the builder from
main (the page aj got), with the new builder and no evidence (refused), and with the new builder and
evidence. The pictures and recording for the QA page are taken from those builds by shoot.js.
"""

import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
NEW_BUILDER = os.path.join(REPO, "claude-house-rules", "plugins", "house-rules", "scripts", "make_page.py")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def run(*a, cwd=None):
    r = subprocess.run(list(a), cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("%s failed: %s" % (" ".join(a), r.stderr or r.stdout))
    return r.stdout


def git(d, *a):
    return run("git", "-C", d, "-c", "user.name=demo", "-c", "user.email=demo@example.invalid",
               "-c", "commit.gpgsign=false", *a)


def clip(src, out, label, grey):
    vf = ("hue=s=0," if grey else "") + ("drawtext=fontfile=%s:text='%s':fontcolor=white:fontsize=22:"
                                         "box=1:boxcolor=black@0.6:x=10:y=10" % (FONT, label))
    run("ffmpeg", "-v", "error", "-y", "-i", src, "-vf", vf, "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", out)


def main(work, plunder, old_builder):
    os.makedirs(work, exist_ok=True)
    demo = os.path.join(work, "demo")
    if os.path.exists(demo):
        raise SystemExit("%s exists; pass a fresh work dir" % demo)
    os.makedirs(os.path.join(demo, "docs"))
    style = subprocess.run(["git", "-C", plunder, "show", "FETCH_HEAD:docs/page-style.json"],
                           capture_output=True, text=True, check=True).stdout
    open(os.path.join(demo, "docs", "page-style.json"), "w").write(style)
    git(demo, "init", "-q", "-b", "main")
    open(os.path.join(demo, "README.md"), "w").write("base\n")
    git(demo, "add", "-A")
    git(demo, "commit", "-qm", "base")
    git(demo, "checkout", "-q", "-b", "AjsAgent/ophan-arrival-418")
    files = {"Assets/Models/ArtBible/Enemies/Fear/TheOphanOfHours/TheOphanOfHours.controller": b"%YAML 1.1\n",
             "Assets/Models/ArtBible/Animations/TheOphanOfHours_Generic.fbx": b"fbx\n",
             "Assets/_Project/Scripts/Runtime/Raid/Ophan/OphanHunt.cs": b"class OphanHunt { }\n"}
    for rel in ("docs/art/anim/fear/ophan_spread.mp4", "docs/art/anim/fear/ophan_spread.png",
                "docs/generated/ophan-418/solo-beam.png", "docs/generated/ophan-418/coop-beam-host.png"):
        files[rel] = subprocess.run(["git", "-C", plunder, "show", "FETCH_HEAD:" + rel],
                                    capture_output=True, check=True).stdout
    for rel, data in files.items():
        p = os.path.join(demo, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(data)
    real = os.path.join(demo, "docs", "art", "anim", "fear", "ophan_spread.mp4")
    qa = os.path.join(demo, "docs", "generated", "qa")
    os.makedirs(qa)
    clip(real, os.path.join(qa, "standin-before.mp4"), "STAND-IN BEFORE", True)
    clip(real, os.path.join(qa, "standin-after.mp4"), "STAND-IN AFTER", False)
    git(demo, "add", "-A")
    git(demo, "commit", "-qm", "the Ophan in the sky")

    old = json.load(open(os.path.join(HERE, "ophan-page-as-sent.page.json")))
    with_ev = json.load(open(os.path.join(HERE, "ophan-page-with-evidence.page.json")))
    paths = {}
    for name, page in (("as-sent", old), ("with-evidence", with_ev)):
        p = os.path.join(work, "ophan-%s.page.json" % name)
        json.dump(page, open(p, "w"), indent=2)
        paths[name] = p
    out = {}
    r = subprocess.run([sys.executable, old_builder, "build", paths["as-sent"], "--project", demo,
                        "--out", os.path.join(work, "pages", "old-builder.html")], capture_output=True, text=True)
    out["old builder, page as sent"] = (r.returncode, (r.stdout + r.stderr).strip())
    r = subprocess.run([sys.executable, NEW_BUILDER, "build", paths["as-sent"], "--project", demo,
                        "--out", os.path.join(work, "pages", "new-builder-refused.html")], capture_output=True, text=True)
    out["new builder, page as sent"] = (r.returncode, (r.stdout + r.stderr).strip())
    r = subprocess.run([sys.executable, NEW_BUILDER, "build", paths["with-evidence"], "--project", demo,
                        "--out", os.path.join(work, "pages", "new-builder.html")], capture_output=True, text=True)
    out["new builder, page with evidence"] = (r.returncode, (r.stdout + r.stderr).strip())
    json.dump(out, open(os.path.join(work, "builds.json"), "w"), indent=2)
    for k, (rc, o) in out.items():
        print("== %s: exit %d\n%s\n" % (k, rc, o))


if __name__ == "__main__":
    main(*sys.argv[1:4])
