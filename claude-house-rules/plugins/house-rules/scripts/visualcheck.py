#!/usr/bin/env python3
"""visualcheck.py - capture a page as phone/desktop x light/dark screenshots plus a machine-readable report (#564).

  visualcheck.py doctor
  visualcheck.py shots --steps FILE --out DIR [--viewports phone,desktop] [--themes light,dark]
  visualcheck.py video --steps FILE --out DIR [--viewport phone|desktop] [--theme light|dark]
  visualcheck.py frames --video FILE --out DIR [--every SECONDS] [--columns N] [--expect-motion]

UNTESTED (#565, not tried here): Unity and game projects. The intended route is to capture the Game view with the
unity-cli skill (its Game view screenshot, or the Unity Recorder for a video), then run the same `frames` command on
the resulting video file. Nothing in this script talks to Unity.

Exit codes: 0 ok, 1 something wrong on a page, 3 tools missing, 4 bad usage. Playwright and Pillow are imported
only inside the commands that need them, so `doctor` and `--help` run on plain Python 3.8+. It never installs anything.
"""

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
VIEWPORTS = {"phone": (375, 812), "desktop": (1280, 800)}
THEMES = ("light", "dark")
ACTION_TIMEOUT_MS = 30000


def find_browser():
    """Path of a usable Chromium, or None. VISUALCHECK_BROWSER wins, then /opt/pw-browsers, then Playwright's own."""
    env = os.environ.get("VISUALCHECK_BROWSER")
    if env:
        return env if os.path.isfile(env) else None
    for pat in ("/opt/pw-browsers/chromium-*/chrome-linux*/chrome", "/opt/pw-browsers/chromium-*/chrome-linux*/headless_shell"):
        found = sorted(glob.glob(pat))
        if found:
            return found[-1]
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            path = p.chromium.executable_path
        return path if os.path.isfile(path) else None
    except Exception:  # Playwright absent or its driver failed: "no browser found" is the honest answer
        return None


def _have(mod):
    try:
        __import__(mod)
        return True
    except ImportError:
        return False


def doctor():
    rows = [("playwright", _have("playwright"), "pip install playwright pillow"),
            ("pillow", _have("PIL"), "pip install playwright pillow"),
            ("chromium", find_browser(), "python3 -m playwright install chromium (or set VISUALCHECK_BROWSER to a chrome binary)"),
            ("ffmpeg", shutil.which("ffmpeg"), "install ffmpeg with your package manager (only the later video step needs it)")]
    for name, found, fix in rows:
        detail = found if isinstance(found, str) else ""
        print("%-10s %s" % (name, ("ok " + detail).strip() if found else "MISSING - " + fix))
    return 0 if all(r[1] for r in rows[:3]) else 3


