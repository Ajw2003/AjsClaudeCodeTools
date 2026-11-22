#!/usr/bin/env python3
"""visualcheck.py - capture a page as phone/desktop x light/dark screenshots plus a machine-readable report (#564).

  visualcheck.py doctor
  visualcheck.py shots --steps FILE --out DIR [--viewports phone,desktop] [--themes light,dark]

Exit codes: 0 ok, 1 something wrong on a page, 3 tools missing, 4 bad usage. Playwright and Pillow are imported
only inside the commands that need them, so `doctor` and `--help` run on plain Python 3.8+. It never installs anything.
"""

import argparse
import glob
import json
import os
import shutil
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
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 0 if e.code == 0 else 4
    if args.cmd == "doctor":
        return doctor()
    if args.cmd == "shots":
        return shots(args)
    ap.print_usage()
    return 4


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
