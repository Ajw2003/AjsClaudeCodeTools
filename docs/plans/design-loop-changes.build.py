"""Builds the item data for docs/plans/design-loop-changes.html from git (python THIS_FILE OUT.json), with tools/diff_parts.py doing every count.
Each item lists its files; a Python file's parts are grouped under plain words. Every changed part
of hook.py must land in exactly one item, or the build stops."""
import json, os, re, subprocess, sys
REPO = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True).stdout.strip()
sys.path.insert(0, os.path.join(REPO, "tools"))
import diff_parts as dp

BASE, HEAD = "origin/main", "HEAD"
P = "claude-house-rules/plugins/house-rules/"
HOOK = P + "scripts/hook.py"
_cache = {}


def info(path):
    if path not in _cache:
        _cache[path] = dp.parts(REPO, BASE, HEAD, path)
    return _cache[path]


used_hook = []


def frow(path, groups=None):
    """[path, added, removed, [[plain, a, r], ...]]. groups: [(plain, [part names])] for a slice of
    a file; None for the whole file (Markdown files list their sections)."""
    d = info(path)
    by = {n: (a, r) for n, a, r in d["parts"]}
    if groups is None:
        parts = [] if len(d["parts"]) <= 1 or not path.endswith(".md") else [[n, a, r] for n, a, r in d["parts"]]
        return [path, d["added"], d["removed"], parts]
    rows, ta, tr = [], 0, 0
    for plain, names in groups:
        missing = [n for n in names if n not in by]
        assert not missing, (path, missing)
        if path == HOOK:
            used_hook.extend(names)
        a = sum(by[n][0] for n in names); r = sum(by[n][1] for n in names)
        rows.append([plain, a, r]); ta += a; tr += r
    return [path, ta, tr, rows]


def pages():
    out = subprocess.run(["git", "-C", REPO, "diff", "--numstat", BASE, HEAD, "--", "docs/plans"],
                         capture_output=True, text=True, check=True).stdout.split("\n")
    rows = [[l.split("\t")[2].replace("docs/plans/", ""), int(l.split("\t")[0]), int(l.split("\t")[1])] for l in out if l.strip()]
    return ["docs/plans/", sum(r[1] for r in rows), sum(r[2] for r in rows), rows]


I = []
I.append(["new", "Show-don't-tell rule", "Loaded every session in its own slot.", None,
  "The request is the scope; every plan reaches you as a page; options with my suggestion, you pick; no code before an approved design; issue labels say whose move it is.",
  ["Plans and choices arrived as walls of text, and code could start before you'd seen a design.", "A rule that every plan, design and choice reaches you as a page, as a proposal you approve or deny.", "You see and decide the design before anything is built."],
  [frow(P + "rules/show-dont-tell.md")]])
I.append(["new", "Its detail file", "The why behind each part.", None,
  "The request as scope, a page is a proposal, check what exists first, depth matches the task, the code lock, logging first, a home for each feature, the handover page, helpers.",
  ["The reasons behind the rule lived only in our chat.", "A detail file with each part's why and the incident that prompted it.", "Later sessions apply the rule to cases it doesn't name."],
  [frow(P + "rules/detail/show-dont-tell.md")]])
I.append(["new", "Rule loader", "A new start-of-session hook for the two new rules.", None,
  "The main rules file was 47 characters from its limit, so the new rules load in their own slot. A missing file is named while the other still loads, and the voice switch moved here with the voice.",
  ["The main rules file had no room for another rule.", "A second start-of-session loader that reads the two new rules, each reported if missing.", "Both rules reach every session without crowding the others."],
  [frow(HOOK, [("The loader and its list of rule files", ["event_showrule", "SHOWRULE_FILES", "EVENTS"]),
               ("The voice switch, moved here from the main loader", ["_VOICE_HEADING", "_apply_voice_toggle", "event_inject"])]),
   frow(P + "hooks/hooks.json"), frow(P + "scripts/run.sh"), frow("claude-house-rules/README.md")]])
