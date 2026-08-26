#!/usr/bin/env node
// UserPromptSubmit hook: force-inject standing behavior rules into every turn,
// so enforcement doesn't depend on a skill being semantically matched.

let input = '';
process.stdin.on('data', (d) => { input += d; });
process.stdin.on('end', () => {
  const rules = [
    'Standing behavior rules (scope-guard):',
    "- Match response depth to task complexity — don't reason at length about simple problems.",
    '- If a requirement is ambiguous, ask; do not guess and proceed.',
    '- Take the simplest, most direct path that satisfies exactly what was asked.',
    '- Do not build for hypotheticals ("what if X/Y/Z") beyond what was actually requested.',
  ].join('\n');

  process.stdout.write(JSON.stringify({
    hookSpecificOutput: { hookEventName: 'UserPromptSubmit' },
    additionalContext: rules,
  }));
  process.exit(0);
});
