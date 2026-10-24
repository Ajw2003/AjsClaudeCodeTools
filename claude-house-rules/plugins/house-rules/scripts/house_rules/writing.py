"""house_rules.writing - the writing part (#359, step 2c of #340): the plain-summary, long-reply, visual and editor
checks, and the page writing note. Moved verbatim from hook.py; docs/4-systems/plugin-restructure.md, "Step 2c", says
what moved and why.

Imports only from house_rules.core."""

import os
import re

from house_rules import core
from house_rules.core import *  # noqa: F401,F403
from house_rules.core import (  # noqa: F401
    _AUDIT_COMMAND_TOOLS,
    _AUDIT_WRITE_TOOLS,
    _MD_FENCED_BLOCK_RE,
    _TOGGLE_OFF,
    _ag,
    _clear_writing_enabled,
    _common_git_dir,
    _issues_locate,
    _load_turn,
    _loop_enabled,
    _not_checked_note,
    _payload_cwd,
    _reply_links_page,
    _turn_tool_uses,
)


_VISUAL_EXT_RE = re.compile(
    r"\.(css|scss|sass|less|html?|jsx|tsx|vue|svelte|astro|uss|uxml|xaml|unity|prefab)$", re.IGNORECASE
)


_IMAGE_EXT_RE = re.compile(r"\.(png|jpe?g|gif|webp|bmp)$", re.IGNORECASE)


_SCREENSHOT_WORD_RE = re.compile(r"screenshot|playwright|puppeteer|capture|browser|computer", re.IGNORECASE)


# --- plain summary first (#98) -------------------------------------------------------------
# A reply reporting finished work opens with a plain summary a person can read on a phone. What
# can be checked from text: the opening is not code, not a table, not a pile of `names`, and no
# table anywhere is too wide for a phone screen. Measured on this repo's own session before
# shipping: the 4 real end-of-work replies all passed.
PLAIN_SUMMARY_MIN_CHARS = 600


PLAIN_OPENING_CHARS = 500


PLAIN_OPENING_MAX_CODE_SPANS = 3


PLAIN_MAX_TABLE_COLUMNS = 3


_GIT_COMMIT_OR_PUSH_RE = re.compile(r"\bgit\b[^|;&\n]*\b(commit|push)\b")


_MD_FENCE_RE = re.compile(r"```")


_MD_TABLE_ROW_RE = re.compile(r"(?m)^\s*\|.*\|\s*$")


_MD_CODE_SPAN_RE = re.compile(r"`[^`\n]+`")


_MD_LEADING_HEADING_RE = re.compile(r"^\s*#+ .*\n+")


def _plain_summary_enabled():
    return os.environ.get("HOUSE_RULES_PLAIN_SUMMARY", "on").strip().lower() not in _TOGGLE_OFF


def _plain_summary_problems(reply):
    """What stops this reply's opening reading as a plain summary on a phone - [] when nothing
    does, or when the reply is too short to need one."""
    if len(reply or "") < PLAIN_SUMMARY_MIN_CHARS:
        return []
    body = _MD_LEADING_HEADING_RE.sub("", reply, count=1)
    opening = body[:PLAIN_OPENING_CHARS].split("\n\n")[0]
    problems = []
    if _MD_FENCE_RE.search(opening):
        problems.append("it opens with a code block")
    if _MD_TABLE_ROW_RE.search(opening):
        problems.append("it opens with a table")
    spans = len(_MD_CODE_SPAN_RE.findall(opening))
    if spans > PLAIN_OPENING_MAX_CODE_SPANS:
        problems.append("its first paragraph carries %d code names" % spans)
    widest = max((l.count("|") - 1 for l in reply.splitlines() if _MD_TABLE_ROW_RE.match(l)), default=0)
    if widest > PLAIN_MAX_TABLE_COLUMNS:
        problems.append("it has a %d-column table, too wide for a phone" % widest)
    return problems


_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'\u2019-]*")


