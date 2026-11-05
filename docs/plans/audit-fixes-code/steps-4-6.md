# Audit fixes, steps 4 to 6: the proposed code

This file holds the code proposed for steps 4, 5 and 6 of `docs/4-systems/audit-fixes.md`:
#480 (close the ways around the code lock), #481 (make each approval move only what aj named) and
#482 (tooling fixes and dead code). Steps 1 to 3 are in `steps-1-3.md` beside it. No source file has
been changed. Every **Now** block was copied from the code on `AjsAgent/audit-2026-11-05` at
`19b6d88`, and every line number was read on that commit.

**Findings covered (28):** D3, D4, A9, A7, D2, D9, A2, A10 and the issue text for D10 (step 4); D5,
D6, D7, D8 and U3 (step 5); A12, A16, A13, A14, A15, D11, D12, H5, A18, A19, A20 and H4 (step 6).

**Files touched (12):** `scripts/house_rules/design_loop.py`, `core.py`, `delegation.py`,
`safe_git.py`, `scripts/make_page.py`, `scripts/clarity.py`, `scripts/hook.py`,
`scripts/plain_docs_check.py`, `tools/_plugin_sync.py`, `tools/force_update.py`, `tools/install.py`
and `tools/diff_parts.py`. Tests go into `scripts/checks/design_loop.py`, `checks/delegation.py`,
`checks/core.py` and `tools/verify_tools.py`. All `scripts/` paths are under
`claude-house-rules/plugins/house-rules/`.

**Size, counted from the blocks below by a script:** the **Now** blocks hold 141 lines and the
**Proposed** blocks hold 402, so about 260 lines are added. On top of that, A19 deletes the lines it
lists plus 63 blank lines, and A20 deletes the 304-line `tools/check_verify_inventory.py`. The test
code is not in these counts.

**How the proofs were run:** a scratch script fed each finding's payload to the real `hook.py`
(`commitgate`, `scope`, `closablemerge`, `agentcap` or `autosave`) in throwaway git repos, each with a
decisions log. The output is quoted under each finding. "By reading" means the case was not run.

## Where these steps touch steps 1 to 3

- **`_loop_write` and the stage file (A7, D9).** Step 3's U2 pushes the stage file after each
  approval, and step 3's U1 copies a branch's stage file. Both call or follow `_loop_write`. A7
  changes how it writes, and D9 moves the `labels` key out of the committed file. Build step 3 first,
  then apply these on top.
- **Shell command reading (A9).** Step 2's U6 changes how the guard in `safe_git.py` reads quoted text
  and heredocs. A9's new refusal lives in `design_loop.py`, not in the guard, and strips heredocs with
  the existing `_HEREDOC_RE`. If step 2 adds a shared quote stripper, A9 should use it instead.
- **`_GH_PREFIX` and issue recording (D11).** Step 3's U2b widens `_GH_ISSUE_CREATE_RE` through
  `_GH_PREFIX`. D11 only changes how labels are read from a matched command, so the two don't clash.
  A label set from a shell variable (`--label "$L"`) will read as unlabelled after D11.
- **`_RELAYED_PROMPT_RE` (D2).** Step 1's D1 adds markers in `core.py`. D2 changes the approval
  patterns in `design_loop.py`, which only see prompts that D1 has already let through.
- **`safe_git.py` line numbers (A19, A15, A7).** The blank-line clean-up shifts every line number in
  `safe_git.py`, so it goes last, after steps 1 and 2 have landed there.
- **Atomic writes (A7 and A8).** Step 1's A8 gives `tools/install.py` a temp-file-and-`os.replace`
  write. A7 adds `core._write_atomic` for the plugin's own state files. `tools/install.py` can't
  import the plugin, so the two stay separate.

---

## Step 4 (#480): close the ways around the code lock

### D3. A write to the old `.git/house-rules-loop.json` opens Build in a new project

**File:** `scripts/house_rules/design_loop.py:405-457` (`_loop_read` reads the old path at
`:410-411`, and `_loop_file_refusal` compares one path at `:449`).

**Now:**

```python
    want = os.path.normcase(os.path.abspath(_loop_path(git_dir)))
    for p in paths:
        if isinstance(p, str) and p:
            p = p if os.path.isabs(p) else os.path.join(cwd, p)
            if os.path.normcase(os.path.abspath(p)) == want:
```

**Proposed:**

```python
    # D3: the old place in the git directory is still read when .claude/ has no stage file, so it is the stage file too.
    want = {os.path.normcase(os.path.abspath(x)) for x in (_loop_path(git_dir), os.path.join(_loop_dir(git_dir), LOOP_FILE))}
    for p in paths:
        if isinstance(p, str) and p:
            p = p if os.path.isabs(p) else os.path.join(cwd, p)
            if os.path.normcase(os.path.abspath(p)) in want:
```

**Why this is enough:** the old file is read only when `.claude/` has none, and with this change
neither path can be written with Write, Edit or a shell redirect. A9 below covers `cp` and `mv`.
Reading the old file stays, so a project that still has only the old file keeps its stage. This keeps
the first promise: only aj's messages move a stage.

**Test case** (`checks/design_loop.py`, beside the legacy cases at `:891-906`):

```python
_d3 = tempfile.mkdtemp(prefix="house-rules-d3-", dir=_FIXTURE_ROOT)
subprocess.run(["git", "init", "-q", _d3], check=True)
_d3_w = _wt_gate("Write", {"file_path": os.path.join(_d3, ".git", "house-rules-loop.json"), "content": "{}"}, _d3)[0]
_d3_sh = _wt_bash("echo '{\"stage\": \"build\"}' > .git/house-rules-loop.json", _d3)[0]
_loop_cases.append(("D3: a Write or a shell redirect into the old .git stage file is refused",
                    _d3_w == "deny" and _d3_sh == "deny"))
```

**Proved on the current code:** in a fresh repo, the Write of `.git/house-rules-loop.json` printed
`(no output)`, so no decision. After the file said `"stage": "build"`, the Write of `src/a.py` also
printed `(no output)`, so it was allowed.

### D4. `.claude/settings.json`, a helper's worktree and code under `docs/` are open in every stage

**File:** `scripts/house_rules/design_loop.py:161` and `:187-198` (`_is_source_path`). This function
also decides H5, so both findings are fixed here.

**Now:**

```python
_ISSUE_EDIT_ALLOWED_TOPS = ("docs", ".claude")
```

```python
def _is_source_path(fp, cwd, top):
    """The commitgate test: is `fp` a source file of the checkout at `top`? False for a path
    outside it, docs/, .claude/, any .md file and the tracker files."""
    if not os.path.isabs(fp):
        fp = os.path.join(cwd, fp)
    try:
        rel = os.path.relpath(os.path.normcase(os.path.abspath(fp)), os.path.normcase(top))
    except ValueError:
        rel = ".."  # another drive: outside the project
    parts = rel.replace("\\", "/").split("/")
    return not (parts[0] == ".." or parts[0] in _ISSUE_EDIT_ALLOWED_TOPS or rel.lower().endswith(".md")
                or os.path.basename(rel) in (ISSUES_FILE, LOOP_FILE))
```

**Proposed:**

```python
# D4: under docs/ only code is locked; H5: notes and data files are open everywhere, like .md.
_CODE_EXTS = (".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".sh", ".bash", ".ps1", ".rb", ".bat",
              ".cmd", ".cs", ".go", ".rs", ".java", ".c", ".cpp", ".h")
_OPEN_EXTS = (".md", ".txt", ".csv", ".tsv")
```

```python
def _is_source_path(fp, cwd, top):
    """The commitgate test: is `fp` a source file of the checkout at `top`? False for a path outside it,
    any .md, .txt, .csv or .tsv file, the tracker files, and docs/ or .claude/ files that are not code.
    .claude/settings*.json is locked (it can switch the loop off), and a path inside
    .claude/worktrees/<name>/ is judged as if from that worktree, which is a whole checkout (D4, H5)."""
    if not os.path.isabs(fp):
        fp = os.path.join(cwd, fp)
    try:
        rel = os.path.relpath(os.path.normcase(os.path.abspath(fp)), os.path.normcase(top))
    except ValueError:
        rel = ".."  # another drive: outside the project
    parts = rel.replace("\\", "/").split("/")
    if parts[:2] == [".claude", "worktrees"] and len(parts) > 3:
        parts = parts[3:]
    name, low = parts[-1], "/".join(parts).lower()
    if parts[0] == ".." or low.endswith(_OPEN_EXTS) or name in (ISSUES_FILE, LOOP_FILE):
        return False
    if parts[0] == ".claude":
        return name.lower().startswith("settings") and low.endswith(".json")
    if parts[0] == "docs":
        return low.endswith(_CODE_EXTS)
    return True
```

The constant `_ISSUE_EDIT_ALLOWED_TOPS` is then unused (grep finds it only at `:161` and `:197`), so it
is deleted. The refusal text at `:1051` changes from "docs/, .claude/ and .md files stay open" to
"docs/ pages, .claude/ files other than settings, and .md, .txt and .csv files stay open".

**Why this is enough:** the three proved holes each get one rule. `.claude/settings.json` is locked,
a worktree's source is judged like the main checkout's source, and code files under `docs/` are
locked. Pages (`.html`, `.page.json`), images and other `.claude/` state stay open, so designs can
still be written in the Design stage. This keeps the second promise: no code before an approved
build plan. `.json` stays locked outside `docs/` and `.claude/`, because `package.json` and
`tsconfig.json` change how a build runs. That is narrower than H5 asked for, and it is listed under
"Not decided".

**Test case** (`checks/design_loop.py`, after `:622`, where the stage is Design):

