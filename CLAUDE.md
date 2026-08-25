# Global rules — see the house-rules plugin

The rules are not stored here. They live in one place and are injected into every session
automatically by the `house-rules` plugin:

    claude-house-rules/plugins/house-rules/rules/house-rules.md
    https://github.com/Ajw2003/AjsClaudeCodeTools

Do not paste the rules back into this file. Claude Code auto-loads every CLAUDE.md it finds,
so a copy here means the same text loads twice and the two drift apart unnoticed.

To check the plugin is live:  claude plugin list
To check nothing has drifted: sh claude-house-rules/plugins/house-rules/scripts/verify.sh