def _long_reply_words(reply, cwd=""):
    """The word count when the reply is too long and links no page or picture, else 0."""
    if not reply or _reply_links_page(reply, cwd):
        return 0
    words = len(_WORD_RE.findall(_MD_FENCED_BLOCK_RE.sub("", reply)))
    return words if words >= LONG_REPLY_WORDS else 0


def _long_reply_note(words):
    return (
        "House rules, show don't tell: this reply is %d words and links no page or picture. At %d words or more, "
        "the detail belongs on a page: move it there, keep the reply to a plain summary, the link, and "
        "numbered steps for what aj needs to do, and end on one question or next step." % (words, LONG_REPLY_WORDS)
    )


# #309 (incident 8 of #303): writing kinds that only report, to aj, until the restructure. The bare-reference
# check read "the option I suggested" as a bare "option I" and asked for the reply to be resent, twice in a row.
_WRITING_REPORT_ONLY = ("bare-ref",)


# #249: a page goes past the editor helper before aj reads it; a long reply does too only with
# HOUSE_RULES_EDITOR=on (#325: a long chat reply forcing a subagent run cost too many tokens).
EDITOR_NOTE = (
    "House rules, write it so nothing is left to guess: %s, and no @house-rules:editor helper ran this "
    "turn. Hand the text (or the page's path) to @house-rules:editor (Agent tool, subagent_type "
    "house-rules:editor), apply its rewrites, then send the result. HOUSE_RULES_CLEAR_WRITING=off "
    "turns this off; only pages are checked unless HOUSE_RULES_EDITOR=on adds long replies."
)


def _pages_changed_this_turn(transcript_path, cwd):
    """(pages, problem): docs/plans/*.html pages modified since aj's last message, however they
    were written. No pages when the project has no docs/plans folder or the message carries no
    timestamp; a timestamp that can't be read is reported as the problem."""
    import datetime
    _records, user, _detail = _load_turn(transcript_path)
    stamp = (user or {}).get("timestamp")
    top = _issues_locate(cwd)[0] or cwd
    plans = os.path.join(top, "docs", "plans")
    if not stamp or not os.path.isdir(plans):
        return [], None
    try:
        since = datetime.datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).timestamp()
    except ValueError as exc:
        return [], "house-rules: could not read aj's message time (%s), so pages written by a shell command were not checked." % exc
    pages = [n for n in os.listdir(plans) if n.lower().endswith((".html", ".htm"))]
    if _common_git_dir(top):
        # #284: a clone, checkout or merge sets every file's time, so in a repository a page counts only
        # when git shows it new, edited, or in a commit made since aj's message.
        try:
            _rc, status, _e = _ag(top, ["status", "--porcelain", "--untracked-files=all", "--", "docs/plans"])
            rc, log, err = _ag(top, ["log", "--since=@%d" % int(since), "--no-merges", "--name-only",
                                     "--format=", "--", "docs/plans"], check=False)
            if rc != 0:
                if "does not have any commits" not in err:  # a new repository has no log yet; status covers it
                    raise RuntimeError("git log failed: %s" % (err or "exit %d" % rc))
                log = ""
        except RuntimeError as exc:
            return [], "house-rules: git could not list this turn's pages (%s), so they were not checked." % exc
        touched = {os.path.basename(line[3:].strip().strip('"')) for line in status.splitlines() if len(line) > 3}
        try:
            # During an uncommitted merge, status lists every page the other branch brought in. A page
            # still identical to MERGE_HEAD's copy came from the merge, not this turn, so it does not count.
            if _ag(top, ["rev-parse", "-q", "--verify", "MERGE_HEAD"], check=False)[0] == 0:
                _rc, differ, _e = _ag(top, ["diff", "--name-only", "MERGE_HEAD", "--", "docs/plans"])
                differ = {os.path.basename(line.strip()) for line in differ.splitlines() if line.strip()}
                touched = {n for n in touched if n in differ}
        except RuntimeError as exc:
            return [], "house-rules: git could not compare pages with the merge (%s), so they were not checked." % exc
        touched |= {os.path.basename(line.strip()) for line in log.splitlines() if line.strip()}
        return sorted(os.path.join(plans, n) for n in pages if n in touched), None
    return sorted(os.path.join(plans, n) for n in pages if os.path.getmtime(os.path.join(plans, n)) >= since), None