I.append(["new", "Stages and approvals", "Your messages move a feature through Design, Plan, Build, QA, Done.", None,
  "\"Design approved\", \"Build plan approved\", \"QA passed\", \"QA failed\" and \"skip design\" move the stage. A bare \"approved\" moves nothing. The stage is kept in a file git never commits.",
  ["Nothing tracked where a feature was, or whether you had approved it.", "A stage for each feature, moved only by your own approval messages.", "Only you can move work forward, and a session picks up where the last one stopped."],
  [frow(HOOK, [("Reading your messages and moving the stage", ["_loop_apply", "_loop_scope_note", "event_scope", "SCOPE_REMINDER"]),
               ("The stage file and the approval phrases", ["LOOP_FILE", "LOOP_STAGE_NAMES", "_LOOP_DESIGN_RE", "_LOOP_PLAN_RE", "_LOOP_QA_RE", "_LOOP_SKIP_RE", "_LOOP_BARE_RE", "_loop_enabled", "_loop_read", "_loop_write"]),
               ("Reading a feature's name from your message", ["_loop_name", "_LOOP_NAME_END_RE"])])]])
I.append(["new", "Code lock", "Source edits are refused outside the Build stage.", None,
  "Docs and .md files stay open. Helpers' edits are held too. In Build, an edit is refused while any issue isn't labelled in progress.",
  ["Nothing stopped a code edit before you'd approved a design.", "A lock that refuses source edits outside the Build stage.", "No code appears that you haven't approved, and docs stay editable."],
  [frow(HOOK, [("The lock itself", ["_loop_gate"]), ("The shared \"is this a source file?\" filter", ["_gated_edit", "_issues_gate"]),
               ("The lock wired into the before-an-edit hook", ["event_commitgate"])])]])
I.append(["new", "Logged first", "An approval only counts after the decisions log changed.", None,
  "If nothing was logged since the last approval, the stage doesn't move, and I'm told to log it and ask again.",
  ["An approval could move a stage with nothing written down.", "A check that the decisions log has a new entry before an approval counts.", "Every stage leaves a record you can read later."],
  [frow(HOOK, [("Fingerprinting the decisions log", ["LOOP_LOG", "_loop_log_mark", "_loop_unlogged"])])]])
I.append(["new", "Feature home", "A build plan needs at least two labelled issues.", None,
  "Issues made during planning are recorded, whether made from a terminal or with the GitHub tool.",
  ["Issues made with the GitHub tool were invisible to the hooks.", "A record of every issue made during planning, by either route.", "Each feature has its issues before building starts."],
  [frow(HOOK, [("Recording created issues", ["_created_issue", "_loop_record_issues", "_issues_record", "_GITHUB_ISSUE_WRITE_RE", "_GH_PREFIX", "event_autosave"])])]])
I.append(["new", "Label check", "Every stage move reads the issue labels.", None,
  "Read from GitHub, or from my recorded label changes when GitHub can't be read. Swapping every issue to needs review starts QA; after QA failed, the labels go back to in progress before the redo.",
  ["Labels were moved by hand and nothing checked them.", "A check at every stage move that each issue's label matches the stage.", "An issue's label always tells you whose move it is."],
  [frow(HOOK, [("Reading labels from GitHub", ["_loop_key", "_loop_gh_labels", "_loop_labels", "LOOP_GH_SECONDS", "LOOP_LABELS_FILE_ENV"]),
               ("Recording my label changes", ["_label_changes", "_gh_label_flags", "_GH_ISSUE_EDIT_RE", "_GH_LABEL_FLAG_RE", "_loop_record_labels"]),
               ("Judging labels against the stage", ["_loop_wrong", "_loop_to_qa", "_LOOP_QA_NOTE", "_loop_label_refusal"]),
               ("Naming wrong labels at the end of a reply", ["_loop_stop_line"])])]])
I.append(["new", "Helper note", "A helper starts knowing the feature, stage and issues.", None,
  "It builds only approved steps and never designs or approves.",
  ["A helper started with no idea which feature it was inside.", "A start-up note giving it the feature, its stage and its issues.", "Helpers build only what you approved."],
  [frow(HOOK, [("The note and where it's added", ["_loop_helper_note", "event_subagentrules"])])]])
