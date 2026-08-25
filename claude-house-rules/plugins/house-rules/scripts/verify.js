#!/usr/bin/env node
'use strict';

/**
 * verify.js — proves the house-rules guard actually does what it claims.
 *
 * Run it yourself, any time, on any machine:
 *
 *     node plugins/house-rules/scripts/verify.js
 *
 * It feeds real hook payloads to house-rules.js and prints a numbered PASS/FAIL line for
 * each one, then a final verdict. Exit code 0 = all passed, 1 = something failed.
 * Nothing is hidden: every command tested is printed alongside its result.
 */

const path = require('path');
const { spawnSync } = require('child_process');

const GUARD = path.join(__dirname, 'house-rules.js');

// Each case: what we feed in, and whether we expect a permission prompt ("ask") or silence.
const CASES = [
  // Read-only git — must pass straight through, per the rules.
  { command: 'git status', expect: 'pass', note: 'read-only git is explicitly fine' },
  { command: 'git log --oneline -n 20', expect: 'pass', note: 'read-only git is explicitly fine' },
  { command: 'git diff HEAD~1', expect: 'pass', note: 'read-only git is explicitly fine' },

  // Ordinary work — must not be nagged.
  { command: 'npm test', expect: 'pass', note: 'ordinary foreground command' },
  { command: 'ls -la src', expect: 'pass', note: 'ordinary foreground command' },
  { command: 'Get-ChildItem C:\\Users', expect: 'pass', note: 'ordinary foreground command' },

  // Rule: never commit without asking.
  { command: 'git commit -m "wip"', expect: 'ask', rule: 'Never commit without asking' },
  { command: 'git add -A', expect: 'ask', rule: 'Never commit without asking' },
  { command: 'git push origin main', expect: 'ask', rule: 'Never commit without asking' },
  { command: 'git push --force-with-lease', expect: 'ask', rule: 'Never commit without asking' },
  { command: 'git checkout -b feature/x', expect: 'ask', rule: 'Never commit without asking' },
  { command: 'git reset --hard origin/main', expect: 'ask', rule: 'Never commit without asking' },

  // Rule: never hide work in a background window or a silent process.
  {
    command: 'Start-Process powershell -WindowStyle Hidden -ArgumentList "-File build.ps1"',
    expect: 'ask',
    rule: 'Never hide work in a background window or a silent process',
  },
  {
    command: 'npm run dev > dev.log 2>&1 &',
    expect: 'ask',
    rule: 'Never hide work in a background window or a silent process',
  },
  {
    command: 'nohup ./long-task.sh',
    expect: 'ask',
    rule: 'Never hide work in a background window or a silent process',
  },
  {
    command: 'Start-Job -ScriptBlock { .\\build.ps1 }',
    expect: 'ask',
    rule: 'Never hide work in a background window or a silent process',
  },
  {
    command: 'npm run build && npm test',
    expect: 'pass',
    note: '&& is not backgrounding — must not false-positive',
  },

  // Rule: never take a destructive action without checking first.
  {
    command: 'rm -rf node_modules',
    expect: 'ask',
    rule: 'Never take a destructive action without checking first',
  },
  {
    command: 'Remove-Item -Recurse -Force .\\dist',
    expect: 'ask',
    rule: 'Never take a destructive action without checking first',
  },
  {
    command: 'taskkill /IM node.exe /F',
    expect: 'ask',
    rule: 'Never take a destructive action without checking first',
  },
];

function runGuard(command) {
  const payload = JSON.stringify({
    session_id: 'verify',
    tool_name: 'Bash',
    tool_input: { command },
  });
  const res = spawnSync(process.execPath, [GUARD, 'guard'], {
    input: payload,
    encoding: 'utf8',
  });
  if (res.error) throw res.error;
  const out = (res.stdout || '').trim();
  if (!out) return { decision: 'pass', reason: '' };
  let parsed;
  try {
    parsed = JSON.parse(out);
  } catch (e) {
    return { decision: 'malformed', reason: out };
  }
  const hso = parsed.hookSpecificOutput || {};
  return { decision: hso.permissionDecision || 'pass', reason: hso.permissionDecisionReason || '' };
}

function runInject() {
  const res = spawnSync(process.execPath, [GUARD, 'inject'], { input: '{}', encoding: 'utf8' });
  if (res.error) throw res.error;
  try {
    const parsed = JSON.parse((res.stdout || '').trim());
    return (parsed.hookSpecificOutput || {}).additionalContext || '';
  } catch (e) {
    return '';
  }
}

// ---------------------------------------------------------------------------

console.log('');
console.log('house-rules guard — verification');
console.log('================================');
console.log('Node:  ' + process.version);
console.log('Guard: ' + GUARD);
console.log('');
console.log('Each step feeds one shell command to the guard and checks the decision it returns.');
console.log('"ask"  = Claude Code will show you a permission prompt naming the rule.');
console.log('"pass" = the command runs with no extra prompt.');
console.log('');

let failures = 0;
let step = 0;

for (const c of CASES) {
  step += 1;
  const num = String(step).padStart(2, ' ');
  let got;
  try {
    got = runGuard(c.command);
  } catch (e) {
    failures += 1;
    console.log(`${num}. FAIL  ${c.command}`);
    console.log(`        guard crashed: ${e.message}`);
    continue;
  }

  const ok = got.decision === c.expect;
  const ruleOk = !c.rule || (got.reason || '').includes(c.rule);
  const passed = ok && ruleOk;
  if (!passed) failures += 1;

  console.log(`${num}. ${passed ? 'PASS' : 'FAIL'}  ${c.command}`);
  console.log(`        expected ${c.expect}, got ${got.decision}${c.note ? '  (' + c.note + ')' : ''}`);
  if (c.rule) {
    console.log(`        rule cited: ${ruleOk ? 'yes — "' + c.rule + '"' : 'NO — expected "' + c.rule + '"'}`);
  }
}

// Last step: the SessionStart injection.
step += 1;
const num = String(step).padStart(2, ' ');
const injected = runInject();
const expectedHeadings = [
  'Never hide work in a background window or a silent process',
  'Build things the user can run, verify, and keep',
  'Never commit without asking',
  'Never take a destructive action without checking first',
];
const missing = expectedHeadings.filter((h) => !injected.includes(h));
if (missing.length) failures += 1;
console.log(`${num}. ${missing.length ? 'FAIL' : 'PASS'}  SessionStart injects the rules into context`);
console.log(`        ${injected.length} characters injected, ${expectedHeadings.length - missing.length}/${expectedHeadings.length} rules present`);
if (missing.length) console.log('        missing: ' + missing.join('; '));

console.log('');
console.log('--------------------------------');
if (failures === 0) {
  console.log(`RESULT: PASS — all ${step} checks passed. The guard is behaving as written.`);
} else {
  console.log(`RESULT: FAIL — ${failures} of ${step} checks failed. See the FAIL lines above.`);
}
console.log('');
console.log('Note: matching is textual, so a command that merely mentions a tripwire word');
console.log('inside quotes (e.g. echo "git commit") will also prompt. That is deliberate —');
console.log('an extra keypress is cheaper than a missed commit.');
console.log('');

process.exit(failures === 0 ? 0 : 1);