```python
_loop_cases.append(("D4: .claude/settings.json, a worktree's source file and code under docs/ are locked",
                    _loop_edit(".claude/settings.json") == _loop_edit(".claude/settings.local.json")
                    == _loop_edit(".claude/worktrees/agent-1/src/a.py") == _loop_edit("docs/tool.py") == "deny"))
_loop_cases.append(("D4/H5: pages, .claude/ state, a worktree's .md and plain data files stay open",
                    _loop_edit("docs/plans/x.page.json") == _loop_edit(".claude/x.json")
                    == _loop_edit(".claude/worktrees/agent-1/README.md") == _loop_edit("notes.txt")
                    == _loop_edit("data.csv") == "allow"))
```

**Proved on the current code:** in the Plan stage, Writes of `.claude/settings.json`, `docs/tool.py`
and `.claude/worktrees/agent-1/src/a.py` each printed `(no output)`. The control Write of `src/a.py`
was refused with `"permissionDecision":"deny"`.

### A9. `cp`, `mv` or `git checkout REV --` can overwrite the stage file

**File:** `scripts/house_rules/design_loop.py:441-442`, the shell branch of `_loop_file_refusal`.

**Now:**

```python
    elif data.get("tool_name") in _SHELL_TOOLS and isinstance(ti.get("command"), str):
        paths = _script_write_targets(_apply_assigns(ti["command"]))[0]
```

**Proposed:**

```python
    elif data.get("tool_name") in _SHELL_TOOLS and isinstance(ti.get("command"), str):
        if _loop_file_shell_write(ti["command"]):
            return ("House rules, design loop: this command names %s and isn't a read, `git add` or `git commit`, "
                    "so it could overwrite the stage. Only aj's approval messages move the stage. To switch the "
                    "loop off: HOUSE_RULES_LOOP=off." % LOOP_FILE)
        paths = _script_write_targets(_apply_assigns(ti["command"]))[0]
```

```python
# A9: commands that only read a file, and the git steps that save it. Anything else naming the stage file is refused.
# sed, awk, echo and printf are here because their writes (sed -i, a > redirect) are caught by _script_write_targets.
_LOOP_READERS = {"cat", "head", "tail", "less", "more", "grep", "rg", "jq", "wc", "ls", "stat", "file", "diff",
                 "sed", "awk", "echo", "printf"}
_LOOP_GIT_READS = {"add", "commit", "diff", "log", "show", "status", "blame"}
_LOOP_JSON_READ_RE = re.compile(r"json\.load\(\s*open\(")
_LOOP_PY_WRITE_RE = re.compile(r"shutil|os\.(?:replace|rename|remove)|\.write|json\.dump\b|copy", re.IGNORECASE)


def _loop_file_shell_write(cmd):
    """A9: True when a shell statement names the stage file and is not a read-only command, `git add` or
    `git commit`. Python or node count as a read only when they json.load the file and write nothing."""
    import shlex
    for stmt in re.split(r"&&|\|\||;|\n|\|", _HEREDOC_RE.sub("", cmd)):
        if LOOP_FILE not in stmt:
            continue
        try:
            words = [w for w in shlex.split(stmt) if "=" not in w.split("/")[0] and w not in ("sudo", "env", "time")]
        except ValueError:
            return True  # unbalanced quotes around the stage file's name: refuse rather than guess
        first = os.path.basename(words[0]) if words else ""
        if first in _LOOP_READERS:
            continue
        if first == "git":
            rest = words[1:]
            while rest and rest[0].startswith("-"):  # git's own options, such as -C <path>
                rest = rest[2:] if rest[0] in ("-C", "-c") else rest[1:]
            if rest and rest[0] in _LOOP_GIT_READS:
                continue
        if re.match(r"(?:python3?|py|node)(?:\.exe)?$", first) and _LOOP_JSON_READ_RE.search(stmt) \
                and not _LOOP_PY_WRITE_RE.search(stmt):
            continue
        return True
    return False
```

**Why this is enough:** the audit's three forms (`cp`, `mv` and `git checkout REV --`) are refused
because none of them starts with a read-only command. The commands sessions run every day still pass:
`cat` and `python3 -c "json.load(open(...))"` to read the file, and `git add` and `git commit` to
save it. A `git show REV:file > x` redirect already goes through `_script_write_targets`. This keeps
the first promise.

**Test case** (`checks/design_loop.py`, beside `_stage_sh` at `:890`):

```python
_a9 = [_wt_bash(c)[0] for c in ("cp /tmp/x.json .claude/house-rules-loop.json",
                                "mv x .claude/house-rules-loop.json",
                                "git checkout HEAD~3 -- .claude/house-rules-loop.json")]
_a9_ok = [_wt_bash(c)[0] for c in ("cat .claude/house-rules-loop.json",
                                   "git add .claude/house-rules-loop.json && git commit -m x",
                                   "python3 -c \"import json; print(json.load(open('.claude/house-rules-loop.json')))\"")]
_loop_cases.append(("A9: cp, mv and git checkout -- onto the stage file are refused; reads and git add/commit are not",
                    _a9 == ["deny"] * 3 and "deny" not in _a9_ok))
```

**Proved on the current code:** in the Plan stage, both
`cp /tmp/x.json .claude/house-rules-loop.json` and
`git checkout HEAD~3 -- .claude/house-rules-loop.json` printed `(no output)` from `commitgate`.

### A7. A half-written stage file switches the code lock off

