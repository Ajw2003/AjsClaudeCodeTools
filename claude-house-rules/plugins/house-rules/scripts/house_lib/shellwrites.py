"""house_lib.shellwrites - which files a shell command writes (moved out of house-rules, #440 part B).

`script_write_targets(cmd)` was `_script_write_targets` in house_rules/design_loop.py (#262): it reads the
paths a Bash/PowerShell command writes through a python/node script (open w/a, write_text, writeFileSync),
`sed -i` / `perl -pi`, `tee` or a `>` / `>>` redirect, and says whether some path could not be read. The
design loop's gate and the repeat-failure lock (rule-enforcement `lockgate`) both use it. `copy_targets`
adds cp / mv / install / dd of= / truncate for the lock. STDLIB ONLY.
"""

import re
import shlex

_ASSIGN_RE = re.compile(r"""(?:^|(?<=[;&\n]))\s*([A-Za-z_]\w*)=(?:"([^"$`\\\n]*)"|'([^'\n]*)'|([^\s;&|"'$`\\()<>*?]*))[ \t]*(?:&&|;)""")


def _apply_assigns(cmd):
    """#261/#262: drop simple same-command NAME=value assignments and expand $NAME / ${NAME}
    from them; a name that was not assigned stays as written."""
    assigns = {}
    for am in _ASSIGN_RE.finditer(cmd):
        assigns[am.group(1)] = am.group(2) if am.group(2) is not None else (am.group(3) if am.group(3) is not None else am.group(4))
    if assigns:
        cmd = _ASSIGN_RE.sub("", cmd)
        cmd = re.sub(r"\$\{(\w+)\}|\$(\w+)", lambda mm: assigns.get(mm.group(1) or mm.group(2), mm.group(0)), cmd)
    return cmd


_HEREDOC_RE = re.compile(r"<<-?[ \t]*(['\"]?)(\w+)\1[^\n]*\n.*?\n[ \t]*\2[ \t]*(?=\n|$)", re.DOTALL)


_QUOTED_RE = re.compile(r"(>>?[ \t]*)?(\"[^\"\n]*\"|'[^'\n]*')")


_REDIRECT_RE = re.compile(r"(?<![<>&|])(?:\d|&)?>>?(?![&(>])[ \t]*(\"[^\"\n]+\"|'[^'\n]+'|[^\s;&|<>()\"']+)")


_PY_OPEN_RE = re.compile(r"\bopen\(\s*([^,()]+?)\s*,\s*(?:mode\s*=\s*)?['\"][wax]")


_PY_WRITE_TEXT_RE = re.compile(r"\.write_text\(")


_PY_WRITE_TEXT_LIT_RE = re.compile(r"Path\(\s*(['\"])([^'\"]+)\1\s*\)\s*\.write_text\(")


_NODE_WRITE_RE = re.compile(r"\bwriteFileSync\(")


_NODE_WRITE_LIT_RE = re.compile(r"\bwriteFileSync\(\s*(['\"])([^'\"]+)\1")


_SCRIPT_RUNNER_RE = re.compile(r"(?:^|[\s;&|(/])(?:python3?|py|node)(?:\.exe)?(?=\s|$)")


_LITERAL_RE = re.compile(r"^(['\"])(.+)\1$")


def _statements(body):
    """Cut a command into statements at && || ; newline | that sit OUTSIDE quotes (single, double,
    backslash escapes), so a multi-line quoted message stays one statement."""
    out, cur, i, n, q = [], [], 0, len(body), None
    while i < n:
        c = body[i]
        if q == "'":
            if c == "'":
                q = None
        elif q == '"':
            if c == "\\" and i + 1 < n:
                cur.append(c)
                i += 1
                c = body[i]
            elif c == '"':
                q = None
        elif c == "\\" and i + 1 < n:
            cur.append(c)
            i += 1
            c = body[i]
        elif c in "'\"":
            q = c
        elif c in ";\n|" or (c == "&" and body[i + 1:i + 2] == "&"):
            if c in "&|" and body[i + 1:i + 2] == c:
                i += 1
            out.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(c)
        i += 1
    out.append("".join(cur))
    return out


