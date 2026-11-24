# Acceptance test 4: real sweep of the 14-folder fixture

Fixture: 14 folders with one 5-line Python file each, plus one root file (`settings.toml`), 15 batches.
Run exactly as `commands/review.md` says: one `house-rules:reviewer` per batch in codebase mode, one at a time.
Figures are the harness's `duration_ms` and `subagent_tokens` for each reviewer. Every batch answered `no findings`.

| Batch | Seconds | Tokens |
|---|---|---|
| d01 | 6.9 | 13,024 |
| d02 | 5.0 | 13,733 |
| d03 | 6.4 | 13,493 |
| d04 | 5.9 | 13,711 |
| d05 | 5.9 | 13,875 |
| d06 | 6.2 | 13,659 |
| d07 | 5.8 | 12,809 |
| d08 | 6.2 | 13,767 |
| d09 | 5.4 | 12,786 |
| d10 | 5.4 | 13,705 |
| d11 | 5.9 | 13,852 |
| d12 | 6.2 | 13,676 |
| d13 | 4.9 | 13,515 |
| d14 | 5.7 | 13,896 |
| root files | 7.1 | 13,893 |

**Totals:** 88.9 seconds of reviewer time and 203,394 tokens for 15 files in 15 batches.

**Notice said:** about 2 minutes and about 66,000 tokens (7.1 seconds and 4,400 tokens per file).
**Time:** 89 seconds actual against 107 seconds estimated, so the time figure held (it was a little high).
**Tokens:** 203,394 actual against 66,000 estimated, so the token figure was 3.1 times too low.
A reviewer costs about 13,500 tokens even for a one-file batch (reading its rules and starting up), so a count that grows only with files undercounts small batches.
Two measurements fit one rule: about 10,000 tokens per batch plus about 3,400 per file (1 file: 13,400, measured 12,800 to 13,900; 10 markdown files: 44,000, measured 43,991).

**Not exercised:** merging and ranking by [high], [medium], [low] (acceptance test 7), because no batch reported a finding.