**File:** `scripts/house_rules/design_loop.py:109-111` (`_issues_write`), `:425-429` (`_loop_write`)
and `:1982-1984` (`_page_blocks`); `delegation.py:907-911` (`_agentcap_save`, which shares one temp
name across processes) and `:1215-1217` (`_autosave_write`); `safe_git.py:550-553` and `:571-574`
(the rerun counts); `core.py:2198-2203` (`_waiting_save`); and `scripts/make_page.py:410-412` (the
stage file's `qa_page` key).

**Now** (`_loop_write`; the other eight writers have the same shape):

```python
def _loop_write(git_dir, state):
    path = _loop_path(git_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f)
```

**Proposed:** one helper in `core.py`. A name that starts with `_` isn't brought in by `from house_rules.core import *`, so `_write_atomic` is added to the explicit `from house_rules.core import (...)` list in `design_loop.py`, `delegation.py` and `safe_git.py`:

```python
def _write_atomic(path, text):
    """A7: write `text` so a reader never sees a half-written file: a temp file named for this process, then
    os.replace, which is atomic on one filesystem. The temp file is removed if the write fails."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
```

The callers each become one line:

```python
def _issues_write(git_dir, state):
    _write_atomic(os.path.join(git_dir, ISSUES_FILE), json.dumps(state))
```

```python
def _loop_write(git_dir, state):
    _write_atomic(_loop_path(git_dir), json.dumps(state))
```

```python
        data[session_id] = {"mark": mark, "count": count}
        _write_atomic(path, json.dumps(data))
```

```python
def _agentcap_save(path, recs):
    _write_atomic(path, json.dumps({"agents": recs}))
```

```python
def _autosave_write(path, text):
    _write_atomic(path, text)
```

```python
        recs[key] = {"script": script, "head": head, "count": count + 1}
        _write_atomic(path, json.dumps({"records": recs}))
```

```python
            else:
                recs[key] = before
            _write_atomic(path, json.dumps({"records": recs}))
```

```python
def _waiting_save(path, entries):
    _write_atomic(path, json.dumps(entries, indent=1))
```

`make_page.py` doesn't import the plugin's `core`, so it gets the same two lines inline:

```python
    tmp = "%s.%d.tmp" % (stage, os.getpid())  # A7: never leave a half-written stage file
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, stage)
```

**Why this is enough:** a reader now sees either the old file or the new one, never an empty one, and
the process id in the temp name means two hooks never write the same temp file. This keeps the second
promise, because the lock no longer fails open in the middle of a write. Two hooks that read, change
and write at the same moment can still lose one update; that needs a lock file, and it is listed
under "Not decided".

**Test case** (`checks/core.py`):

```python
import importlib
_core = importlib.import_module("house_rules.core")
_aw = os.path.join(_FIXTURE_ROOT, "atomic", "state.json")
_core._write_atomic(_aw, '{"a": 1}')
_core._write_atomic(_aw, '{"a": 2}')
report("PASS" if (json.load(open(_aw, encoding="utf-8")) == {"a": 2}
                  and os.listdir(os.path.dirname(_aw)) == ["state.json"]) else "FAIL",
       "A7: _write_atomic replaces the file whole and leaves no temp file behind")
```

**Proved on the current code:** by reading. The audit ran the empty-file case and got "the
design-loop lock is off for this call".

### D2. A question, or a "don't", that quotes an approval moves the stage

**File:** `scripts/house_rules/design_loop.py:371-380`.

**Now:**

```python
_LOOP_DESIGN_RE = re.compile(r"\bdesign\s+approved\s*:?[ \t]*(\S[^\n]*)", re.IGNORECASE)


_LOOP_PLAN_RE = re.compile(r"\bbuild\s+plan\s+approved\s*:?[ \t]*(\S[^\n]*)", re.IGNORECASE)


_LOOP_QA_RE = re.compile(r"\bqa\s+(passed|failed)\s*:?[ \t]*(\S[^\n]*)", re.IGNORECASE)


_LOOP_SKIP_RE = re.compile(r"\bskip\s+design\b", re.IGNORECASE)
```

**Proposed:**

```python
# D2: an approval counts only where aj's sentence starts with it (a line start, or after . ! , ; or a tag such as
# <message>, with optional quote marks or a bullet), and not when it runs into a question mark.
_LOOP_LEAD = r"(?:^|[.!,;][ \t]+)(?:<[\w/]+>)?[ \t>\"'*\-]*"
_LOOP_NOT_ASKED = r"(?![^\n.!]*\?)"


_LOOP_DESIGN_RE = re.compile(r"(?m)" + _LOOP_LEAD + r"design\s+approved" + _LOOP_NOT_ASKED
                             + r"\s*:?[ \t]*(\S[^\n]*)", re.IGNORECASE)


_LOOP_PLAN_RE = re.compile(r"(?m)" + _LOOP_LEAD + r"build\s+plan\s+approved" + _LOOP_NOT_ASKED
                           + r"\s*:?[ \t]*(\S[^\n]*)", re.IGNORECASE)


_LOOP_QA_RE = re.compile(r"(?m)" + _LOOP_LEAD + r"qa\s+(passed|failed)" + _LOOP_NOT_ASKED
                         + r"\s*:?[ \t]*(\S[^\n]*)", re.IGNORECASE)


_LOOP_SKIP_RE = re.compile(r"(?<!don't )(?<!dont )(?<!do not )(?<!not )\bskip\s+design\b" + _LOOP_NOT_ASKED,
                           re.IGNORECASE)
```

**Why this is enough:** the proved example, "What would happen if I said Design approved: login
page? Don't do it yet.", fails both tests: the phrase follows "said", and it runs into "?". "Please
don't skip design" fails the look-behind. The #307 message "Design approved: importer.  Build plan
approved: Importer" still finds both phrases, because the second follows ". ". This keeps the first
promise, because a message aj didn't mean as an approval moves nothing.

**Test case** (`checks/design_loop.py`, with the `_ma_` helpers at `:1303-1323`):

```python
_ma_set({"feature": "", "stage": "design"})
_n, _s = _ma_say("What would happen if I said Design approved: login page? Don't do it yet.")
_ma_set({"feature": "x", "stage": "plan"})
_n2, _s2 = _ma_say("Please don't skip design on this one.")
_ma_set({"feature": "", "stage": "design"})
_n3, _s3 = _ma_say("<message>Thanks. Design approved: login page 1A</message>")
report("PASS" if (_s["stage"] == "design" and not _s2.get("skip") and _s3["stage"] == "plan"
                  and _s3.get("feature") == "login page") else "FAIL",
       "design loop (D2): a question or a don't moves nothing; an approval after a sentence or a tag still counts")
```

**Proved on the current code:** "What would happen if I said Design approved: login page? Don't do
it yet." gave `stage after: plan feature: login page`. "Please don't skip design on this one." gave
`skip after "Please don't skip design": True`.

### D9. Switching to an old branch brings back its stage, and its labels pass the check when GitHub can't be read

**File:** `scripts/house_rules/design_loop.py:405-429` (`_loop_read`, `_loop_write`) and
`:566-569` (the fallback in `_loop_labels`).

**Now:**

```python
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        why = "Labels were taken from the changes this hook recorded, because the GitHub read failed (%s)." % exc
    recorded = state.get("labels") if isinstance(state.get("labels"), dict) else {}
    return {k: recorded.get(k) for k in keys}, why
```

```python
    return dict(fresh, **data), None
```

**Proposed:** the recorded labels move out of the committed stage file into the common git
directory, which no branch switch can bring back. `_loop_labels` is unchanged; `_loop_read` and
`_loop_write` change. The `_loop_write` below includes A7's atomic write:

```python
LOOP_LABELS_CACHE = "house-rules-labels.json"  # D9: facts about GitHub, kept out of the branch


def _loop_labels_cache(git_dir):
    """The label changes this hook recorded in this clone, or {} when there are none or the file can't be read."""
    try:
        data = json.loads(_read_text(os.path.join(_loop_dir(git_dir), LOOP_LABELS_CACHE)))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}
```

```python
    state = dict(fresh, **data)
    state["labels"] = _loop_labels_cache(git_dir)  # D9: never the labels an old branch committed
    return state, None
```

```python
def _loop_write(git_dir, state):
    if isinstance(state.get("labels"), dict):
        _write_atomic(os.path.join(_loop_dir(git_dir), LOOP_LABELS_CACHE), json.dumps(state["labels"]))
    _write_atomic(_loop_path(git_dir), json.dumps({k: v for k, v in state.items() if k != "labels"}))
```

**Why this is enough:** the proved bypass needed two things: the old branch's stage, and the old
branch's recorded `in progress` labels, used when the GitHub read failed. After this change the
labels come from this clone's own record, which holds the latest change this hook saw, whichever
branch is checked out. A fresh clone with no record, where GitHub can't be read, gets "no labels
known", so its Build edits are refused with the reason. The stage itself still travels with the
branch, as #265 chose. This keeps the second promise.

**Test case:** the fixture at `checks/design_loop.py:908-913` writes `labels` into the stage file. It
changes to write them into the cache instead, and the cases at `:689-706` read the cache:

```python
def _loop_cached_labels(d=None):
    try:
        return json.load(open(os.path.join(d or _loop_dir, ".git", "house-rules-labels.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return {}
```

```python
_d9 = tempfile.mkdtemp(prefix="house-rules-d9-", dir=_FIXTURE_ROOT)
subprocess.run(["git", "init", "-q", _d9], check=True)
os.makedirs(os.path.join(_d9, ".claude"))
json.dump({"feature": "old", "stage": "build", "skip": False, "approvals": [],
           "issues": [{"repo": "o/r", "number": 1, "labelled": True}],
           "labels": {"o/r#1": ["in progress"]}},
          open(os.path.join(_d9, ".claude", "house-rules-loop.json"), "w", encoding="utf-8"))
_d9_env = dict(_loop_env, HOUSE_RULES_LOOP_LABELS_FILE=os.path.join(_FIXTURE_ROOT, "no-such-labels.json"))
_d9_out = run_hook("commitgate", json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Edit", "session_id": "d9",
                   "cwd": _d9, "tool_input": {"file_path": os.path.join(_d9, "app.py")}}), env=_d9_env)[1]
_loop_cases.append(("D9: a committed stage file's own labels don't open Build when GitHub can't be read",
                    '"deny"' in _d9_out and "no labels known" in _d9_out))
```

**Proved on the current code:** by reading for this exact payload. The deep dive's run switched to an
old branch with `git switch old-build`; with the GitHub read failing, the source edit was allowed.

### A2. Any merged pull request unlocks closing any QA-passed issue

**File:** `scripts/house_rules/design_loop.py:2119-2130` (`event_closablemerge`) and `:1256-1259`
(`_loop_record_labels`, where an opened pull request is seen).

**Now:**

```python
        open_ = [e for e in state.get("closable", []) if isinstance(e, dict) and e.get("merged_pr") is None]
        if not open_:
            return 0
        repo, number = merged
        for e in open_:
            e["merged_pr"] = {"repo": repo, "number": number, "at": int(time.time())}
        _loop_write(git_dir, state)
        trace("house-rules plugin: merge of %s#%d stamped %d closable record(s)." % (repo, number, len(open_)))
```

**Proposed:** when a pull request is opened in a session, its `Refs #N` and `Part of #N` links are
recorded. A merge stamps only records holding an issue that the merged pull request links. A pull
request opened elsewhere has its body read once with `gh pr view`. This block also carries U3's note
(step 5):

```python
_PR_REF_RE = re.compile(r"\b(?:Refs|Part of)\s+([\w.-]+/[\w.-]+)?#(\d+)", re.IGNORECASE)
LOOP_PR_BODIES_ENV = "HOUSE_RULES_LOOP_PR_BODIES_FILE"  # tests: {"owner/repo#n": body}; a missing file is a failed read


def _pr_refs(body, repo):
    """A2: [[repo, number]] that a pull request body links with `Refs #N` or `Part of #N`; a bare #N is in `repo`."""
    return [[(r or repo).lower(), int(n)] for r, n in _PR_REF_RE.findall(body or "")]


def _merged_pr_refs(state, repo, number):
    """(refs, problem) for the merged pull request: the links recorded when it was opened in a session, else
    its body read once from GitHub. problem says why nothing could be read ("" when it could)."""
    rec = state.get("pr_refs") if isinstance(state.get("pr_refs"), dict) else {}
    hit = rec.get("%s#%d" % (repo.lower(), number)) if repo else next(
        (v for k, v in rec.items() if k.endswith("#%d" % number)), None)
    if isinstance(hit, list):
        return hit, ""
    stand_in = os.environ.get(LOOP_PR_BODIES_ENV)
    try:
        if stand_in:
            with open(stand_in, "r", encoding="utf-8") as f:
                return _pr_refs(json.load(f)["%s#%d" % (repo, number)], repo), ""
        if not repo or not shutil.which("gh"):
            raise RuntimeError("no repo is named" if not repo else "gh is not installed")
        import subprocess
        proc = subprocess.run(["gh", "pr", "view", str(number), "--repo", repo, "--json", "body", "--jq", ".body"],
                              capture_output=True, text=True, timeout=LOOP_GH_SECONDS)
        if proc.returncode != 0:
            raise RuntimeError(((proc.stderr or "").strip().splitlines() or ["gh exited %d" % proc.returncode])[0])
        return _pr_refs(proc.stdout, repo), ""
    except Exception as exc:
        return [], "its body could not be read (%s: %s)" % (type(exc).__name__, exc)
```

In `event_closablemerge`, replacing the **Now** lines:

```python
        open_ = [e for e in state.get("closable", []) if isinstance(e, dict) and e.get("merged_pr") is None]
        repo, number = merged
        notes = []
        if open_:
            refs, why = _merged_pr_refs(state, repo, number)
            hit = [e for e in open_ if any(isinstance(i, dict) and i.get("number") == n
                                           and _close_repo_match(r, i.get("repo", ""))
                                           for i in e.get("issues") or [] for r, n in refs)]
            for e in hit:
                e["merged_pr"] = {"repo": repo, "number": number, "at": int(time.time())}
            if hit:
                _loop_write(git_dir, state)
            else:
                notes.append("house-rules: the merge of %s#%d stamped no closable record, because %s." % (
                    repo, number, why or "it links none of the QA-passed issues with `Refs #N`"))
            trace("house-rules plugin: merge of %s#%d stamped %d closable record(s)." % (repo, number, len(hit)))
        if state.get("stage") == "qa":  # U3
            notes.append('Design loop: pull request %s#%d merged while "%s" is in QA, so the stage file still '
                         'says QA. Ask aj for "QA passed: %s" or "QA failed: %s"; the stage moves only on their word.'
                         % ((repo, number) + (state.get("feature") or "this feature",) * 3))
        if notes:
            emit({"systemMessage": " ".join(notes),
                  "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": " ".join(notes)}})
