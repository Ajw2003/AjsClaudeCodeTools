"""artlib.py - the one place the art-pipeline gate logic lives. hook.py and review.py both
import it. Stdlib only."""

import fnmatch
import json
import os
import re
import shutil
import subprocess
import time

DEFAULT_GLOBS = ["*.fbx", "*.glb", "*.gltf", "*.blend", "*.obj"]
DEFAULT_EXCLUDE = ["node_modules/", "Library/", "Temp/", ".git/"]
DEFAULT_REVIEW_DIR = "docs/art/reviews"
DEFAULT_ASSET_DIR = "docs/art/assets"
STAGES = ["brief", "concept", "spec", "model", "rig", "clips", "engine", "done"]
APPROVAL = ("brief", "concept")
LOOK = ("spec", "model", "rig", "clips", "engine")
KINDS = ("prop", "character", "creature", "set")
NA_KINDS = ("prop", "set")  # rig and clips are n/a for these
MIN_SEEN = 40
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")
MAX_BLOCKS = 3
DOC_PATHS = ["docs/**", "**/*.json"]
DOC_TIMEOUT = 60
HERE = os.path.dirname(os.path.abspath(__file__))


def git(cwd, *args):
    p = subprocess.run(["git", "-c", "core.quotepath=off"] + list(args), cwd=cwd,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args), p.stderr.decode("utf-8", "replace").strip()))
    return p.stdout.decode("utf-8", "replace")


def repo_info(start_dir):
    """(toplevel, absolute git dir) or None when start_dir is not in a git repo."""
    try:
        top = git(start_dir, "rev-parse", "--show-toplevel").strip()
        gd = git(start_dir, "rev-parse", "--absolute-git-dir").strip()
    except (RuntimeError, OSError):
        return None
    return os.path.normpath(top), os.path.normpath(gd)


def head_sha(root):
    try:
        return git(root, "rev-parse", "HEAD").strip()
    except RuntimeError:  # no commits yet
        return ""


def load_config(root):
    cfg = {"model_globs": DEFAULT_GLOBS, "exclude": DEFAULT_EXCLUDE, "review_dir": DEFAULT_REVIEW_DIR,
           "doc_check": "", "doc_check_paths": DOC_PATHS,
           "asset_dir": DEFAULT_ASSET_DIR, "min_looks": 2, "engine": "unity", "engine_capture": "",
           "stage_outputs": {}}
    path = os.path.join(root, ".art-pipeline.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            user = json.load(fh)  # a bad config raises; callers announce it
        for k in cfg:
            if k in user:
                cfg[k] = user[k]
    return cfg


def is_model(rel, cfg):
    low = rel.lower()
    for ex in cfg["exclude"]:
        ex = ex.lower()
        if low.startswith(ex) or ("/" + ex) in ("/" + low):
            return False
    base = low.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(base if "/" not in g else low, g.lower()) for g in cfg["model_globs"])


def tracked_has_art(root, cfg):
    out = git(root, "ls-files", "--cached", "--others", "--exclude-standard")
    return any(is_model(f, cfg) for f in out.splitlines())


def changed_files(root, start):
    names = set()
    if start and start != head_sha(root):
        names.update(git(root, "diff", "--name-only", "%s..HEAD" % start).splitlines())
    toks = git(root, "status", "--porcelain", "-uall", "-z").split("\0")
    i = 0
    while i < len(toks):
        t = toks[i]
        i += 1
        if len(t) < 4:
            continue
        names.add(t[3:])
        if t[0] in "RC":
            i += 1  # skip the rename source
    return sorted(names)


def changed_models(root, start, cfg):
    return [n for n in changed_files(root, start) if is_model(n, cfg) and os.path.isfile(os.path.join(root, n))]


def _path_match(rel, pat):
    return fnmatch.fnmatch(rel, pat) or (pat.startswith("**/") and fnmatch.fnmatch(rel, pat[3:]))


# doc_check commands are POSIX sh; on Windows shell=True means cmd.exe, which runs `a; exit 3` as one echo and exits 0.
_SH = ["sh", "-c"] if shutil.which("sh") else None


