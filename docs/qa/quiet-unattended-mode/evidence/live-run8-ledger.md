# Design review loop: deviations and parked decisions

Every change from the approved build plan, and every question parked instead of asked. Each row says what the plan said, what was done, why, and how to undo it. aj reviews this on the QA page.

## Choices

| # | Step | Choice made | Assumption | Why | How to undo |
|---|---|---|---|---|---|
| K1 | 1 | page.html header colour #1a6fb0 (blue), title 'Demo Page' | the colour is the user's free choice | the request said a colour of my choice | edit the style attribute in page.html |
| K2 | 6 | built the QA page at docs/qa/demo/index.html from the ledger and step states; stamp = UTC build time plus the step-state fingerprint | stamp means a dated, fingerprinted record on the page, since the step title did not define it | the final pass asked for the page now, with no stamp format given | delete docs/qa/demo/index.html |

## Deviations

| # | Step | The plan said | What was done | Why | How to undo |
|---|---|---|---|---|---|

## Parked decisions

| # | Step | Question | Default taken for now | What it affects | How to answer |
|---|---|---|---|---|---|