```

In `_loop_record_labels`, beside the existing `if pr and state["stage"] == "build":` at `:1257`:

```python
        if pr:  # A2: what this pull request links, so its merge stamps only those issues
            resp = data.get("tool_response")
            url = re.search(r"github\.com/([\w.-]+/[\w.-]+)/pull/(\d+)", resp if isinstance(resp, str) else json.dumps(resp))
            ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
            body = ti.get("body") if isinstance(ti.get("body"), str) else ti.get("command") or ""
            fm = _PR_BODY_FILE_RE.search(body) if "command" in ti else None
            if fm and fm.group(1).strip("\"'") != "-":
                try:
                    body = _read_text(os.path.join(_payload_cwd(payload), fm.group(1).strip("\"'")))
                except OSError:
                    pass  # the guard already read this file before the command ran; refs from the command text stand
            if url:
                state.setdefault("pr_refs", {})["%s#%s" % (url.group(1).lower(), url.group(2))] = _pr_refs(body, url.group(1))
```

**Why this is enough:** a merge can no longer unlock issues that its pull request doesn't name. The
`Refs #N` links are already required by `_issues_guard` (`:1572-1575`), so every pull request opened
in a session has them. A pull request opened outside a session is read once from GitHub. When that
read fails, nothing is stamped and the note says why. This guards aj's QA: no issue closes before
aj has passed QA and a pull request naming it has merged.

**Test case** (`checks/design_loop.py`): the fixture `_cl_open` at `:1015` gains
`"issues": [{"repo": "o/r", "number": 7}]`, and `_cl_set` writes
`"pr_refs": {"o/r#12": [["o/r", 7]], "o/r#14": [["o/r", 7]], "o/r#16": [["o/r", 7]], "ajw2003/ajsclaudecodetools#373": [["ajw2003/ajsclaudecodetools", 7]]}`,
so the existing merge cases still stamp. The new cases are:

```python
_cl_set({"stage": "done", "closable": [dict(_cl_open)], "pr_refs": {"other/repo#99": [["other/repo", 1]]}})
_o = _cl_merge("mcp__github__merge_pull_request", {"owner": "other", "repo": "repo", "pullNumber": 99}, {"merged": True})
_cl_cases.append(("A2: a merge whose pull request links none of the QA-passed issues stamps nothing, and says so",
                  _cl_state()["closable"][0]["merged_pr"] is None and "stamped no closable record" in _o))
_cl_set({"stage": "done", "closable": [dict(_cl_open)]})
_bodies = os.path.join(_FIXTURE_ROOT, "pr-bodies.json")
json.dump({"o/r#21": "Refs #7"}, open(_bodies, "w", encoding="utf-8"))
_cl_merge("mcp__github__merge_pull_request", {"owner": "o", "repo": "r", "pullNumber": 21}, {"merged": True},
          env=dict(_cl_env, HOUSE_RULES_LOOP_PR_BODIES_FILE=_bodies))
_cl_cases.append(("A2: a pull request opened elsewhere is read once, and its Refs #7 stamps #7's record",
                  (_cl_state()["closable"][0]["merged_pr"] or {}).get("number") == 21))
```

**Proved on the current code:** a closable record for `own/repo#5`, then a merge of the unrelated
`other/repo#99`, gave `merged_pr after: {'repo': 'other/repo', 'number': 99, 'at': 1793862526}`.

### A10. Three helpers launched together all get past the two-helper cap

**File:** `scripts/house_rules/delegation.py:902-904` (`_agentcap_live`), `:931-933` (the add in
`_agentcap_update`) and `:967-968` (the allow in `event_agentcap`).

**Now:**

```python
def _agentcap_live(recs, now=None):
    now = time.time() if now is None else now
    return [r for r in recs if now - r["start"] <= AGENT_STALE_SECONDS]
```

```python
        if add:
            recs = [r for r in recs if r.get("id") != add[0]]
            recs.append({"id": add[0], "type": add[1], "start": time.time()})
```

```python
            if len(recs) < AGENT_CAP:
                return 0
```

**Proposed:**

```python
AGENT_PENDING_SECONDS = 120  # A10: a launch the cap allowed holds a place until its SubagentStart arrives


def _agentcap_live(recs, now=None):
    now = time.time() if now is None else now
    return [r for r in recs if now - r["start"] <= (AGENT_PENDING_SECONDS if str(r.get("id", "")).startswith("pending:")
                                                    else AGENT_STALE_SECONDS)]
```

```python
        if add:
            recs = [r for r in recs if r.get("id") != add[0]]
            pending = [r for r in recs if str(r.get("id", "")).startswith("pending:")]
            if pending and not str(add[0]).startswith("pending:"):
                recs.remove(min(pending, key=lambda r: r["start"]))  # A10: this agent takes its launch's place
            recs.append({"id": add[0], "type": add[1], "start": time.time()})
```

```python
            if len(recs) < AGENT_CAP:
                note = _agentcap_update(add=("pending:%s" % (data.get("tool_use_id") or time.time()), "starting"))
                if note:
                    emit({"systemMessage": "house-rules: " + note})
                return 0
```

**Why this is enough:** the count now goes up when a launch is allowed, not seconds later when the
helper starts, so a third launch made before the first two have started is refused. A launch that
never starts, because another hook refused it, holds its place for two minutes rather than the
45-minute stale limit. Two launch checks running at the same instant can still both read the old
count. That needs a lock file, and it is listed under "Not decided". This rule isn't one of the three
promises; it enforces the house rule "at most two helpers".

**Test case** (`checks/delegation.py`, after `:1136`):

```python
if os.path.exists(_cap_state):
    os.remove(_cap_state)
_c10 = [_cap_spawn() for _ in range(3)]
commit_case(
    "agentcap (A10): three launches before any helper starts - the third is denied",
    not _cap_denied(_c10[0][1]) and not _cap_denied(_c10[1][1]) and _cap_denied(_c10[2][1]),
    "outs %r" % [o[1][:80] for o in _c10],
)
_cap_start("capP")
commit_case(
    "agentcap (A10): a starting helper takes its launch's placeholder, so the count stays two",
    len(json.load(open(_cap_state, encoding="utf-8"))["agents"]) == 2,
    "state %r" % open(_cap_state, encoding="utf-8").read()[:200],
)
```

**Proved on the current code:** three `agentcap` calls in a row on an empty state file each printed
`(no output)`, so all three were allowed.

### D10. Shell writes to source files are only reported (issue text only)

D10 stays with the restructure, as #309 decided. Step 4 opens this issue:

**Title:** Refuse shell writes to source files outside Build, as the Write and Edit tools are refused

**Body:**

> The design loop refuses Write, Edit and NotebookEdit on source files outside the Build stage, but
> a shell command that writes a source file is only reported (`design_loop.py:1040-1047`, switched
> to report-only in #309). The deep dive of 2026-11-05 (finding 10,
> `docs/audits/2026-11-05-design-loop-deep-dive.md`) proved that `cat > src/a.py <<'X' ... X` in the Plan
> stage goes through with a report. That makes it the largest remaining way around the code lock.
> It was switched off because the refusal also stopped writes to `docs/` and `.claude/`, which are
> meant to stay open. After step 4 of #476, `_is_source_path` tells those paths apart properly, so the
> refusal can come back for source paths only.
>
> ### Depends on
>
> #480 (step 4 of #476), for the new `_is_source_path`, and the plugin restructure's plan (#306).
>
> ### Depended on by
>
> Nothing.
>
> ### Done when
>
> A shell write to a source file outside Build is refused with the same reason as a Write. The
> `docs/` and `.claude/` writes from #309's incident 4 still pass. There is a `verify.py` case for each.
>
> Opened by AJ's agent

---

## Step 5 (#481): make each approval move only what aj named

### D5. Approving the design again in Build loses the feature's issues

**File:** `scripts/house_rules/design_loop.py:697-702` (pieces applied in stage order) and `:817-822`
(the design branch of `_loop_apply_one`).

**Now:**

```python
    notes = [_loop_apply_one(state, piece, top) for _order, piece in sorted(pieces, key=lambda p: p[0])]
```

```python
            state["feature"], state["stage"], approval = name, "plan", ("Design approved", name)
            state["redo"] = False
            if not redo:
                _loop_keep_feature(state, feature, stage)  # #375: a feature in build or QA keeps its issues
                state["issues"] = []
                state.pop("qa_page", None); state.pop("qa_page_linked", None)  # #269: not the next feature's
```

**Proposed:**

```python
    notes = [_loop_apply_one(state, piece, top) for _order, piece in pieces]  # D5: in the order aj wrote them
```

