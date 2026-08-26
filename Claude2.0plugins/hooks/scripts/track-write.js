#!/usr/bin/env node
// PostToolUse(Write) hook: if the newly written file looks "runnable"
// (a script, or a project entry point), remember it for this session so
// check-deliverable.js can nag if it never actually got run.

const fs = require('fs');
const path = require('path');

const RUNNABLE_EXT = /\.(py|js|mjs|cjs|ts|sh|ps1|bat|cmd)$/i;
const RUNNABLE_NAME = /^(dockerfile|docker-compose\.ya?ml)$/i;

let input = '';
process.stdin.on('data', (d) => { input += d; });
process.stdin.on('end', () => {
  let data;
  try { data = JSON.parse(input); } catch { process.exit(0); }

  const sessionId = data.session_id;
  const filePath = data.tool_input && data.tool_input.file_path;
  if (!sessionId || !filePath) process.exit(0);

  const base = path.basename(filePath);
  if (!RUNNABLE_EXT.test(base) && !RUNNABLE_NAME.test(base)) process.exit(0);

  const stateDir = path.join(__dirname, '..', 'state');
  fs.mkdirSync(stateDir, { recursive: true });
  const stateFile = path.join(stateDir, `${sessionId}.json`);

  let pending = [];
  try { pending = JSON.parse(fs.readFileSync(stateFile, 'utf8')); } catch {}
  if (!pending.includes(filePath)) pending.push(filePath);
  fs.writeFileSync(stateFile, JSON.stringify(pending));
  process.exit(0);
});
