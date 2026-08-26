#!/usr/bin/env node
// Stop hook: if a runnable file was written this turn and nothing was ever
// executed to verify it, block once and say which file(s) are unverified.

const fs = require('fs');
const path = require('path');

let input = '';
process.stdin.on('data', (d) => { input += d; });
process.stdin.on('end', () => {
  let data;
  try { data = JSON.parse(input); } catch { process.exit(0); }

  // Already nagged once this turn (or user is mid a blocked-Stop retry) - let it stop.
  if (data.stop_hook_active) process.exit(0);

  const sessionId = data.session_id;
  if (!sessionId) process.exit(0);

  const stateFile = path.join(__dirname, '..', 'state', `${sessionId}.json`);
  let pending = [];
  try { pending = JSON.parse(fs.readFileSync(stateFile, 'utf8')); } catch { process.exit(0); }
  if (!Array.isArray(pending) || pending.length === 0) process.exit(0);

  try { fs.unlinkSync(stateFile); } catch {}

  const list = pending.map((f) => `- ${f}`).join('\n');
  process.stdout.write(JSON.stringify({
    hookSpecificOutput: {
      hookEventName: 'Stop',
      decision: 'block',
      reason: `You wrote the following file(s) but never ran or verified them this turn:\n${list}\nRun them (or start and confirm they work) before finishing, or explain why running isn't applicable.`,
    },
  }));
  process.exit(0);
});