I.append(["new", "Long-reply reminder", "Over 200 words with no page link gets a reminder.", None,
  "Code blocks aren't counted.",
  ["Long replies buried the one step you needed.", "A reminder when a reply runs over 200 words with no page.", "Detail goes onto a page; the reply stays short."],
  [frow(HOOK, [("Counting a reply's words", ["LONG_REPLY_WORDS", "_PAGE_LINK_RE", "_MD_FENCED_BLOCK_RE", "_WORD_RE", "_long_reply_words", "_long_reply_note"])])]])
I.append(["new", "Handover page template", "The four-part page every proposal is built from.", None,
  "In short, Changes, Choices, Wrap-up, filled from one block. Since v2, New items carry three labelled boxes and any opened item lists its files.",
  ["Each page was built by hand, and they didn't match.", "One template every page is filled from.", "Every page reads and works the same way."],
  [frow(P + "templates/handover-page.html")]])
I.append(["new", "Clear writing rule", "\"Write it so nothing is left to guess\".", None,
  "Proper sentences, said once, explicit context, measured numbers, named references, exact inputs, done-criteria. It merged the plain-language rule and three other lines.",
  ["How my writing should read was spread over three rules, with nothing checking it.", "One rule for clarity and wording, with its detail and examples.", "Replies, pages and issues read as plain English and leave nothing to guess."],
  [frow(P + "rules/clear-writing.md"), frow(P + "rules/detail/clear-writing.md")]])
I.append(["new", "Shared writing checker", "Vague claims, bare references, repetition, jargon, long sentences.", None,
  "One module for the hook and the plain-docs checker, calibrated on 93 real replies. The end-of-reply check gives one note listing every finding.",
  ["Vague numbers like \"about 43\" and bare \"#229\"s went out unchecked.", "A checker that reads every reply and page for them.", "You get counted numbers and named references."],
  [frow(P + "scripts/clarity.py"),
   frow(HOOK, [("Loading the checker", ["(top of file)"]), ("The end-of-reply check, wired to every new note", ["event_handover"]),
               ("One writing note per reply", ["_clear_writing_enabled", "_writing_findings", "_writing_note"]),
               ("The not-checked detector, moved into the checker", ["_unreasoned_not_checked", "_NOT_CHECKED_RE", "_REASON_RE", "_SENTENCE_END_RE"])]),
   frow(P + "scripts/plain_docs_check.py")]])
I.append(["new", "Issue sections", "An issue without its three sections is refused.", None,
  "\"Depends on\", \"Depended on by\" and \"Done when\", for the GitHub tool and gh alike.",
  ["Issues could be made with no dependencies or done-criteria.", "A refusal for any issue missing those three sections.", "Every issue says what blocks it and when it's done."],
  [frow(HOOK, [("Refusing an issue made with gh", ["_issues_guard", "ISSUE_SECTIONS_DENY"]), ("Refusing an issue made with the GitHub tool", ["event_guardgithub"])])]])
I.append(["new", "Page check", "A page under docs/plans is checked when it's written.", None,
  "Pages written with a shell command are checked when the reply ends; the real run found that gap.",
  ["Pages were checked only by my own search.", "The same checker run on every page under docs/plans, however it was written.", "A page is fixed before you see it."],
  [frow(HOOK, [("Checking a page", ["_PLANS_PAGE_RE", "_page_writing_note", "event_artifact"]), ("Finding pages written by a shell command", ["_pages_changed_this_turn"])])]])
I.append(["new", "Editor helper", "Rewrites pages and long replies.", None,
  "It runs on Sonnet; the end-of-reply check reminds me when it didn't run.",
  ["No one read my pages and long replies for grammar and tone before you did.", "An editor helper that returns rewrites before they go out.", "Clipped phrases like \"checks it's Build\" are fixed before you read them."],
  [frow(P + "agents/editor.md"), frow(HOOK, [("The reminder when it didn't run", ["EDITOR_NOTE", "_editor_owed"])])]])
I.append(["new", "Counting tool", "Splits a file's changes into its parts.", None,
  "Every count on this page comes from it, and anyone can rerun it: python tools/diff_parts.py BASE HEAD PATH.",
  ["The counts came from a script in my scratchpad.", "A tool in the repo, with a check, that reproduces every count.", "You can check any number on a changes page yourself."],
  [frow("tools/diff_parts.py"), frow("tools/verify_tools.py")]])
