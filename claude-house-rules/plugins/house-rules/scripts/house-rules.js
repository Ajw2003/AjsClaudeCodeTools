#!/usr/bin/env node
'use strict';

/**
 * house-rules.js — the enforcement half of aj's global CLAUDE.md rules.
 *
 * Two modes, both driven by Claude Code hooks (see ../hooks/hooks.json):
 *
 *   node house-rules.js inject   SessionStart. Prints the rules back into the model's
 *                                context, so the rules travel with the plugin instead of
 *                                needing a CLAUDE.md in every repo on every machine.
 *
 *   node house-rules.js guard    PreToolUse on Bash|PowerShell. Reads the pending shell
 *                                command from stdin and, if it trips a rule, asks Claude
 *                                Code to put a permission prompt in front of you naming
 *                                the rule. Anything else runs untouched.
 *
 * Design notes:
 *  - Never blocks outright. Every match resolves to permissionDecision "ask", because the
 *    rules are "do not do X without asking", not "X is forbidden".
 *  - Fails open. A crash, a bad payload, or a missing rules file exits 0 with no output so
 *    a broken guard can never wedge a session. That is a deliberate trade: the guard is a
 *    safety net under the rules in context, not the only thing holding them up.
 *  - Pattern matching is textual, so it over-triggers rather than under-triggers (a command
 *    that merely mentions `git commit` inside a quoted string will still prompt). An extra
 *    prompt costs one keypress; a missed commit costs your history.
 */

const fs = require('fs');
const path = require('path');

const MODE = process.argv[2] || 'guard';
const RULES_FILE = path.join(__dirname, '..', 'rules', 'house-rules.md');

// ---------------------------------------------------------------------------
// Rule checks. Each entry: which rule it enforces, what to match, and the
// plain-English reason you will read in the permission prompt.
// ---------------------------------------------------------------------------

const CHECKS = [
  // Rule 1 — Never hide work in a background window or a silent process.
  {
    rule: 'Never hide work in a background window or a silent process',
    why: 'starts a hidden window you cannot watch',
    re: /-WindowStyle\s+Hidden/i,
  },
  {
    rule: 'Never hide work in a background window or a silent process',
    why: 'spawns a separate process with Start-Process',
    re: /\bStart-Process\b/i,
  },
  {
    rule: 'Never hide work in a background window or a silent process',
    why: 'runs the work as a background job',
    re: /\bStart-Job\b|\s-AsJob\b/i,
  },
  {
    rule: 'Never hide work in a background window or a silent process',
    why: 'detaches the process from your terminal',
    re: /\b(nohup|setsid|disown)\b/i,
  },
  {
    rule: 'Never hide work in a background window or a silent process',
    why: 'backgrounds the command with a trailing &',
    re: /(^|[^&])&\s*$/,
  },

  // Rule 3 — Never commit without asking.
  {
    rule: 'Never commit without asking',
    why: 'reaches a remote (push)',
    re: /\bgit\s+(?:-\S+\s+)*push\b/i,
  },
  {
    rule: 'Never commit without asking',
    why: 'mutates the repo, the index, or the working tree',
    re: /\bgit\s+(?:-\S+\s+)*(add|commit|checkout|switch|reset|revert|stash|rm|mv|branch|merge|rebase|clean|tag|cherry-pick|am|apply|remote|submodule|filter-branch)\b/i,
  },

  // Rule 4 — Never take a destructive action without checking first.
  {
    rule: 'Never take a destructive action without checking first',
    why: 'deletes files recursively or by force',
    re: /\brm\s+(-\S*[rRf]\S*\s+)/,
  },
  {
    rule: 'Never take a destructive action without checking first',
    why: 'deletes files (Remove-Item)',
    re: /\bRemove-Item\b|\bri\s+-Recurse\b/i,
  },
  {
    rule: 'Never take a destructive action without checking first',
    why: 'deletes files (del /f or rmdir /s)',
    re: /\bdel\s+\/[fqs]|\brmdir\s+\/s/i,
  },
  {
    rule: 'Never take a destructive action without checking first',
    why: 'kills a running process',
    re: /\bStop-Process\b|\btaskkill\b|\bpkill\b|\bkill\s+-9\b/i,
  },
  {
    rule: 'Never take a destructive action without checking first',
    why: 'truncates or overwrites file contents in place',
    re: /\bClear-Content\b|\btruncate\s+-s\b/i,
  },
];

// ---------------------------------------------------------------------------

function readStdin() {
  try {
    return fs.readFileSync(0, 'utf8');
  } catch (_) {
    return '';
  }
}

function emit(obj) {
  process.stdout.write(JSON.stringify(obj));
}

/** Collect every rule the command trips, deduped by rule name. */
function findViolations(command) {
  const hits = [];
  for (const check of CHECKS) {
    if (!check.re.test(command)) continue;
    const existing = hits.find((h) => h.rule === check.rule);
    if (existing) {
      if (!existing.reasons.includes(check.why)) existing.reasons.push(check.why);
    } else {
      hits.push({ rule: check.rule, reasons: [check.why] });
    }
  }
  return hits;
}

function guard() {
  const raw = readStdin();
  if (!raw.trim()) return;

  let payload;
  try {
    payload = JSON.parse(raw);
  } catch (_) {
    return; // fail open
  }

  const command = (payload && payload.tool_input && payload.tool_input.command) || '';
  if (typeof command !== 'string' || !command.trim()) return;

  const violations = findViolations(command);
  if (violations.length === 0) return; // silent pass-through

  const lines = violations.map(
    (v) => `  • "${v.rule}" — this command ${v.reasons.join(', and ')}.`
  );

  const reason = [
    'Your house rules want you asked before this runs:',
    ...lines,
    '',
    'Approve to let it run, or reject and Claude will explain what it was about to do.',
  ].join('\n');

  emit({
    hookSpecificOutput: {
      hookEventName: 'PreToolUse',
      permissionDecision: 'ask',
      permissionDecisionReason: reason,
    },
  });
}

function inject() {
  let rules;
  try {
    rules = fs.readFileSync(RULES_FILE, 'utf8');
  } catch (_) {
    return; // fail open
  }

  const context = [
    "The following are the user's standing house rules. They apply to every project and",
    'override default behaviour. They are enforced by a PreToolUse hook that will put a',
    'permission prompt in front of the user for mutating git commands, destructive commands,',
    'and backgrounded or hidden processes — but the hook is a backstop, not permission to',
    'skip asking in chat first.',
    '',
    rules,
  ].join('\n');

  emit({
    suppressOutput: true,
    hookSpecificOutput: {
      hookEventName: 'SessionStart',
      additionalContext: context,
    },
  });
}

try {
  if (MODE === 'inject') inject();
  else guard();
} catch (_) {
  // Fail open, always.
}
process.exit(0);