def _editor_enabled():
    # #325: off unless set to something that is not an "off" value, i.e. "on".
    return os.environ.get("HOUSE_RULES_EDITOR", "off").strip().lower() not in _TOGGLE_OFF


def _editor_owed(written, tool_uses, reply):
    """What makes the editor helper owed this turn ("" when nothing does, or when it ran)."""
    for block in tool_uses:
        inp = block.get("input") if isinstance(block.get("input"), dict) else {}
        if block.get("name") in ("Agent", "Task") and str(inp.get("subagent_type", "")).endswith("editor"):
            return ""
    pages = [os.path.basename(p) for p in written if _PLANS_PAGE_RE.search(str(p).replace("\\", "/"))]
    if pages:
        return "this turn wrote the page %s" % ", ".join(sorted(set(pages)))
    if not _editor_enabled():  # #325: the long-reply trigger needs HOUSE_RULES_EDITOR=on
        return ""
    words = len(_WORD_RE.findall(_MD_FENCED_BLOCK_RE.sub("", reply or "")))
    if words >= LONG_REPLY_WORDS:
        return "this reply is %d words" % words
    return ""


def _writing_note(not_checked, writing, long_words):
    """#248: one end-of-reply note for every writing finding, in place of separate notes."""
    lines = []
    if not_checked:
        lines.append(_not_checked_note(not_checked))
    if writing:
        lines.append(
            "House rules, write it so nothing is left to guess: aj has already seen this "
            "reply, so send only the corrected sentences, not the whole reply again:\n" + "\n".join(
                "- \"%s\": %s" % (phrase, why) for _kind, phrase, why in writing[:12])
            + ("\n(and %d more)" % (len(writing) - 12) if len(writing) > 12 else "")
            + "\nCount what can be counted, name what you point at, say each thing once, and give a "
            "reason in the same sentence for anything that genuinely can't be measured. "
            "HOUSE_RULES_CLEAR_WRITING=off turns this off.")
    if long_words:
        lines.append(_long_reply_note(long_words))
    return "\n\n".join(lines)


def _plain_summary_note(problems):
    return (
        "House rules, plain summary first: this reply reports finished work, but %s. Rewrite it "
        "so it opens with a short plain-English summary - what is done, what it changes for the "
        "user, what is waiting on them - before any technical detail, in short paragraphs that "
        "read on a phone, with no table wider than three columns and jargon glossed on first "
        "use. Keep the technical detail; put it after the summary." % "; ".join(problems)
    )


def _visual_check_enabled():
    return os.environ.get("HOUSE_RULES_VISUAL_CHECK", "on").strip().lower() not in _TOGGLE_OFF


def _looked_at_result(tool_uses):
    """True when the turn captured or read an image of the result."""
    for block in tool_uses:
        name = block.get("name") or ""
        inp = block.get("input") if isinstance(block.get("input"), dict) else {}
        if _SCREENSHOT_WORD_RE.search(name):
            return True
        if name == "Read" and _IMAGE_EXT_RE.search(inp.get("file_path") or ""):
            return True
        if name in _AUDIT_COMMAND_TOOLS and _SCREENSHOT_WORD_RE.search(inp.get("command") or ""):
            return True
    return False


def _visual_note(files):
    return (
        "House rules, a visual change is checked by looking at it: this turn changed %s, but "
        "nothing in it captured or looked at the result. Before this turn ends, screenshot the "
        "same flow before (the committed version) and after, plus any flow the change adds, and "
        "say what the images show. If nothing can render here, say what stops it and name the "
        "screenshot the user should take." % ", ".join(files[:6])
    )


_PLANS_PAGE_RE = re.compile(r"(?:^|[\\/])docs[\\/]plans[\\/][^\\/]+\.html?$", re.IGNORECASE)