def script_write_targets(cmd):
    """(targets, unreadable): file paths a shell command writes through a python/node script
    (open w/a, write_text, writeFileSync), sed -i / perl -pi, tee, or a > / >> redirect, and
    whether some write's path could not be read from the command text (#262)."""
    targets, unreadable = [], False
    body = _HEREDOC_RE.sub("", cmd)
    if _SCRIPT_RUNNER_RE.search(cmd):
        for m in _PY_OPEN_RE.finditer(cmd):
            lit = _LITERAL_RE.match(m.group(1))
            if lit and "$" not in lit.group(2):
                targets.append(lit.group(2))
            else:
                unreadable = True
        lits = _PY_WRITE_TEXT_LIT_RE.findall(cmd)
        targets += [p for _, p in lits]
        if len(_PY_WRITE_TEXT_RE.findall(cmd)) > len(lits):
            unreadable = True
        lits = _NODE_WRITE_LIT_RE.findall(cmd)
        targets += [p for _, p in lits]
        if len(_NODE_WRITE_RE.findall(cmd)) > len(lits):
            unreadable = True
    for stmt in _statements(body):
        try:
            words = shlex.split(stmt)
        except ValueError:
            unreadable = True  # unbalanced quotes: the shell would reject it; cannot be read, so not skipped
            continue
        for i, w in enumerate(words):
            if w not in ("sed", "perl", "tee"):
                continue
            if any(p not in ("sudo", "env", "time", "nohup") and "=" not in p for p in words[:i]):
                continue  # not in command position (e.g. `echo sed -i`, `grep tee f`)
            rest = words[i + 1:]
            files, has_script, skip = [], False, False
            in_place = w == "tee"
            for a in rest:
                if skip:
                    skip = False
                elif a in ("-e", "-f", "--expression", "--file"):
                    has_script, skip = True, True
                elif re.match(r"^-[A-Za-z]+$", a) and a.endswith("e") and not re.match(r"^-[A-Za-z]*i", a):
                    has_script, skip = True, True  # -ne / -pe: the next word is the script
                elif a.startswith("-"):
                    if a == "--in-place" or a.startswith("--in-place=") or re.match(r"^-[A-Za-z]*i", a):
                        in_place = True
                else:
                    files.append(a)
            if not in_place:
                continue
            if w == "sed" and not has_script and files:
                files = files[1:]
            if not files:
                unreadable = True
            for f in files:
                if re.search(r"[$`~*?]", f):
                    unreadable = True
                else:
                    targets.append(f)
            break
    plain = _QUOTED_RE.sub(lambda m: m.group(0) if m.group(1) else " ", body)
    for m in _REDIRECT_RE.finditer(plain):
        t = m.group(1).strip("'\"")
        if t.startswith("/dev/"):
            continue
        if re.search(r"[$`~*?]", t):
            unreadable = True
        else:
            targets.append(t)
    return targets, unreadable


def copy_targets(cmd):
    """(targets, unreadable): files a cp / mv / install / dd of= / truncate command overwrites or removes.
    cp and install write their last argument; mv, truncate and dd of= name every file they touch."""
    targets, unreadable = [], False
    body = _HEREDOC_RE.sub("", cmd)
    for stmt in _statements(body):
        try:
            words = shlex.split(stmt)
        except ValueError:
            unreadable = True
            continue
        for i, w in enumerate(words):
            name = w.rsplit("/", 1)[-1]
            if name not in ("cp", "mv", "install", "dd", "truncate", "ln"):
                continue
            if any(p not in ("sudo", "env", "time", "nohup", "command") and "=" not in p for p in words[:i]):
                continue
            args = [a for a in words[i + 1:] if not a.startswith("-") or name == "dd"]
            if name == "dd":
                args = [a[3:] for a in args if a.startswith("of=")]
            elif name in ("cp", "install", "ln"):
                args = args[-1:] if len(args) >= 2 else []
            for a in args:
                if re.search(r"[$`~*?]", a):
                    unreadable = True
                else:
                    targets.append(a)
            break
    return targets, unreadable