def run_doc_check(root, cfg, names):
    """None when not configured / nothing relevant changed, else ('ok'|'fail'|'timeout', [detail])."""
    cmd = cfg.get("doc_check")
    if not cmd:
        return None
    pats = cfg.get("doc_check_paths") or DOC_PATHS
    if not any(is_model(n, cfg) or any(_path_match(n, g) for g in pats) for n in names):
        return None
    try:
        p = subprocess.run(_SH + [cmd] if _SH else cmd, shell=not _SH, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=DOC_TIMEOUT)
    except subprocess.TimeoutExpired:
        return "timeout", ["doc_check `%s` timed out after %ds; not checked" % (cmd, DOC_TIMEOUT)]
    if p.returncode == 0:
        return "ok", []
    tail = p.stdout.decode("utf-8", "replace").strip().splitlines()[-20:]
    return "fail", ["doc_check `%s` exited %d:" % (cmd, p.returncode)] + tail


# --- ledger -----------------------------------------------------------------------------

def san(session_id):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", session_id or "") or "nosession"


def ledger_path(gitdir, session_id):
    sid = san(session_id)
    return os.path.join(gitdir, "art-pipeline", sid + ".json")


def load_ledger(path):
    if not os.path.exists(path):
        return {"start": "", "seen": [], "blocks": {}}
    with open(path, "r", encoding="utf-8") as fh:
        led = json.load(fh)
    if not isinstance(led, dict) or not isinstance(led.get("seen"), list):
        raise ValueError("ledger %s has the wrong shape" % path)
    led.setdefault("start", "")
    led.setdefault("blocks", {})
    return led


def save_ledger(path, led):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(led, separators=(",", ":")))


def norm(p):
    return os.path.normcase(os.path.realpath(p))


# --- review records ---------------------------------------------------------------------

def record_name(model):
    return model.replace("/", "__") + ".review.json"


def load_records(root, cfg):
    d = os.path.join(root, cfg["review_dir"])
    recs, bad = [], []
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.endswith(".review.json"):
                try:
                    with open(os.path.join(d, f), "r", encoding="utf-8") as fh:
                        r = json.load(fh)
                    if not isinstance(r, dict):
                        raise ValueError("not an object")
                    recs.append(r)
                except Exception as exc:
                    bad.append("%s/%s (%s)" % (cfg["review_dir"], f, exc))
    return recs, bad


def check_model(root, model, recs, seen_paths, cfg):
    """('ok'|'waived'|'fail', [problems]). Passes if any record for the model is satisfied."""
    mine = [r for r in recs if r.get("model") == model]
    if not mine:
        return "fail", ["no review record in %s/ with \"model\": \"%s\"" % (cfg["review_dir"], model)]
    last = None
    for r in mine:
        probs = []
        verdict = r.get("verdict")
        seen_txt = r.get("seen") if isinstance(r.get("seen"), str) else ""
        sheet = r.get("sheet") if isinstance(r.get("sheet"), str) else ""
        sheet_abs = os.path.join(root, sheet) if sheet else ""
        if verdict not in ("pass", "fail", "waived"):
            probs.append("verdict must be pass, fail or waived (got %r)" % (verdict,))
        elif verdict == "fail":
            probs.append("the record's verdict is fail - fix the model, re-render the sheet, re-review")
        if len(seen_txt.strip()) < MIN_SEEN:
            probs.append("\"seen\" must say what the reviewer saw (>= %d chars)" % MIN_SEEN)
        if not sheet or not os.path.isfile(sheet_abs):
            probs.append("sheet %r does not exist" % sheet)
        else:
            if os.path.getmtime(sheet_abs) < os.path.getmtime(os.path.join(root, model)):
                probs.append("sheet %s is older than the model - re-render it" % sheet)
            if norm(sheet_abs) not in seen_paths:
                probs.append("sheet %s was not opened (Read) this session" % sheet)
        if not probs:
            return ("waived" if verdict == "waived" else "ok"), []
        last = probs
    return "fail", last


