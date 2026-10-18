# Triage Labels

The `triage` skill (mattpocock-skills) speaks in canonical roles. This file maps each role to the
label string this repo's GitHub tracker uses. Approved 2026-10-17; the proposal is
[docs/plans/triage-label-mapping.html](../plans/triage-label-mapping.html).

| Role              | Label in this repo | Meaning                                  |
| ----------------- | ------------------ | ---------------------------------------- |
| `bug`             | `bug`              | Something is broken                      |
| `enhancement`     | `Feature`          | New feature or improvement               |
| `needs-triage`    | `needs-triage`     | Maintainer needs to evaluate this issue  |
| `needs-info`      | `needs-info`       | Waiting on reporter for more information |
| `ready-for-agent` | `ready-for-agent`  | Fully specified, ready for an AFK agent  |
| `ready-for-human` | `ready-for-human`  | Requires human implementation            |
| `wontfix`         | `wontfix`          | Will not be actioned                     |

Triage never applies or removes `in progress` or `needs review`. The house-rules design loop reads
those two labels to decide whether an issue is being built or waiting for aj's testing, so a triage
change to them would move an issue's stage by accident.
