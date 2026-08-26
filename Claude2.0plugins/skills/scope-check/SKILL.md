---
name: scope-check
description: Self-audit checklist for staying terse, asking on ambiguity, taking the simplest path, and not over-building. Load before finalizing a plan or a non-trivial change, or run explicitly as /scope-check.
---

Before finalizing a plan, a design, or a non-trivial change, check all four:

1. **Depth matches the task.** Is the reasoning/response longer than this problem actually requires? If the task is simple, the answer should be short.
2. **No unresolved ambiguity.** Is there any requirement I decided on my own instead of asking about? If yes, ask before proceeding instead of guessing.
3. **Simplest path.** Is there a more direct way to satisfy exactly what was asked, with less code, fewer files, or fewer new abstractions?
4. **No speculative scope.** Am I building or handling anything the user didn't actually ask for ("in case they also want X/Y/Z")? If so, cut it — it can be added later if actually requested.

If any check fails, fix it before presenting the plan or the change — don't note the issue and proceed anyway.
