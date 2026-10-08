#!/usr/bin/env python3
"""Render review PNGs + stats.json for one model through Unity batchmode (renders: no -nographics).

  python unity_capture.py --project <dir> --model Assets/Art/Generated/X.fbx --out <abs dir>

Editor is chosen from ProjectSettings/ProjectVersion.txt under the Hub path, or $UNITY_EDITOR.
Needs the com.aj.art-pipeline package in the project (claude-art-pipeline/unity).
Prints PNG paths on success; the log tail and exit 1 on failure.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HUB = Path(os.environ.get("UNITY_HUB_EDITORS", r"C:\Program Files\Unity\Hub\Editor"))


def find_editor(project: Path) -> Path:
    if os.environ.get("UNITY_EDITOR"):
        return Path(os.environ["UNITY_EDITOR"])
    text = (project / "ProjectSettings" / "ProjectVersion.txt").read_text()
    ver = re.search(r"m_EditorVersion:\s*(\S+)", text).group(1)
    exe = HUB / ver / "Editor" / "Unity.exe"
    if not exe.exists():
        sys.exit(f"ERROR: Unity {ver} not found at {exe} (set UNITY_EDITOR to override)")
    return exe


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--model", required=True, help="Assets/... path of the FBX")
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout", type=int, default=1800)
    a = ap.parse_args()

    project, out = Path(a.project).resolve(), Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / "stats.json").unlink(missing_ok=True)
    log = out / "unity.log"
    cmd = [str(find_editor(project)), "-batchmode", "-quit", "-projectPath", str(project),
           "-logFile", str(log), "-executeMethod", "AjArtPipeline.ArtPipelineCapture.Run",
           "-artModel", a.model, "-artOut", str(out)]
    try:
        rc = subprocess.run(cmd, timeout=a.timeout).returncode
    except subprocess.TimeoutExpired:
        rc = -1
    stats = out / "stats.json"
    if rc != 0 or not stats.exists():
        tail = log.read_text(errors="replace").splitlines()[-40:] if log.exists() else ["(no log written)"]
        print(f"ERROR: unity exit {rc}; log {log}\n" + "\n".join(tail), file=sys.stderr)
        return 1
    for p in json.loads(stats.read_text())["images"]:
        print(p)
    print(stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
