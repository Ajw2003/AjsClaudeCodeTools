#!/usr/bin/env node
// PostToolUse(Bash|PowerShell) hook: something actually got executed this
// turn, so clear this session's pending-unverified-file list.

const fs = require('fs');
const path = require('path');

let input = '';
process.stdin.on('data', (d) => { input += d; });
process.stdin.on('end', () => {
  let data;
  try { data = JSON.parse(input); } catch { process.exit(0); }

  const sessionId = data.session_id;
  if (!sessionId) process.exit(0);

  const stateFile = path.join(__dirname, '..', 'state', `${sessionId}.json`);
  try { fs.unlinkSync(stateFile); } catch {}
  process.exit(0);
});