```python
            same = stage in ("build", "qa") and _loop_same(name, feature)  # D5: an amended design, not a new feature
            state["feature"], state["stage"], approval = name, "plan", ("Design approved", name)
            state["redo"] = False
            if same:
                state.pop("qa_page", None); state.pop("qa_page_linked", None)  # the amended build gets a new QA page
            elif not redo:
                _loop_keep_feature(state, feature, stage)  # #375: a feature in build or QA keeps its issues
                state["issues"] = []
                state.pop("qa_page", None); state.pop("qa_page_linked", None)  # #269: not the next feature's
```

`_loop_same` is new in D6 below. The docstring of `_loop_apply_stage` at `:694-696` changes from "in
stage order" to "in the order aj wrote them".

**Why this is enough:** an amended design for the same feature keeps its issues and goes back to
Plan, so code stays locked until aj approves the build plan again. The existing issues count toward
that approval, so none need making again. "QA failed: feat. Design approved: feat" now applies the
failure first, so the redo is seen. This keeps the second promise, and it removes the forced
re-creation of issues.

**Test case** (`checks/design_loop.py`, `_ma_` helpers):

```python
_ma_set({"feature": "feat", "stage": "build", "issues": [{"repo": "o/r", "number": n, "labelled": True} for n in (1, 2)]},
        {"o/r#%d" % n: ["Feature", "in progress"] for n in (1, 2)})
_n, _s = _ma_say("Design approved: feat")
report("PASS" if (_s["stage"] == "plan" and [i["number"] for i in _s.get("issues", [])] == [1, 2]
                  and "feat" not in (_s.get("features") or {})) else "FAIL",
       "design loop (D5): a design approved again in Build goes to Plan and keeps the feature's issues")
_ma_set({"feature": "feat", "stage": "qa", "issues": [{"repo": "o/r", "number": n, "labelled": True} for n in (1, 2)]},
        {"o/r#%d" % n: ["Feature", "in progress"] for n in (1, 2)})
_n, _s = _ma_say("QA failed: feat. Design approved: feat")
report("PASS" if (_s["stage"] == "plan" and len(_s.get("issues", [])) == 2) else "FAIL",
       "design loop (D5): \"QA failed: X. Design approved: X\" is read in order - the redo keeps the issues")
```

**Proved on the current code:** "Design approved: feat" in Build gave `stage: plan issues: []
kept: ['feat']`.

### D6. The feature name in an approval is never checked

**File:** `scripts/house_rules/design_loop.py:778-783` (the build-plan branch) and `:826-829` (the QA
branch).

**Now:**

```python
    m = _LOOP_PLAN_RE.search(text)
    if m:
        name = _loop_name(m.group(1))
        if stage != "plan":
```

```python
                verdict, name = m.group(1).lower(), _loop_name(m.group(2))
                stored = _loop_stored(state, name)
                if stored is not None:
                    return _loop_stored_qa(state, stored, verdict, name, top)
```

**Proposed:**

```python
def _loop_same(a, b):
    """D6: True when two feature names agree, ignoring case and _loop_name's clean-up, or when one starts with the
    other as whole words ("background work tracking" and "background work tracking 1A except ...")."""
    x, y = _loop_name(a or "").lower(), _loop_name(b or "").lower()
    if not x or not y:
        return False
    short, longer = sorted((x, y), key=len)
    return longer == short or longer.startswith(short + " ")
```

```python
    m = _LOOP_PLAN_RE.search(text)
    if m:
        name = _loop_name(m.group(1))
        if stage == "plan" and not _loop_same(name, feature):
            return ('Design loop: aj wrote "Build plan approved: %s", but the feature in Plan is "%s", so nothing '
                    "moved. Ask aj to approve it by that name, or to approve a design for \"%s\" first."
                    % (name, feature, name))
        if stage != "plan":
```

```python
                verdict, name = m.group(1).lower(), _loop_name(m.group(2))
                stored = _loop_stored(state, name)
                if stored is not None:
                    return _loop_stored_qa(state, stored, verdict, name, top)
                if stage in ("build", "qa") and not _loop_same(name, feature):
                    return ('Design loop: aj wrote "QA %s: %s", but the feature in %s is "%s" and no kept feature has '
                            "that name, so nothing moved. Ask aj which feature they meant."
                            % (verdict, name, LOOP_STAGE_NAMES[stage], feature))
```

**Why this is enough:** an approval that names a different feature is refused with both names,
instead of moving the current one. The prefix rule keeps the long names aj really types. This keeps
the first promise: a stage moves only when aj names its feature.

**Test case** (`checks/design_loop.py`, `_ma_` helpers):

```python
_ma_set({"feature": "login", "stage": "plan", "issues": [{"repo": "o/r", "number": n, "labelled": True} for n in (1, 2)]},
        {"o/r#%d" % n: ["Feature", "in progress"] for n in (1, 2)})
_n, _s = _ma_say("Build plan approved: payments")
_n2, _s2 = _ma_say("Build plan approved: login 1A except keep the old flag")
report("PASS" if (_s["stage"] == "plan" and '"login"' in _n and _s2["stage"] == "build") else "FAIL",
       "design loop (D6): a build plan approval naming another feature moves nothing; a longer form of the name counts")
```

**Proved on the current code:** with "login" in Plan, "Build plan approved: payments" gave `stage:
build feature: login`. Measured against aj's real approvals in `.claude/house-rules-loop.json`, two
of the nine build-plan approvals would have been refused: "guard audit" after the design "guards
audit", and "plugin restructure 2.68.1 patch" after "plugin restructure direction".

### D7. "skip design" lasts too long, and the wrong edit can use it up

**File:** `scripts/house_rules/design_loop.py:858-860` (an approval is recorded) and `:887-889`
(the skip).

**Now:**

```python
    if approval:
        state.setdefault("approvals", []).append(
            {"stage": approval[0], "name": approval[1], "at": int(time.time())})
```

```python
    if _LOOP_SKIP_RE.search(text):
        state["skip"] = True
        return 'Design loop: aj wrote "skip design", so the next code edit goes through, then the lock is back.'
```

**Proposed:**

```python
    if approval:
        state["skip"] = False  # D7: a skip belongs to the stage it was typed in
        state.setdefault("approvals", []).append(
            {"stage": approval[0], "name": approval[1], "at": int(time.time())})
```

```python
    if _LOOP_SKIP_RE.search(text):
        if stage == "build":
            return ('Design loop: aj wrote "skip design", but the stage is Build, so code edits are already open '
                    "and nothing was stored.")
        state["skip"] = True
        return 'Design loop: aj wrote "skip design", so the next code edit goes through, then the lock is back.'
```

**Why this is enough:** a skip typed in Build is no longer stored to be found after QA, and any stage
move clears a skip nobody has used. The other half of D7, where a NotebookEdit made first uses up the
skip, is left as it is. Every code edit tool is a code edit, and the skip is "the next code edit", as
its message says. This keeps the second promise.

**Test case:**

```python
_ma_set({"feature": "x", "stage": "build", "issues": [{"repo": "o/r", "number": 1, "labelled": True}]},
        {"o/r#1": ["in progress"]})
_n, _s = _ma_say("skip design")
_ma_set({"feature": "x", "stage": "plan", "skip": True,
         "issues": [{"repo": "o/r", "number": n, "labelled": True} for n in (1, 2)]},
        {"o/r#%d" % n: ["in progress"] for n in (1, 2)})
_n2, _s2 = _ma_say("Build plan approved: x")
report("PASS" if (not _s.get("skip") and "already open" in _n and _s2["stage"] == "build" and not _s2["skip"])
       else "FAIL", "design loop (D7): skip design in Build stores nothing, and a stage move clears an unused skip")
```

**Proved on the current code:** "skip design" typed in Build gave `skip stored in Build: True`.

### D8. Any claude.ai artifact link counts as the QA page

**File:** `scripts/house_rules/design_loop.py:1877-1888`.

**Now:**

```python
_QA_ARTIFACT_RE = re.compile(r"https://claude\.ai/artifact/\S+|claude\.ai/code/artifact/\S+", re.IGNORECASE)
```

```python
    if not (page and (in_reply or _QA_ARTIFACT_RE.search(reply))):
        return False
```

**Proposed:** `_QA_ARTIFACT_RE` is deleted (grep finds it only at `:1877` and `:1887`), and:

```python
    if not (page and in_reply):  # D8: the reply names this feature's QA page; a bare artifact link proves nothing
        return False
```

The fix text in `_check_qa_page` at `:1906-1908` ends "then name the page's file in the reply, beside
any link".

**Why this is enough:** a QA page now counts only when the reply names the page file recorded for
this feature. The page's own file name is specific to the feature (for example `rerun-limit-qa.html`).
The audit's other suggestion was to record the artifact link that `make_page.py` publishes. That isn't
possible, because `make_page.py` builds a file and publishes nothing. This keeps QA honest: aj is
handed the right page.