def _page_writing_note(file_path):
    """#248: the shared writing checker on a page just written under docs/plans/, or "" when the
    file is not such a page, is clean, or the check is off."""
    if not _PLANS_PAGE_RE.search(file_path.replace("\\", "/")) or not _clear_writing_enabled():
        return ""
    if clarity is None:
        return CLARITY_ERROR
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            html = f.read()
    except OSError as exc:
        return "house-rules: the page writing check could not read %s (%s)." % (file_path, exc)
    found = clarity.findings(clarity.page_text(html), skip=("not-checked",) + _WRITING_REPORT_ONLY)
    if not found:
        return ""
    return ("House rules, write it so nothing is left to guess: the page %s has %d thing(s) to fix "
            "before you publish it:\n%s\nCount what can be counted, name what you point at, and say "
            "each thing once. Then hand the page to @house-rules:editor before publishing."
            % (os.path.basename(file_path), len(found),
               "\n".join("- \"%s\": %s" % (p, why) for _k, p, why in found[:12])))


# The writing checks of the end-of-reply dispatcher (event_handover in hook.py), moved out of it verbatim (#359).
def handover_turn_writes(turn_records):
    """(files written this turn, True when the turn committed or pushed): what the parity, visual and plain-summary
    checks all read from the transcript."""
    written_now = []
    committed_now = False
    for block in _turn_tool_uses(turn_records):
        inp = block.get("input") if isinstance(block.get("input"), dict) else {}
        if block.get("name") in _AUDIT_WRITE_TOOLS:
            fp = inp.get("file_path") or inp.get("notebook_path")
            if fp and fp not in written_now:
                written_now.append(fp)
        elif block.get("name") in _AUDIT_COMMAND_TOOLS and _GIT_COMMIT_OR_PUSH_RE.search(inp.get("command") or ""):
            committed_now = True
    return written_now, committed_now


def handover_plain_check(written_now, committed_now, have_reply, reply_text):
    """The plain-summary problems of the reply ([] when none)."""
    plain_problems = []
    if (written_now or committed_now) and _plain_summary_enabled() and have_reply:
        plain_problems = _plain_summary_problems(reply_text)
    return plain_problems


def handover_page_editor_check(transcript_path, payload, written_now, turn_records, have_reply, reply_text):
    """(notes for pages a shell command wrote, what makes the editor owed or None, trace lines)."""
    shell_page_notes = []
    editor_owed = None
    trace_lines_early = []
    if _clear_writing_enabled():
        # A page written by a shell command never passes the Write hook (found in the real
        # run, #250), so pages changed since aj's message are checked here too.
        changed, page_problem = _pages_changed_this_turn(transcript_path, _payload_cwd(payload))
        if page_problem:
            trace_lines_early.append(page_problem)
        shell_pages = [pg for pg in changed if pg not in written_now]
        for pg in shell_pages:
            note = _page_writing_note(pg)
            if note:
                shell_page_notes.append(note)
        editor_owed = _editor_owed(written_now + shell_pages, list(_turn_tool_uses(turn_records)),
                                   reply_text if have_reply else "")
    return shell_page_notes, editor_owed, trace_lines_early


def handover_visual_check(written_now, turn_records):
    """The visual files written this turn that nothing looked at ([] when none)."""
    visual_files = []
    if written_now and _visual_check_enabled():
        visual = [os.path.basename(p) for p in written_now if _VISUAL_EXT_RE.search(p)]
        if visual and not _looked_at_result(list(_turn_tool_uses(turn_records))):
            visual_files = visual
    return visual_files


def handover_long_reply(payload, have_reply, reply_text):
    return _long_reply_words(reply_text, _payload_cwd(payload)) if (have_reply and _loop_enabled()) else 0


