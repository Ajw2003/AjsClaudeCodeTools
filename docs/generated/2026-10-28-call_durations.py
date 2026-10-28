"""Per-tool-call wall time from a Claude Code transcript: tool_use timestamp to tool_result timestamp."""
import json, sys
from datetime import datetime

def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

starts, rows = {}, []
for path in sys.argv[1:]:
    for line in open(path):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        content = (r.get("message") or {}).get("content")
        if not isinstance(content, list) or "timestamp" not in r:
            continue
        for b in content:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                inp = b.get("input") or {}
                label = inp.get("description") or inp.get("command") or inp.get("file_path") or ""
                starts[b["id"]] = (ts(r["timestamp"]), b["name"], str(label)[:70], bool(inp.get("run_in_background")))
            elif b.get("type") == "tool_result" and b.get("tool_use_id") in starts:
                t0, name, label, bg = starts.pop(b["tool_use_id"])
                rows.append(((ts(r["timestamp"]) - t0).total_seconds(), name, label, bg))

rows.sort(reverse=True)
n = len(rows)
for limit in (10, 30, 60, 120):
    print("calls over %3d s: %d of %d" % (limit, sum(1 for d, *_ in rows if d > limit), n))
print("longest 8:")
for d, name, label, bg in rows[:8]:
    print("  %6.1f s  %-8s %s%s" % (d, name, label, "  [background]" if bg else ""))