**Test case** (`checks/design_loop.py`, beside the #269 QA page cases):

```python
import importlib
_dl_mod = importlib.import_module("house_rules.design_loop")
_qa8 = {"qa_stage": "qa", "qa_page": "docs/plans/feat-qa.html", "reply": "QA page: https://claude" ".ai/artifact/abc",
        "cwd": _loop_dir, "qa_git_dir": os.path.join(_loop_dir, ".git")}
_loop_cases.append(("D8: a bare artifact link doesn't count as the QA page; the page's file name does",
                    _dl_mod._check_qa_page(dict(_qa8)) != ""
                    and _dl_mod._check_qa_page(dict(_qa8, reply="QA page: docs/plans/feat-qa.html")) == ""))
```

**Proved on the current code:** by reading `:1887`: `_QA_ARTIFACT_RE.search(reply)` alone is enough
to set `qa_page_linked`. The deep dive ran it with a made-up artifact link.

### U3. `main` still carries a merged feature's QA stage

**File:** the stage file on `origin/main`. `git show origin/main:.claude/house-rules-loop.json` reads
`qa rerun limit`, and that feature's pull request is merged.

**Now:** `event_closablemerge` stamps the closable records, and nothing else happens.

**Proposed:** the `if state.get("stage") == "qa":` note in A2's block above. When a pull request
merges while the feature is in QA, the model is told to ask aj for the QA verdict. The stage is never
moved by the merge itself.

**Why this is enough:** the plan in `docs/4-systems/audit-fixes.md` said "`main` gets no stage file
from a merged feature". That would mean the merge moves the stage to Done, so a merge, not aj's
message, would move a stage. It would break the first promise, so this proposal replaces it with the
note. The stage on `main` becomes true once aj answers. The plan's table line is corrected in the
same change.

**Test case:**

```python
_cl_set({"feature": "f", "stage": "qa", "closable": [], "issues": _cl_issues})
_o = _cl_merge("mcp__github__merge_pull_request", {"owner": "o", "repo": "r", "pullNumber": 30}, {"merged": True})
_cl_cases.append(("U3: a merge while the feature is in QA leaves the stage alone and asks for aj's verdict",
                  _cl_state()["stage"] == "qa" and "QA passed: f" in _o))
```

**Proved on the current code:** by reading `event_closablemerge` at `:2095-2134`, which never reads the
stage.

---

## Step 6 (#482): fix the wrong answers in the tooling and remove dead code

### A12. The version check "updates" a newer copy down

**File:** `scripts/house_rules/core.py:1327` and `:1338`.

**Now:**

```python
        if installed and market_version and installed != market_version:
```

```python
        elif not market_version and installed and github_version and installed != github_version:
```

**Proposed:**

```python
        if installed and market_version and _version_tuple(installed) < _version_tuple(market_version):
```

```python
        elif not market_version and installed and github_version and _version_tuple(installed) < _version_tuple(github_version):
```

**Why this is enough:** an update is suggested only when the installed copy is older, using
`_version_tuple` (`core.py:479`), which already exists. A branch build that is ahead of `main` is no
longer told it is out of date. The marketplace-against-GitHub comparison at `:1332` stays `!=`,
because a clone that differs from GitHub in either direction needs a sync.

**Test case** (`checks/core.py`, with the existing versioncheck stand-ins):

```python
report("PASS" if (_core._version_tuple("2.75.0") > _core._version_tuple("1.0.0")
                  and _core._version_tuple("2.10.0") > _core._version_tuple("2.9.9")) else "FAIL",
       "A12: versions compare as numbers, so 2.75.0 is newer than 1.0.0 and 2.10.0 newer than 2.9.9")
```

The full versioncheck case reuses the audit's run: installed 2.75.0 against a published 1.0.0 must
print no update command.

**Proved on the current code:** by reading. The full audit ran it: a running 2.75.0 against a
published 1.0.0 ran `claude plugin update`.

### A16. `force_update.py` can leave the plugin uninstalled without saying so

**File:** `tools/force_update.py:82-83`.

**Now:**

```python
    invoke_claude(["plugin", "uninstall", args.plugin], f"Uninstalling {args.plugin}")
    invoke_claude(["plugin", "install", args.plugin, "-y"], f"Reinstalling {args.plugin}")
```

**Proposed:**

```python
    invoke_claude(["plugin", "uninstall", args.plugin], f"Uninstalling {args.plugin}")
    try:
        invoke_claude(["plugin", "install", args.plugin, "-y"], f"Reinstalling {args.plugin}")
    except SystemExit as exc:
        raise SystemExit(f"{exc}\nThe plugin is now UNINSTALLED, so its guard hooks are off. "
                         f"Install it again with: claude plugin install {args.plugin} -y")
```

**Why this is enough:** the failure now says that the guard is gone, and it gives the one command
that brings it back. This keeps the third promise, because aj learns that nothing is guarding the
session.

**Test case** (`tools/verify_tools.py`): run `force_update.py --skip-marketplace-update` with a
stand-in `claude` on `PATH` that succeeds on `uninstall` and exits 1 on `install`. Assert that the
output holds "UNINSTALLED" and "claude plugin install house-rules@aj-house-rules -y".

**Proved on the current code:** by reading `invoke_claude` at `force_update.py:27-31`, which raises
`"Reinstalling ... failed (exit N)."` and nothing more.

### A13. The installer's file check always finds a difference

**File:** `tools/_plugin_sync.py:22-29`.

**Now:**

```python
    for dirpath, dirnames, filenames in os.walk(root):
        if os.sep + ".in_use" + os.sep in dirpath + os.sep:
            continue
        for fname in filenames:
            full = os.path.join(dirpath, fname)
```

**Proposed:**

```python
    for dirpath, dirnames, filenames in os.walk(root):
        if os.sep + ".in_use" + os.sep in dirpath + os.sep:
            continue
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]  # A13: written by running the hooks, never shipped
        for fname in filenames:
            if fname.endswith(".pyc") or fname == ".python-cache":
                continue
            full = os.path.join(dirpath, fname)
```

**Why this is enough:** these are the same skips `tools/clean_install_test.py:302-305` already makes.
`.python-cache` is a file (`run.sh:60` writes the interpreter path into it), not a folder.

**Test case** (`tools/verify_tools.py`):

```python
_ts = tempfile.mkdtemp(); _td = tempfile.mkdtemp()
for _root in (_ts, _td):
    open(os.path.join(_root, "a.py"), "w").write("x = 1\n")
os.makedirs(os.path.join(_td, "__pycache__"))
open(os.path.join(_td, "__pycache__", "a.cpython-313.pyc"), "wb").write(b"\0")
open(os.path.join(_td, ".python-cache"), "w").write("python3\n")
check("A13: tree_hash ignores __pycache__, .pyc and .python-cache",
      diff_trees(tree_hash(_ts), tree_hash(_td)) == [])
```

**Proved on the current code:** `diff_trees` between this repo's plugin folder and the installed
2.75.0 copy gave 15 differences, and every one was a cache file, for example
`('cache only', 'scripts/.python-cache')` and `('differs', 'scripts/__pycache__/clarity.cpython-313.pyc')`.

### A14. The page builder's node check can fail a page wrongly

**File:** `scripts/make_page.py:574-578`.

**Now:**

```python
            if r.returncode == 0:
                fd, js = tempfile.mkstemp(suffix=".js")
                with os.fdopen(fd, "w") as f:
                    f.write(NODE_JS)
                runs.append(("node playwright", [node, js, out, arg, "(%s)()" % CLIP_JS]))
```

**Proposed:**

```python
            if r.returncode == 0:
                # A14: run from the folder the probe ran in, so require finds the same playwright; "make_page"
                # fills process.argv[1], keeping the page at argv[2] as NODE_JS expects. No temp file is left behind.
                runs.append(("node playwright", [node, "-e", NODE_JS, "make_page", out, arg, "(%s)()" % CLIP_JS]))
```

**Why this is enough:** `node -e` resolves `require` from the current folder, just as the probe at
`:569` does, so the two can't disagree. A run here confirmed the argument positions:
`node -e "console.log(process.argv[2], process.argv[3], process.argv[4])" make_page FILE '["light"]' CLIP`
printed `FILE ["light"] CLIP`. Grep finds no other use of `tempfile` in `make_page.py`, so
`import tempfile` at `:31` is deleted too.

**Test case** (`checks/make_page.py`): build a page with `PATH` holding only a stand-in `node` that
prints its arguments, and assert that `-e` comes second and the page path comes fifth.

**Proved on the current code:** by reading. The full audit ran it with `playwright` only in a
project's `node_modules`, and got `Cannot find module 'playwright'`.

### A15. Two checks answer "does this commit include every file?" differently

**File:** `scripts/house_rules/docs.py:208` and `safe_git.py:1539`.

**Now:**

```python
_COMMIT_ALL_RE = re.compile(r"(^|\s)(-a\b|--all\b|-am\b|-ma\b)", re.IGNORECASE)
```

```python
_COMMIT_ALL_RE = re.compile(r"\scommit\b[^\n;&|]*?\s(?:-a\b|--all\b|-[A-Za-z]*a[A-Za-z]*\b)")
```

**Proposed:** the `safe_git.py` line moves to `core.py` unchanged. Both copies are deleted, and
`_COMMIT_ALL_RE` is added to the explicit `from house_rules.core import (...)` list in `docs.py` and
`safe_git.py`, because `import *` skips names that start with `_`:

```python
_COMMIT_ALL_RE = re.compile(r"\scommit\b[^\n;&|]*?\s(?:-a\b|--all\b|-[A-Za-z]*a[A-Za-z]*\b)")  # A15: one answer for docs and safe_git
```

**Why this is enough:** both checks now give the same answer. `docs.py` passes the commit statement,
which holds " commit", so the moved pattern matches there too.

**Test case** (`checks/docs.py`):

```python
_ca = importlib.import_module("house_rules.core")._COMMIT_ALL_RE
report("PASS" if ([bool(_ca.search(c)) for c in ("git commit -sam x", "git commit -qa -m x", "git commit -am x",
                                                  "git commit --amend -m x", "git commit -m x")]
                  == [True, True, True, False, False]) else "FAIL",
       "A15: one commit -a pattern, which sees -sam and -qa and not --amend")
```

**Proved on the current code:** for `git commit -sam x` and `git commit -qa -m x`, the `docs.py`
pattern said `False` and the `safe_git.py` pattern said `True`. Both agreed on `-am`, `--amend` and
plain `-m`.

### D11. "Labelled" is a text search of the whole command

**File:** `scripts/house_rules/design_loop.py:1085-1098` (`_created_issue`).

**Now:**

```python
    if tool == "Bash":
        cmd = ti.get("command") or ""
        if not _GH_ISSUE_CREATE_RE.search(cmd):
            return None
        label_text, how = cmd, "`gh issue create`"
    elif _GITHUB_ISSUE_WRITE_RE.match(tool) and str(ti.get("method", "")).lower() == "create":
        labels = ti.get("labels") if isinstance(ti.get("labels"), list) else []
        label_text, how = " ".join(str(l) for l in labels), "GitHub tool issue_write"
    else:
        return None
```

```python
    labelled = any(l.lower() in label_text.lower() for l in (ISSUES_LABEL, ISSUES_LABEL_OLD))
```

**Proposed:**

```python
    if tool == "Bash":
        cmd = ti.get("command") or ""
        if not _GH_ISSUE_CREATE_RE.search(cmd):
            return None
        labels, how = _gh_label_flags(cmd)["add"], "`gh issue create`"  # D11: the label flags, not the title
    elif _GITHUB_ISSUE_WRITE_RE.match(tool) and str(ti.get("method", "")).lower() == "create":
        labels = [str(l) for l in ti["labels"]] if isinstance(ti.get("labels"), list) else []
        how = "GitHub tool issue_write"
    else:
        return None
```

```python
    labelled = bool({l.lower() for l in labels} & {ISSUES_LABEL.lower(), ISSUES_LABEL_OLD.lower()})
```

**Why this is enough:** only a real label counts. `_gh_label_flags` (`:1150`) already reads
`--label` and `-l`, including comma lists.

**Test case:**

```python
_loop_post("Bash", {"command": "gh issue create --title 'Fix AjsAgent created this' --body x"},
           {"stdout": "https://github.com/o/r/issues/301\n"})
_loop_cases.append(("D11: the label name in a title doesn't make an issue labelled",
                    any(i.get("number") == 301 and not i.get("labelled") for i in _loop_state().get("issues", []))))
```

This runs while the fixture's stage is Plan, so the issue is recorded.

**Proved on the current code:** `gh issue create --title 'Fix AjsAgent created this' --body x` gave
`recorded issues: [{'repo': 'o/r', 'number': 9, 'labelled': True}]`.

### D12. A failed `gh api` call is recorded as a label change

**File:** `scripts/house_rules/design_loop.py:1171-1176` (`_gh_api_label_change`) and `:1211` (its caller).

**Now:**

```python
def _gh_api_label_change(cmd, text):
    """#278: (repo, number, None, add, remove) for a succeeded `gh api repos/O/R/issues/N/labels` call (the REST
    form that works in cloud sessions), else None. Repo and number come from the path, not the response."""
    m = _GH_API_LABELS_RE.search(cmd)
    if not m or _GH_API_FAILED_RE.search(text):
        return None
```

```python
    api = _gh_api_label_change(cmd, text)
```

**Proposed:**

```python
def _gh_api_worked(resp):
    """D12: proof a `gh api` labels call worked: exit code 0, or, where none is reported, the JSON list of labels
    the endpoint answers with. A sign-in prompt or any other text is not proof."""
    if isinstance(resp, list):
        return True
    if isinstance(resp, str):
        resp = {"stdout": resp}
    if not isinstance(resp, dict):
        return False
    code = resp.get("exit_code", resp.get("exitCode", resp.get("returncode")))
    if code is not None:
        return code == 0
    try:
        return isinstance(json.loads(resp.get("stdout") or ""), list)
    except ValueError:
        return False


def _gh_api_label_change(cmd, text, resp=None):
    """#278: (repo, number, None, add, remove) for a succeeded `gh api repos/O/R/issues/N/labels` call (the REST
    form that works in cloud sessions), else None. Repo and number come from the path, not the response."""
    m = _GH_API_LABELS_RE.search(cmd)
    if not m or _GH_API_FAILED_RE.search(text) or not _gh_api_worked(resp):
        return None
```

```python
    api = _gh_api_label_change(cmd, text, resp)
```

**Why this is enough:** a label change is recorded only on proof that it worked. Those records are
the fallback the label check uses when GitHub can't be read, which D9 relies on. Two fixtures at
`checks/design_loop.py:696` and `:699` send `""` as a DELETE's reply. A real `gh api -X DELETE`
answers with the remaining labels, so those fixtures change to `{"stdout": "[]\n", "stderr": ""}`.

**Test case:**

```python
_loop_post("Bash", {"command": "gh api repos/o/r/issues/204/labels -f 'labels[]=needs review'"},
           {"stdout": "", "stderr": "To get started with GitHub CLI, please run:  gh auth login", "exit_code": 4})
_loop_post("Bash", {"command": "gh api repos/o/r/issues/205/labels -f 'labels[]=needs review'"},
           {"stdout": "", "stderr": "To get started with GitHub CLI, please run:  gh auth login"})
_loop_cases.append(("D12: a gh api label call that failed, with or without an exit code, records nothing",
                    not {"o/r#204", "o/r#205"} & set(_loop_cached_labels())))
```

**Proved on the current code:** a `gh api` label add answered with the sign-in message, and even with
`"exit_code": 4`, gave `recorded labels: {'o/r#1': ['needs review']}`.

### H5. Plain text and data files are locked like code

**File:** `scripts/house_rules/design_loop.py:187-198`. The fix is in D4's `_is_source_path` above
(`_OPEN_EXTS`).

**Why this is enough:** `.txt`, `.csv` and `.tsv` are open in every stage, like `.md`. `.json` stays
locked outside `docs/` and `.claude/`; see "Not decided".

**Test case:** D4's second case covers `notes.txt` and `data.csv`.

**Proved on the current code:** in the Plan stage, Writes of `notes.txt` and `data.csv` were both
refused: `"permissionDecision":"deny","permissionDecisionReason":"House rules, design loop: code edits are closed in t…`.

### A18. `diff_parts.py` miscounts lines that start with `--` or `++`

**File:** `tools/diff_parts.py:64-75`.

**Now:**

```python
    added, removed, o, n = {}, {}, 0, 0
    for line in diff.splitlines():
        hunk = re.match(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if hunk:
            o, n = int(hunk.group(1)), int(hunk.group(2))
        elif line.startswith("+") and not line.startswith("+++"):
```

```python
        elif line.startswith("-") and not line.startswith("---"):
```

**Proposed:**

```python
    added, removed, o, n, in_hunk = {}, {}, 0, 0, False
    for line in diff.splitlines():
        hunk = re.match(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if hunk:
            o, n, in_hunk = int(hunk.group(1)), int(hunk.group(2)), True
        elif not in_hunk:
            continue  # A18: the diff --git, index, --- and +++ header lines come before the first @@
        elif line.startswith("+"):
```

```python
        elif line.startswith("-"):
```

**Why this is enough:** the diff covers one path (`-- path`), so the `---` and `+++` header appears
once, before the first `@@`. After that, every line starting `-` or `+` is content, including a
Markdown `---` rule.

**Test case** (`tools/verify_tools.py`): a temporary repo whose commit removes a `---` line and one
other line. `parts(...)["removed"]` must equal the `git diff --numstat` count, 2.

**Proved on the current code:** by reading. The full audit ran it, and got 1 removed line where
`numstat` says 2.

### A19. Dead code

**Exactly what is deleted, each checked with grep:**

1. `scripts/clarity.py:196`, the first of two lines that both assign `sentences`. The next line
   overwrites it.

   ```python
           sentences = [s for s in _SENTENCE_SPLIT_RE.split(para) if len(_WORD_RE.findall(s)) >= 4]
   ```

2. `scripts/hook.py:189-191`, the `writing` list that is never filled, and its uses at `:202` and
   `:219-220`. `_writing_note` (`writing.py:198`) has one caller, `hook.py:220`, so its `writing`
   argument and its `if writing:` branch (`writing.py:203-211`) go too. The not-checked and long-reply
   notes stay.

   ```python
       # #324: the writing check no longer runs on chat replies (pages and new issues keep it), so no findings
       # and no report line here; the not-checked disclosure still goes through _writing_note.
       writing = []
   ```

   The proposed lines at `:219-220` are:

   ```python
       if not_checked or long_words:
           parts.append(_writing_note(not_checked, long_words))
   ```

   And `writing.py:198-214` becomes:

   ```python
   def _writing_note(not_checked, long_words):
       """#248: one end-of-reply note for the not-checked and long-reply findings."""
       lines = []
       if not_checked:
           lines.append(_not_checked_note(not_checked))
       if long_words:
           lines.append(_long_reply_note(long_words))
       return "\n\n".join(lines)
   ```

3. `scripts/house_rules/design_loop.py:1873-1874` (`_check_page_saved`, which always returns `""`), the
   two `CHECKPOINTS` rows that use it (`:1912-1913`), the `"page built"` entry of `CHECKPOINT_RULES`
   (`:1924`), and the comment's second sentence at `:1776-1777`. Grep finds no other use of any of
   them; `_missed_checkpoints` reads only `"reply ends"` rows. The `pagecheck` hook still does the work.

4. Blank lines in `scripts/house_rules/safe_git.py`: each run of more than two blank lines is cut to
   two, as PEP 8 asks. There are 12 runs (71-74, 185-187, 194-197, 223-228, 253-260, 317-319, 327-332,
   1194-1205, 1260-1263, 1507-1516, 1815-1830 and 1836-1846), and 63 lines go. This goes last, after
   steps 1 and 2.

**Why this is enough:** each deletion was checked with grep for every use, and nothing else calls them.

**Test case:** none new. The full `verify.py` must pass. Grep finds no mention of the two "page
saved" rows in `docs/architecture.md`, so no doc changes with them.

**Proved on the current code:** by reading, with grep for `_check_page_saved`, `CHECKPOINTS`,
`CHECKPOINT_RULES` and `_writing_note`.

### A20. One-off checks that nothing runs, and small copies

1. **`tools/check_verify_inventory.py` (304 lines).** It still passes in structure-only mode: a run
   here printed `RESULT: PASS - the inventory adds up.` for "913" checks. But nothing runs it (grep
   finds it only in docs), and the full `verify.py` run earlier in this session printed 988 lines
   holding "PASS", so the table it guards is already out of date. The proposal is to delete it, and to mark the table in
   `docs/4-systems/verify-suites.md:241`, `:506` and `:661` as a snapshot from 2026-10-21. The other way
   is to run it from `tools/verify_tools.py` and update the table; see "Not decided".

2. **`scripts/plain_docs_check.py:134-151`, the second fence parser.**

   **Now:**

   ```python
   def fenced_ranges(lines):
       """1-indexed (start, end) ranges of fenced code blocks (``` or ~~~), CommonMark-ish."""
       ranges = []
       open_fence = None
       start = 0
       for n, line in enumerate(lines, 1):
           m = FENCE_RE.match(line.rstrip("\n"))
           if m:
               run = m.group(1)
               if open_fence is None:
                   open_fence = run[0]
                   start = n
               elif run[0] == open_fence:
                   ranges.append((start, n))
                   open_fence = None
       if open_fence is not None:
           ranges.append((start, len(lines)))
       return ranges
   ```

   **Proposed:**

   ```python
   from docref import _fence_step  # noqa: E402  A20: one CommonMark fence reader for both checkers


   def fenced_ranges(lines):
       """1-indexed (start, end) ranges of fenced code blocks (``` or ~~~), read by docref's _fence_step."""
       ranges, open_fence, start = [], None, 0
       for n, line in enumerate(lines, 1):
           was_open = open_fence
           open_fence, is_fence = _fence_step(line.rstrip("\n"), open_fence)
           if is_fence and was_open is None and open_fence is not None:
               start = n
           elif is_fence and was_open is not None and open_fence is None:
               ranges.append((start, n))
       if open_fence is not None:
           ranges.append((start, len(lines)))
       return ranges
   ```

   `FENCE_RE` at `plain_docs_check.py:50` is then unused (grep finds it only at `:50` and `:142`) and
   is deleted. `docref.py` has its `__main__` guard at `:388`, so importing it runs nothing.

3. **`tools/install.py:351-352`, the failure counted twice.** `verify_and_self_heal` already calls
   `bad()` at `:140`, and `bad()` adds one to `failures` (`:279-281`).

   **Now:**

   ```python
           if not verify_and_self_heal(source_root, installed_root, reinstall, ok, bad, info):
               failures += 1
   ```

   **Proposed:**

   ```python
           verify_and_self_heal(source_root, installed_root, reinstall, ok, bad, info)  # bad() counts the failure
   ```

**Why this is enough:** about 320 lines that judged nothing are gone, and one fence reader is left.
The fence reader that stays is the one that handles a longer closing fence and a backtick in an info
string.

**Test case:** `python claude-house-rules/plugins/house-rules/scripts/plain_docs_check.py` gives the
same result before and after on `docs/plain/`. For `install.py`, a `tools/verify_tools.py` case
drives `verify_and_self_heal` to fail once and asserts that the failure count is 1.

**Proved on the current code:** by reading, and the structure-only run of
`check_verify_inventory.py` quoted above.

### H4. Every call pays for six to nine hook processes

**Measured here:** one `hook.py` start with an unknown event, which imports everything and then does
nothing, took a median of 56 ms (51 to 83 ms) over 15 runs. A shell command starts four PostToolUse
processes (`creditcheck`, `closablemerge`, `autosave` and `promptran`). Running them in one process
would save at least three starts, about 170 ms per shell command. That is a lower bound, because
`run.sh` and `sh` add their own start-up on top.

**The measurement before any merge:** time 50 shell-command payloads through the four separate
hooks, then through the merged `posttool` below, both called through `run.sh` as `hooks.json` does.
The merge goes in only if the merged median is at least 100 ms faster per call. Otherwise it is
dropped, and the numbers are recorded in `docs/4-systems/hook-engine.md`.

**Proposed merge** (`scripts/hook.py`, a new event; `hooks.json`'s four PostToolUse entries become one
entry with the union matcher):

```python
POST_TOOL_GROUP = (  # H4: one process for these PostToolUse handlers; each keeps the matcher hooks.json gave it
    ("creditcheck", r"Bash"),
    ("closablemerge", r"Bash|mcp__(github|GitHub)__(merge_pull_request|issue_write)"),
    ("autosave", r"Write|Edit|NotebookEdit|Bash|mcp__(github|GitHub)__issue_write"),
    ("promptran", r"Bash|PowerShell|Write|Edit|MultiEdit|NotebookEdit|WebFetch|WebSearch|mcp__.*"),
)


def event_posttool():
    """H4: run the grouped PostToolUse handlers in one process and send one merged answer."""
    import io
    raw = read_payload()
    try:
        tool = (json.loads(raw) or {}).get("tool_name") or ""
    except (ValueError, AttributeError):
        tool = ""
    messages, contexts = [], []
    for name, matcher in POST_TOOL_GROUP:
        if not re.fullmatch(matcher, tool):
            continue
        out = io.StringIO()
        sys.stdin = io.TextIOWrapper(io.BytesIO(raw.encode("utf-8")), encoding="utf-8")
        sys.stdout = out
        try:
            main(["hook.py", name])
        finally:
            sys.stdin, sys.stdout = sys.__stdin__, sys.__stdout__
        text, dec = out.getvalue().strip(), json.JSONDecoder()
        while text:
            obj, end = dec.raw_decode(text)
            text = text[end:].lstrip()
            if obj.get("systemMessage"):
                messages.append(obj["systemMessage"])
            ctx = (obj.get("hookSpecificOutput") or {}).get("additionalContext")
            if ctx:
                contexts.append(ctx)
    answer = {}
    if messages:
        answer["systemMessage"] = "\n".join(messages)
    if contexts:
        answer["hookSpecificOutput"] = {"hookEventName": "PostToolUse", "additionalContext": "\n\n".join(contexts)}
    if answer:
        emit(answer)
    return 0
```

**Why this is enough:** each handler still runs only for the tools its old matcher named, reads the
same payload, and keeps its own error net through `main`. Their outputs are merged into one JSON
answer, because two `emit` calls in one process would be two joined objects, which the existing
comment in `hook.py` warns against. The two PreToolUse hooks (`guard` and `commitgate`) and the
`PostToolUseFailure` entry are left alone, because a refusal from one PreToolUse hook must not depend
on another hook's run.

**Test case:** a `verify.py` case sends one Bash payload through `posttool` and through the four
hooks one by one, and asserts that the merged answer holds every line the four printed.

---

## Not decided / risks

1. **D9: where the recorded labels live.** The proposal moves them into the common git directory, so
   a branch switch can't bring old ones back, and Build still works when GitHub can't be read. The
   audit's own fix was simpler: refuse every Build edit when GitHub can't be read. That would stop all
   Build work on a machine where `gh` isn't signed in, which is a "blocks work" problem, and blocks
   rank above lock bypasses on the combined list. My suggestion is the proposal. Its cost is that a
   fresh clone has no record until the first label change is seen.
2. **D6: strict names.** Two of aj's nine real build-plan approvals ("guard audit" and "plugin
   restructure 2.68.1 patch") would have been refused, and aj would have needed to retype the name. A
   looser rule, such as words in common, would let a wrong feature through again.
3. **D2: the approval must start a sentence.** "Great work, design approved: X" still counts, because
   a comma is allowed before it. "I think design approved: X is fine" doesn't count, and the hook asks
   which approval was meant, through the existing bare-"approved" note. This needs a check in a real
   session, because the wrapping Claude Code puts around a prompt (such as `<message>`) is only
   partly known.
4. **H5: `.json`.** It stays locked outside `docs/` and `.claude/`, because files like `package.json`
   change how a build runs. If aj wants data `.json` open, a folder rule (`data/`) is safer than the
   extension.
5. **A7 and A10: hooks running at the same instant.** Atomic writes stop half-written files, and the
   placeholder stops launches made one after another. Two hooks that read and write at the same
   instant can still lose one update. A lock file would fix both, at about 15 more lines, and isn't
   proposed until a real loss is seen.
6. **A2: pull requests opened outside a session.** Their body is read once with `gh pr view`. When
   that fails, nothing is stamped, the note says why, and the issue can't be closed until a later
   merge or aj's sweep list allows it.
7. **U3 changes the written plan.** `docs/4-systems/audit-fixes.md` said `main` gets no stage file
   from a merged feature. This proposal keeps the stage and asks aj instead, because a merge moving
   the stage would break the first promise.
8. **A20: the inventory checker.** Delete it (my suggestion, because its table is already out of
   date), or run it from `tools/verify_tools.py` and bring the table up to date.
9. **H4** is built only if the measurement shows at least 100 ms saved per shell command.
10. **Fixtures that change:** A2 adds issues and `pr_refs` to `_cl_open`. D9 moves the labels in the
    `:908-913` fixture into the cache, and the label cases at `:689-706` read the cache. D12 changes
    the two DELETE replies at `:696` and `:699`. D3 needs no fixture change, because reading the old
    file stays.
11. **Not run:** D8, D9 (this exact payload), U3, A7, A12, A14, A16 and A18 were checked by reading.
    None of the proposed code has been run, because source edits are locked in the Plan stage.
