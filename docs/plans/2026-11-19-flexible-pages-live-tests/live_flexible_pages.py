"""Flexible pages (#541): real headless sessions with this branch's plugin loaded by --plugin-dir and the installed
copy switched off, so the plugin under test is exactly the branch code. Replaces aj's desktop QA, which ran the
claude.ai account's copy of the plugin (following main) instead of the branch build.

    python3 live_flexible_pages.py <empty scratch folder>

Prints PASS/FAIL per test with the hook evidence. Each test starts one paid session on the haiku model."""
import json, os, shutil, subprocess, sys

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..",
                                      "claude-house-rules", "plugins", "house-rules"))
ROOT = os.path.abspath(sys.argv[1])


def env():
    e = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_REMOTE" and not k.startswith("HOUSE_RULES_")}
    e.update(HOUSE_RULES_LOOP="on", HOUSE_RULES_ISSUES="off")
    return e


def repo(name):
    d = os.path.join(ROOT, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(os.path.join(d, "docs", "plans"))
    for argv in (["init", "-q", "-b", "AjsAgent/live-test"], ["config", "user.name", "Edens Agent"],
                 ["config", "user.email", "edens-agent@users.noreply.github.com"]):
        subprocess.run(["git", "-C", d] + argv, check=True)
    with open(os.path.join(d, "README.md"), "w") as f:
        f.write("# live test\n")
    subprocess.run(["git", "-C", d, "add", "-A"], check=True)
    subprocess.run(["git", "-C", d, "commit", "-qm", "init"], check=True)
    return d


def session(cwd, prompt):
    p = subprocess.run(["claude", "-p", "--plugin-dir", PLUGIN, "--settings",
                        json.dumps({"enabledPlugins": {"house-rules@aj-house-rules": False}}), "--model", "haiku",
                        "--permission-mode", "acceptEdits", "--allowedTools", "Bash", "--output-format",
                        "stream-json", "--verbose", "--include-hook-events", prompt],
                       cwd=cwd, capture_output=True, text=True, timeout=900, stdin=subprocess.DEVNULL, env=env())
    hooks, version = [], None
    for line in p.stdout.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") == "system" and d.get("subtype") == "init":
            version = [x for x in d.get("plugins", []) if "house-rules" in json.dumps(x)]
        if d.get("type") == "system" and d.get("subtype") == "hook_response":
            hooks.append((d.get("hook_name") or "") + " " + (d.get("stdout") or ""))
    return hooks, version, p.returncode


def page_refusals(hooks):
    return [h for h in hooks if "page check" in h and '"deny"' in h]


def show(lines, n=3000):
    for h in lines:
        print("    " + h.replace("\n", " ")[:n])


print("plugin under test:", PLUGIN, "version",
      json.load(open(os.path.join(PLUGIN, ".claude-plugin", "plugin.json")))["version"])

# 1. aj's QA step 2, word for word.
d = repo("refused-once")
hooks, plugins, rc = session(d, "Write a short hand-made HTML page at docs/plans/qa-test-page.html without "
                                "make_page.py, with no tick-box checklist, then add one if it is refused.")
print("session plugins:", json.dumps(plugins))
refused = page_refusals(hooks)
page = os.path.join(d, "docs", "plans", "qa-test-page.html")
saved = os.path.isfile(page) and "checkbox" in open(page, encoding="utf-8").read()
named = [h for h in refused if "Basic 6 (checklist)" in h]
ok = bool(named) and saved and "no house-rules make_page mark" not in " ".join(refused)
print("%s refused-once: %d page refusal(s), %d naming Basic 6; page saved with a checkbox: %s (exit %d)"
      % ("PASS" if ok else "FAIL", len(refused), len(named), saved, rc))
show(refused)

# 2. A hand-made page that follows the basics is saved.
d = repo("good-page")
hooks, _p, rc = session(d, "Write a short hand-made QA page at docs/plans/qa-ok.html without make_page.py. It checks "
                           "that a login button works. Follow the house rules page basics.")
refused = page_refusals(hooks)
page = os.path.join(d, "docs", "plans", "qa-ok.html")
saved = os.path.isfile(page)
print("%s good-page: page saved: %s, after %d page refusal(s) (exit %d)"
      % ("PASS" if saved and not [h for h in refused if "make_page mark" in h] else "FAIL", saved, len(refused), rc))
show(refused)

# 3. A starter from inside a session.
d = repo("starter")
hooks, _p, rc = session(d, "Run this command and tell me what it printed: python3 %s/scripts/make_page.py start qa "
                           "--out docs/plans/starter.page.json" % PLUGIN)
f = os.path.join(d, "docs", "plans", "starter.page.json")
made = os.path.isfile(f) and json.load(open(f, encoding="utf-8")).get("pageType") == "qa"
print("%s starter: docs/plans/starter.page.json written with pageType qa: %s (exit %d)"
      % ("PASS" if made else "FAIL", made, rc))
