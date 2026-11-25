# Review of scripts/review_plan.py (acceptance test 3)

Mode: `code`. Target: `claude-house-rules/plugins/house-rules/scripts/review_plan.py` (as merged at plugin 2.94.0). One reviewer, no findings written by it; this file is saved by the main session, as `commands/review.md` says. The reply is kept as the reviewer wrote it, with one line of the reviewer's own commands summarised at the end.

17 findings: 2 high, 7 medium, 8 low. The main session reproduced four of them before this was saved (see the end).

- [high] review_plan.py:65: the design lookup strips only `-plan`, so a `<date>-<name>-build-plan.html` plan, the most common name in docs/plans, keeps `-build` in its base and gets `design: none` even when the design sits next to it. Tested: `mode docs/plans/2026-11-22-wait-and-visual-checks-build-plan.html` gives `design: none` while `2026-11-22-wait-and-visual-checks.html` exists. Fix: use `re.sub(r"-(build-)?plan$", "", stem)`.
- [high] review_plan.py:65: the lookup also misses folder-style plans such as `docs/plans/2026-11-23-modular-tests/build-plan.html` (base `build`, so `proposal.html` is never found; tested, it gives `design: none`), and it misses a design whose date prefix differs from the plan's, because the dated stem is matched with `endswith`. Fix: strip the leading date before matching, and when the plan is `build-plan.html` look for its folder's sibling design or proposal page.
- [medium] review_plan.py:67: `f.stem.endswith(base)` also matches unrelated pages such as `old-<name>.html`, then `sorted(...)[-1]` quietly picks one, and a `.page.json` or `-qa` page with the same suffix could win in the future. Fix: compare the date-stripped stem for equality, and print every candidate when there is more than one instead of choosing silently.
- [medium] review_plan.py:59: a folder-style plan gives the report name `review-build-plan-<date>`, so every such feature reviewed on the same day writes to the same docs/qa folder (tested). Fix: when the stem is a generic one (`build-plan`, `proposal`, `design`), use the parent folder name with its date stripped.
- [medium] review_plan.py:45: codebase mode needs the exact string `.`. `./`, `$PWD`, or the repo's absolute path give `mode: code` (tested), so one code reviewer gets the whole repo instead of the batched sweep. Fix: test `tpath.resolve() == Path.cwd().resolve()`, or compare against the repo top-level from `git rev-parse --show-toplevel`.
- [medium] review_plan.py:73: a missing `--root` directory or a missing git binary raises an uncaught FileNotFoundError and prints a traceback with rc=1 (tested with `units --root /nonexistent`), not the documented clean error. Fix: catch OSError around `subprocess.run`, print `error: ...` and exit 3.
- [medium] review_plan.py:9: the docstring justifies 8 files per batch with 8 x 7.1 s = 57 s under a 60 s deadline. The notice at line 108 then says code files take longer and 7.1 s is a minimum, so an 8-file code batch can run past the deadline its size was chosen to meet. Fix: base BATCH on a measured code-file time, or leave headroom (for example 6), and state which figure was used.
- [medium] review_plan.py:37: TARGET is resolved against cwd, but `--root` is ignored for it, and codebase mode (`.`) checks that cwd exists while `units`/`batches` sweep `--root`. A `--root` different from cwd makes the mode line and the sweep describe different trees. Fix: resolve TARGET against `root`, or drop `--root` from `mode`.
- [low] review_plan.py:30: a bare word `style` right after TARGET is taken as the `--style` flag, so criteria that start with "style" (for example an image review on "style consistency") silently switch the mode to style and lose that word. The usage text at line 4 does not mention this form. Fix: accept only `--style`, or document the positional keyword and report it.
- [low] review_plan.py:80: tracked files that are deleted in the work tree, submodule gitlinks and symlinked directories are dropped by `is_file()` without a word, so the folder and file counts quietly differ from what git listed. Fix: count the skipped paths and print `skipped: <n> (<reason>)`.
- [low] review_plan.py:10: the docstring lists only exits 0 and 2. Exit 3 (git failure, line 77) is missing, and the `mode` output list at line 4 leaves out the `criteria:` line printed at line 63. Fix: add exit 3 and `criteria:` to the docstring.
- [low] review_plan.py:41: error messages go to stdout, mixed into the `key: value` lines the command parses. Fix: print errors to `sys.stderr`.
- [low] review_plan.py:57: the conditional is dead. When `a.root == "."`, `root` is already `Path(".").resolve()`, which equals `Path.cwd().resolve()`. Fix: use `name = root.name`.
- [low] review_plan.py:89: `sorted(units[u])` is redundant, because `units_of` already adds the files in sorted order. Fix: use `fs = units[u]`.
- [low] review_plan.py:104: the 12-folder notice threshold is an unnamed magic number, unlike BATCH, SEC and TOK. Fix: add a named constant `NOTICE_FOLDERS = 12` next to them.
- [low] review_plan.py:136: after a BrokenPipeError, stdout still holds buffered data. The flush at interpreter shutdown fails and Python can exit 120 instead of the returned 0. Fix: use the standard recipe, `os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())`, before returning. (Reviewer: from how Python handles a failed flush at exit; not tested.)
- [low] review_plan.py:49: only `.html` is checked, so a `.htm` page is sent to code mode. Fix: check `suffix in {".html", ".htm"}`.

## What the main session checked before saving

Run against the merged tree, each reproduced as the reviewer said:
- `mode docs/plans/2026-11-22-wait-and-visual-checks-build-plan.html` printed `design: none` although `2026-11-22-wait-and-visual-checks.html` exists.
- `mode ./` and `mode` with the absolute repo path both printed `mode: code`.
- `units --root /nonexistent` printed a `FileNotFoundError` traceback and exited 1.
- `mode docs/plans/2026-11-23-modular-tests/build-plan.html` printed `design: none` and the report name `review-build-plan-2026-11-24`.

The other findings were not re-run by the main session.

## Reviewer's own commands (summary)

Read `rules/detail/review-modes.md` and `scripts/review_plan.py`; grepped for callers; listed plan pages with `git ls-files`; ran `review_plan.py mode` on the targets named in the findings. It ran nothing that writes. It did not run `verify.py`.