I.append(["new", "System docs", "How the design loop and the clear writing check work.", None,
  "Each covers its pieces, the rules that must stay true, and the traps already hit.",
  ["Neither system had a doc.", "A system doc for each, plus rows in the systems index.", "Anyone changing them can read how they work first."],
  [frow("docs/4-systems/design-loop.md"), frow("docs/4-systems/clear-writing.md"), frow("docs/4-systems/README.md")]])
I.append(["new", "Design pages", "Every proposal you saw, in docs/plans.", None,
  "From the first show-don't-tell draft to this page.",
  ["Proposals lived in chat.", "A page in the repo for every proposal, plan and QA.", "The history of each choice stays as you saw it."],
  [pages()]])
I.append(["chg", "Main rules file", "Sections moved into the new rules.", ["Match response depth, Build only what was asked, Plain language and the voice", "Pointers to Show, don't tell and Write it so nothing is left to guess"], "Its injected size fell from 9,653 to 8,874 characters.", None, [frow(P + "rules/house-rules.md")]])
I.append(["chg", "Other rule files", "Lines moved into the new rules.", ["Exact inputs in Deliver a whole workflow; a plan line in the coding standards; a pointer in the Unity rule", "Pointers to the new rules"], "Nothing in them was lost; each moved line is in the new rules' detail.", None,
  [frow(P + "rules/detail/deliver-workflow.md"), frow(P + "rules/standards/coding-philosophy.md"), frow(P + "rules/detail/unity-tools-first.md"), frow(P + "skills/plain-docs/SKILL.md")]])
I.append(["chg", "Test suite", "Grew from 616 checks to 684.", ["616 checks on main", "684 checks, all passing"], "Covers every piece above. It also fixes the stale-temp-file flake: each run now gets its own temp folder.", None, [frow(P + "scripts/verify.py"), frow("docs/4-systems/verify-suites.md")]])
I.append(["chg", "Spacing in the hook", "Blank lines between new parts.", ["None", "Blank lines"], "The counting tool gives these to the code just above them.", None,
  [frow(HOOK, [("Blank lines", ["read_payload", "event_profile", "_open_issues_text", "_plain_summary_note"])])]])
I.append(["chg", "Version and docs", "Plugin version, and the state, today, decisions and architecture docs.", ["2.62.0", "2.65.1"], "2.63.0 the design loop, 2.64.0 the label check, 2.64.1 names, 2.65.0 clear writing, 2.65.1 this page's format.", None,
  [frow(P + ".claude-plugin/plugin.json"), frow("docs/architecture.md"), frow("docs/3-state/ProjectState.md"), frow("docs/5-today/Today.md"), frow("docs/6-decisions/Decisions.md")]])
for path, old in [("build-what-asked.md", "Build only what was asked"), ("response-depth.md", "Match response depth"), ("plain-language.md", "Plain language")]:
    d = info(P + "rules/detail/" + path)
    I.append(["chg", old + " (detail)", "Deleted; moved into a new rule.", ["%d lines" % d["removed"], "Removed"], "Its text lives on in a new rule's detail file.", None, [frow(P + "rules/detail/" + path)]])

# Every changed part of the hook is on the page exactly once.
allparts = [n for n, a, r in info(HOOK)["parts"]]
dup = sorted({n for n in used_hook if used_hook.count(n) > 1}); left = sorted(set(allparts) - set(used_hook))
assert not dup and not left, ("duplicated", dup, "unplaced", left)
# Every changed file outside docs/plans is on the page.
listed = {f[0] for it in I for f in it[6]}
changed = [l.split("\t")[2] for l in subprocess.run(["git", "-C", REPO, "diff", "--numstat", BASE, HEAD], capture_output=True, text=True).stdout.splitlines()]
missing_files = [c for c in changed if not c.startswith("docs/plans/") and c not in listed]
assert not missing_files, missing_files
json.dump(I, open(sys.argv[1], "w"), ensure_ascii=False)
print(len(I), "items;", sum(1 for i in I if i[0] == "new"), "new; hook parts placed:", len(used_hook), "of", len(allparts))