def evaluate(root, gitdir, session_id):
    """Shared by the Stop gate and `review.py status`. Returns (cfg, ledger, results, bad)
    where results = [(model, status, problems)]."""
    cfg = load_config(root)
    led = load_ledger(ledger_path(gitdir, session_id))
    seen = {norm(e["path"]) for e in led["seen"] if isinstance(e, dict) and "path" in e}
    recs, bad = load_records(root, cfg)
    res = []
    names = changed_files(root, led["start"])
    for m in names:
        if is_model(m, cfg) and os.path.isfile(os.path.join(root, m)):
            st, pr = check_model(root, m, recs, seen, cfg)
            res.append((m, st, pr))
    res += check_assets(root, cfg, names, seen, san(session_id))
    dc = run_doc_check(root, cfg, names)
    if dc:
        res.append(("doc_check", dc[0], dc[1]))
    return cfg, led, res, bad


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def fix_hint(cfg):
    return ("make a review sheet PNG of the model beside its concept (art-pipeline skill), open it "
            "with Read, then: python \"%s\" record --model <model> --sheet <sheet.png> "
            "--verdict pass --seen \"<what you saw, >= %d chars>\"" % (os.path.join(HERE, "review.py"), MIN_SEEN))


# --- asset ledgers (plan -> build -> verify -> iterate) ---------------------------------

def asset_file(root, cfg, slug):
    return os.path.join(root, cfg["asset_dir"], slug + ".json")


def load_asset(root, cfg, slug):
    p = asset_file(root, cfg, slug)
    if not os.path.isfile(p):
        raise ValueError("no asset %r (expected %s)" % (slug, p))
    with open(p, "r", encoding="utf-8") as fh:
        a = json.load(fh)
    if not isinstance(a, dict) or a.get("stage") not in STAGES or not isinstance(a.get("history"), list):
        raise ValueError("asset file %s has the wrong shape" % p)
    return a


def save_asset(root, cfg, a):
    p = asset_file(root, cfg, a["slug"])
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(a, fh, indent=2)
        fh.write("\n")
    return p


def list_assets(root, cfg):
    d = os.path.join(root, cfg["asset_dir"])
    return sorted(f[:-5] for f in os.listdir(d) if f.endswith(".json")) if os.path.isdir(d) else []


def is_look(rec):
    return rec.get("verdict") in ("pass", "fail") and not rec.get("approval")


def newest_session(gitdir):
    """(session id, set of normalized seen paths) of the newest session ledger; stands in for 'this session'."""
    d = os.path.join(gitdir, "art-pipeline")
    leds = [os.path.join(d, f) for f in os.listdir(d) if f.endswith(".json")] if os.path.isdir(d) else []
    if not leds:
        return "", set()
    p = max(leds, key=os.path.getmtime)
    led = load_ledger(p)
    return os.path.basename(p)[:-5], {norm(e["path"]) for e in led["seen"] if isinstance(e, dict) and "path" in e}


def reported(a):
    """Every skip and first-look-pass in the asset's history, as report lines."""
    out = []
    for r in a["history"]:
        if r.get("verdict") == "skipped":
            out.append("SKIPPED %s/%s: %s" % (a["slug"], r["stage"], r.get("reason", "")))
        elif r.get("first_look_pass"):
            out.append("FIRST-LOOK-PASS %s/%s: %s" % (a["slug"], r["stage"], r.get("reason", "")))
    return out


def check_assets(root, cfg, names, seen, sid):
    """res entries for asset ledgers changed this session: ('asset:<slug>', 'fail', problems) when a
    pass record of THIS session names a sheet not opened this session; ('asset:<slug>', 'report', lines)
    for every skip / first-look-pass."""
    res, pre = [], cfg["asset_dir"].rstrip("/") + "/"
    for n in names:
        if not (n.startswith(pre) and n.endswith(".json")) or not os.path.isfile(os.path.join(root, n)):
            continue
        slug = n[len(pre):-5]
        try:
            a = load_asset(root, cfg, slug)
        except Exception as exc:
            res.append(("asset:" + slug, "fail", ["unreadable asset ledger: %s" % exc]))
            continue
        probs = []
        for r in a["history"]:
            sh = r.get("sheet")
            if r.get("verdict") == "pass" and sh and r.get("session") == sid and norm(os.path.join(root, sh)) not in seen:
                probs.append("%s/%s: pass record names sheet %s, which was not opened (Read) this session" % (slug, r.get("stage"), sh))
        if probs:
            res.append(("asset:" + slug, "fail", probs))
        rep = reported(a)
        if rep:
            res.append(("asset:" + slug, "report", rep))
    return res