def load_steps(path):
    """(url, steps) from the steps file, or raises ValueError saying what is wrong."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise ValueError("cannot read steps file %s: %s" % (path, exc))
    if not isinstance(data, dict) or not isinstance(data.get("url"), str) or not data["url"]:
        raise ValueError('the steps file must be a JSON object with a "url" string')
    steps = data.get("steps", [])
    if not isinstance(steps, list):
        raise ValueError('"steps" must be a list')
    for i, s in enumerate(steps):
        if not isinstance(s, dict) or len(s) != 1:
            raise ValueError("step %d must be an object with exactly one key" % i)
        (k, v), = s.items()
        ok = {"goto": isinstance(v, str), "click": isinstance(v, str), "shot": isinstance(v, str) and v != "",
              "wait": isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0,
              "fill": isinstance(v, list) and len(v) == 2 and all(isinstance(x, str) for x in v)}
        if k not in ok:
            raise ValueError("step %d: unknown action %r (use goto, click, fill, wait, shot)" % (i, k))
        if not ok[k]:
            raise ValueError("step %d: bad value for %s" % (i, k))
    if not any("shot" in s for s in steps):
        steps = steps + [{"shot": "page"}]
    return to_url(data["url"]), steps


def to_url(u):
    import pathlib
    return u if "://" in u else pathlib.Path(u).resolve().as_uri()


def is_blank(path):
    from PIL import ImageStat, Image
    with Image.open(path) as im:
        st = ImageStat.Stat(im.convert("RGB"))
    return max(st.stddev) < 1.0


def shots(args):
    try:
        url, steps = load_steps(args.steps)
        vps = [v for v in args.viewports.split(",") if v]
        ths = [t for t in args.themes.split(",") if t]
        bad = [v for v in vps if v not in VIEWPORTS] + [t for t in ths if t not in THEMES]
        if bad or not vps or not ths:
            raise ValueError("unknown viewport/theme %s (viewports: phone, desktop; themes: light, dark)" % ", ".join(bad or ["(empty)"]))
    except ValueError as exc:
        print("bad usage: %s" % exc)
        return 4
    if doctor_quiet():
        print("tools missing; run `visualcheck.py doctor` for the install commands.")
        return 3
    from playwright.sync_api import sync_playwright
    from house_rules.waits import load_waits
    deadline_s = load_waits()["deadline_seconds"]["command"]
    t_end = time.time() + deadline_s
    os.makedirs(args.out, exist_ok=True)
    images, per_image, stopped = [], {}, None
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=find_browser(), args=["--no-sandbox"])
        try:
            for vp in vps:
                for th in ths:
                    if time.time() > t_end:
                        stopped = "deadline of %ss reached before %s-%s" % (deadline_s, vp, th)
                        break
                    w, h = VIEWPORTS[vp]
                    ctx = browser.new_context(viewport={"width": w, "height": h}, color_scheme=th)
                    page = ctx.new_page()
                    page.set_default_timeout(ACTION_TIMEOUT_MS)
                    errs = {"console_errors": [], "page_errors": [], "failed_requests": []}
                    page.on("console", lambda m, e=errs: m.type == "error" and e["console_errors"].append(m.text))
                    page.on("pageerror", lambda x, e=errs: e["page_errors"].append(str(x)))
                    page.on("requestfailed", lambda r, e=errs: e["failed_requests"].append("%s %s" % (r.url, r.failure)))
                    try:
                        page.goto(url)
                        for s in steps:
                            if time.time() > t_end:
                                stopped = "deadline of %ss reached during %s-%s" % (deadline_s, vp, th)
                                break
                            (k, v), = s.items()
                            if k == "goto":
                                page.goto(to_url(v))
                            elif k == "click":
                                page.click(v)
                            elif k == "fill":
                                page.fill(v[0], v[1])
                            elif k == "wait":
                                page.wait_for_timeout(v)
                            else:
                                name = "%s-%s-%s.png" % (v, vp, th)
                                page.screenshot(path=os.path.join(args.out, name))
                                images.append(name)
                                per_image[name] = dict({k2: list(v2) for k2, v2 in errs.items()},
                                                       overflow_x=bool(w == 375 and page.evaluate("document.documentElement.scrollWidth") > w),
                                                       blank=is_blank(os.path.join(args.out, name)))
                                for v2 in errs.values():  # per image: the next shot reports only what happens after this one
                                    del v2[:]
                    except Exception as exc:  # a failed action is a finding on this page, reported in words
                        errs["page_errors"].append("step failed: %s: %s" % (type(exc).__name__, str(exc)[:200]))
                        name = "FAILED-%s-%s.png" % (vp, th)
                        per_image[name] = dict(errs, overflow_x=False, blank=False)
                        images.append(name)
                    finally:
                        ctx.close()
                    if stopped:
                        break
                if stopped:
                    break
        finally:
            browser.close()
    ok = not stopped and all(not (d["console_errors"] or d["page_errors"] or d["failed_requests"] or d["overflow_x"] or d["blank"])
                             for d in per_image.values())
    report = {"ok": ok, "images": images, "deadline_seconds": deadline_s, "per_image": per_image}
    if stopped:
        report["stopped"] = stopped
    with open(os.path.join(args.out, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print("%d image(s) in %s; report.json ok=%s" % (len(images), args.out, ok))
    for n, d in per_image.items():
        flags = [k for k, v in d.items() if v]
        if flags:
            print("  %s: %s" % (n, ", ".join(flags)))
    if stopped:
        print("STOPPED: " + stopped)
    return 0 if ok else 1


def video(args):
    try:
        url, steps = load_steps(args.steps)
        if args.viewport not in VIEWPORTS or args.theme not in THEMES:
            raise ValueError("unknown viewport/theme %s-%s (viewports: phone, desktop; themes: light, dark)" % (args.viewport, args.theme))
    except ValueError as exc:
        print("bad usage: %s" % exc)
        return 4
    if doctor_quiet():
        print("tools missing; run `visualcheck.py doctor` for the install commands.")
        return 3
    from playwright.sync_api import sync_playwright
    from house_rules.waits import load_waits
    deadline_s = load_waits()["deadline_seconds"]["command"]
    t_end = time.time() + deadline_s
    os.makedirs(args.out, exist_ok=True)
    w, h = VIEWPORTS[args.viewport]
    final = os.path.join(args.out, "video-%s-%s.webm" % (args.viewport, args.theme))
    tmp = os.path.join(args.out, "_recording")
    shutil.rmtree(tmp, ignore_errors=True)
    problem = None
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=find_browser(), args=["--no-sandbox"])
        try:
            ctx = browser.new_context(viewport={"width": w, "height": h}, color_scheme=args.theme,
                                      record_video_dir=tmp, record_video_size={"width": w, "height": h})
            page = ctx.new_page()
            page.set_default_timeout(ACTION_TIMEOUT_MS)
            try:
                page.goto(url)
                for s in steps:
                    if time.time() > t_end:
                        problem = "deadline of %ss reached during the steps" % deadline_s
                        break
                    (k, v), = s.items()
                    if k == "goto":
                        page.goto(to_url(v))
                    elif k == "click":
                        page.click(v)
                    elif k == "fill":
                        page.fill(v[0], v[1])
                    elif k == "wait":
                        page.wait_for_timeout(v)
            except Exception as exc:  # a failed step is reported in words
                problem = "step failed: %s: %s" % (type(exc).__name__, str(exc)[:200])
            vid = page.video
            ctx.close()  # flushes the file
            if vid is not None and not problem:
                try:
                    vid.save_as(final)
                except Exception as exc:
                    problem = "the video was not saved: %s" % str(exc)[:200]
        finally:
            browser.close()
            shutil.rmtree(tmp, ignore_errors=True)
    if problem:
        print("video problem: " + problem)
        return 1
    if not os.path.isfile(final) or os.path.getsize(final) == 0:
        print("video problem: %s is missing or empty" % final)
        return 1
    print("video %s (%d bytes)" % (final, os.path.getsize(final)))
    return 0


def measure(deltas, every):
    """The motion measures from consecutive-frame deltas (percent of full scale)."""
    runs, i = [], 0
    while i < len(deltas):
        if deltas[i] < 0.05:
            j = i
            while j + 1 < len(deltas) and deltas[j + 1] < 0.05:
                j += 1
            if j - i + 1 >= 3:
                runs.append([round(i * every, 3), round((j + 1) * every, 3)])
            i = j + 1
        else:
            i += 1
    nz = sorted(d for d in deltas if d > 0)
    jumps = []
    if len(nz) >= 3:
        med = nz[len(nz) // 2] if len(nz) % 2 else (nz[len(nz) // 2 - 1] + nz[len(nz) // 2]) / 2
        jumps = [i for i, d in enumerate(deltas) if d > 5 * med and d >= 5]
    mx = max(deltas) if deltas else 0.0
    return {"deltas": deltas, "max_delta": mx, "frozen_runs": runs, "jumps": jumps, "static": mx < 0.05}


def frames(args):
    if args.every <= 0 or args.columns < 1:
        print("bad usage: --every must be above 0 and --columns at least 1")
        return 4
    if not os.path.isfile(args.video):
        print("bad usage: video file not found: %s" % args.video)
        return 4
    if not shutil.which("ffmpeg"):
        print("tools missing: ffmpeg (install it with your package manager); `visualcheck.py doctor` shows the rest.")
        return 3
    if not _have("PIL"):
        print("tools missing: Pillow (pip install pillow)")
        return 3
    from PIL import Image, ImageChops, ImageDraw, ImageStat
    from house_rules.waits import load_waits
    deadline_s = load_waits()["deadline_seconds"]["command"]
    fdir = os.path.join(args.out, "frames")
    shutil.rmtree(fdir, ignore_errors=True)
    os.makedirs(fdir)
    try:
        pr = subprocess.run(["ffmpeg", "-v", "error", "-i", args.video, "-vf", "fps=1/%s" % args.every,
                             os.path.join(fdir, "f%04d.png")], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=deadline_s)
    except subprocess.TimeoutExpired:
        print("ffmpeg did not finish within the %ss command deadline" % deadline_s)
        return 1
    files = sorted(glob.glob(os.path.join(fdir, "f*.png")))
    if pr.returncode != 0 or not files:
        print("ffmpeg could not read frames from %s (exit %d): %s" % (args.video, pr.returncode, pr.stdout.decode("utf-8", "replace")[:300]))
        return 4
    ims = [Image.open(f).convert("RGB") for f in files]
    deltas = [round(sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3 / 255 * 100, 4) for a, b in zip(ims, ims[1:])]
    m = measure(deltas, args.every)
    tw = min(320, ims[0].width)
    th = round(ims[0].height * tw / ims[0].width)
    cols = min(args.columns, len(ims))
    rows = -(-len(ims) // cols)
    sheet = Image.new("RGB", (cols * tw, rows * (th + 16)), "white")
    d = ImageDraw.Draw(sheet)
    names = []
    for n, im in enumerate(ims):
        x, y = (n % cols) * tw, (n // cols) * (th + 16)
        sheet.paste(im.resize((tw, th)), (x, y + 16))
        d.text((x + 3, y + 2), "%.2fs" % (n * args.every), fill="black")
        names.append({"file": os.path.relpath(files[n], args.out), "t": round(n * args.every, 3)})
    sheet.save(os.path.join(args.out, "sheet.png"))
    bad = m["static"] or bool(m["frozen_runs"]) or bool(m["jumps"])
    ok = not (args.expect_motion and bad)
    with open(os.path.join(args.out, "frames.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(m, ok=ok, expect_motion=args.expect_motion, every=args.every, frames=names), fh, indent=2)
    print("%d frame(s), max delta %.3f%%; sheet %s" % (len(ims), m["max_delta"], os.path.join(args.out, "sheet.png")))
    if m["static"]:
        print("  static: nothing moved between frames")
    for a, b in m["frozen_runs"]:
        print("  frozen from %.2fs to %.2fs" % (a, b))
    for j in m["jumps"]:
        print("  jump at %.2fs (delta %.2f%%)" % ((j + 1) * args.every, deltas[j]))
    return 0 if ok else 1


def doctor_quiet():
    return not (_have("playwright") and _have("PIL") and find_browser())


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("doctor", help="check the tools; installs nothing")
    sp = sub.add_parser("shots", help="screenshots and report")
    sp.add_argument("--steps", required=True)
    sp.add_argument("--out", required=True)
    sp.add_argument("--viewports", default="phone,desktop")
    sp.add_argument("--themes", default="light,dark")
    vp = sub.add_parser("video", help="record a video of the steps")
    vp.add_argument("--steps", required=True)
    vp.add_argument("--out", required=True)
    vp.add_argument("--viewport", default="phone")
    vp.add_argument("--theme", default="light")
    fp = sub.add_parser("frames", help="frame sheet and motion measures from a video")
    fp.add_argument("--video", required=True)
    fp.add_argument("--out", required=True)
    fp.add_argument("--every", type=float, default=0.5)
    fp.add_argument("--columns", type=int, default=4)
    fp.add_argument("--expect-motion", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 0 if e.code == 0 else 4
    if args.cmd == "doctor":
        return doctor()
    if args.cmd == "shots":
        return shots(args)
    if args.cmd == "video":
        return video(args)
    if args.cmd == "frames":
        return frames(args)
    ap.print_usage()
    return 4


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
