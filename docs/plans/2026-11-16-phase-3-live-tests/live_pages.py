"""Feature switches (#537): with the design loop on, a ~250-word reply in a non-git folder gets the page reminder
("links no page or picture") unless "pages off" was typed in that folder first. Real headless sessions with this
branch's plugin; the installed copy switched off. Prints PASS/FAIL with the evidence."""
import json, os, shutil, subprocess, sys

PLUGIN = "/home/user/AjsClaudeCodeTools/claude-house-rules/plugins/house-rules"
ROOT = sys.argv[1]
ASK = "Explain in at least 300 words how a hash table works. Plain prose, no headings, no links."

def env():
    e = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_REMOTE" and not k.startswith("HOUSE_RULES_")}
    e.update(HOUSE_RULES_LOOP="on", HOUSE_RULES_ISSUES="off")
    return e

def session(cwd, prompt):
    p = subprocess.run(["claude", "-p", "--plugin-dir", PLUGIN, "--settings",
                        json.dumps({"enabledPlugins": {"house-rules@aj-house-rules": False}}), "--model", "haiku",
                        "--output-format", "stream-json", "--verbose", "--include-hook-events", prompt],
                       cwd=cwd, capture_output=True, text=True, timeout=600, stdin=subprocess.DEVNULL, env=env())
    out, words = [], 0
    for line in p.stdout.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") == "result":
            words = len((d.get("result") or "").split())
        if d.get("type") == "system" and d.get("subtype") == "hook_response":
            out.append((d.get("hook_name") or "") + " " + (d.get("stdout") or ""))
    return out, words

def reminded(hooks):
    return [h[:200] for h in hooks if "links no page or picture" in h]

for name, first in (("control-pages-on", None), ("pages-off", "pages off")):
    d = os.path.join(ROOT, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    if first:
        session(d, first)
    hooks, words = session(d, ASK)
    hits = reminded(hooks)
    want = first is None
    print("%s %s: reply %d words, page reminder %s (%d hook responses)" % ("PASS" if bool(hits) == want else "FAIL", name,
          words, "given" if hits else "not given", len(hooks)))
    for h in hits:
        print("    " + h.replace("\n", " "))


# The model keeps replies short under the house rules (77 and 72 words on 2026-11-16), so the 160-word reminder
# cannot be forced live; the reminder itself is proven by calling the Stop hook directly (live_pages_direct below)
# and by verify.py. What a live session does show is the standing note on each prompt.
for name, first in (("note-control", None), ("note-pages-off", "pages off")):
    d = os.path.join(ROOT, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    if first:
        session(d, first)
    hooks, _w = session(d, "Say ok.")
    note = [h[:220] for h in hooks if "Pages OFF" in h]
    want = first is not None
    print("%s %s: Pages OFF note on the next prompt %s" % ("PASS" if bool(note) == want else "FAIL", name,
          "present" if note else "absent"))
    for h in note:
        print("    " + h.replace("\n", " "))

# Direct: the Stop hook with a 250-word reply in a non-git folder, pages on vs off.
HOOK = PLUGIN + "/scripts/hook.py"
d = os.path.join(ROOT, "direct"); os.makedirs(d, exist_ok=True)
for pages in ("on", "off"):
    e = env(); e["HOUSE_RULES_PAGES"] = pages
    pl = {"hook_event_name": "Stop", "session_id": "x", "cwd": d, "stop_hook_active": False,
          "last_assistant_message": " ".join(["word"] * 250), "transcript_path": ""}
    p = subprocess.run([sys.executable, HOOK, "handover"], input=json.dumps(pl), capture_output=True, text=True, env=e)
    got = "links no page or picture" in p.stdout
    print("%s direct Stop hook, 250 words, pages %s: reminder %s" % ("PASS" if got == (pages == "on") else "FAIL",
          pages, "given" if got else "not given"))