# --- #344: skipping a check is aj's call; an unasked fix outside the request becomes an issue --------------
# Round 2, answer 12: the agent never decides to skip a check on its own. Round 1, answer 6: an obvious bug
# outside the request becomes an issue, named in the reply, not an unasked fix.
_SKIP_SAID_RE = re.compile(
    r"\b(?:skipp(?:ed|ing)|(?:did not|didn't|have not|haven't|will not|won't|did no|am not|'m not) "
    r"(?:run(?:ning)?|do(?:ing)?)(?: (?:it|that|them|the \w+))?"
    r"|(?:left|leaving) (?:it|that|them|the \w+) (?:out|unrun)|not (?:run|rerun))\b", re.IGNORECASE)
_SKIP_REASON_RE = re.compile(
    r"\b(?:too (?:long|slow|expensive|costly)|takes? (?:over|more than|about|around)? ?\d+ ?(?:min|minutes|hours?)|"
    r"\d+ ?(?:min|minutes|hours?) (?:to run|long)|long[- ]running|slow|costs? (?:money|\$|real)|costly|expensive|"
    r"paid|billing|no access|(?:can't|cannot|can not|couldn't) (?:reach|access|log in)|unreachable|"
    r"another machine|other machine|your machine|different machine|account|credentials|time)\b", re.IGNORECASE)
_SKIP_QUESTION_RE = re.compile(
    r"\b(?:skip|run (?:it|that|them|this)|want me to|should I|shall I|ok(?:ay)? (?:to|if)|is that ok(?:ay)?|"
    r"do you want|would you like)\b", re.IGNORECASE)
_SKIP_RULE_QUOTE = (
    "an agent never decides on its own to skip a check; when a check is over 10 minutes, costs money, or "
    "needs a machine or account it can't reach, it names the check and asks aj plainly whether to skip it")


def _reply_asks_to_skip(text):
    """True when some sentence of the reply is a question about skipping or running a check."""
    for part in re.split(r"(?<=[?])", text):
        if part.rstrip().endswith("?") and _SKIP_QUESTION_RE.search(part):
            return True
    return False


def skipped_check_reasons(reply):
    """Sentences saying a check was skipped or not run for time, cost or an unreachable machine or account,
    when the reply asks aj nothing about skipping ([] when none, or when it asks)."""
    if not reply or clarity is None:
        return []
    text = clarity.prose(reply)
    found = []
    for m in _SKIP_SAID_RE.finditer(text):
        if clarity._is_quoted(text, m.start()):
            continue
        sentence = clarity._sentence_around(text, m.start(), m.end())
        if _SKIP_REASON_RE.search(sentence):
            found.append(" ".join(sentence.split())[:120])
    if found and _reply_asks_to_skip(text):
        return []
    return found


def _skipped_check_note(sentences):
    return (
        "House rules, evidence before claims: this reply says a check was skipped or not run for time, cost "
        "or an unreachable machine or account (%s) and does not ask aj whether to skip it. aj's rule: %s. "
        "Name the check and ask aj plainly in this reply (\"Should I skip X?\"), or run it."
        % ("; ".join("\"%s\"" % x for x in sentences[:3]), _SKIP_RULE_QUOTE)
    )


_UNASKED_FIX_RE = re.compile(
    r"\b(?:while I was (?:there|in there|at it)|I also (?:fixed|patched|cleaned up)|unrelated (?:fix|bug fix|change))\b",
    re.IGNORECASE)
_ISSUE_NUMBER_RE = re.compile(r"(?<![\w/&])#\d+\b")


def unasked_fix_phrases(reply):
    """Phrases saying an unrequested fix was made, when the reply names no issue number ([] otherwise)."""
    if not reply or clarity is None:
        return []
    text = clarity.prose(reply)
    if _ISSUE_NUMBER_RE.search(text):
        return []
    return [m.group(0).lower() for m in _UNASKED_FIX_RE.finditer(text) if not clarity._is_quoted(text, m.start())]


def _unasked_fix_note(phrases):
    return (
        "House rules, stay in scope (a note, not a block): this reply says it fixed something outside the "
        "request (%s) and names no issue. An obvious bug outside the request becomes an issue, named in "
        "the reply, not an unasked fix. File the issue and name it, or say the fix was asked for."
        % ", ".join(sorted(set(phrases)))
    )


core.register_post_tool("artifact", _page_writing_note)
