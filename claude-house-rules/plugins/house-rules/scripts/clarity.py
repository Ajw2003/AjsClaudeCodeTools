"""The shared writing checker for the clear-writing rule (rules/clear-writing.md, issue #247).

One list of writing checks, used by hook.py (replies, pages, issues) and plain_docs_check.py (plain
doc copies). Each detector takes plain text and returns findings: (kind, phrase, why). Stdlib only,
like hook.py. A pattern can't judge grammar or tone; the @house-rules:editor helper does that.
"""
import re

# --- shared word list -------------------------------------------------------------------------
# Small, editable list. Whole-word, case-insensitive. Add to it as new jargon slips through; it
# is meant to be tuned, not exhaustive on day one. (Moved from plain_docs_check.py.)
BANNED_WORDS = [
    "payload",
    "stdin",
    "stdout",
    "dispatch",
    "handler",
    "idempotent",
    "shim",
    "argv",
    "callback",
    "boilerplate",
    "serialize",
    "deserialize",
]

LONG_SENTENCE_WORDS = 40  # replies and pages; plain doc copies keep their own 20-word target

_QUOTE_CHARS = "\"'`“‘"
_SENTENCE_END_RE = re.compile(r"[.!?\n]")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’-]*")
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_CODE_SPAN_RE = re.compile(r"`[^`\n]*`")
_URL_RE = re.compile(r"https?://\S+")
_MD_LINK_URL_RE = re.compile(r"\]\([^)]*\)")


def prose(text):
    """The text a person reads: code blocks, code spans, URLs and link targets removed. A removed
    piece becomes a placeholder word, so it never joins the words either side of it into a phrase."""
    text = _FENCE_RE.sub("\n", text or "")
    text = _CODE_SPAN_RE.sub("CODE", text)
    text = _MD_LINK_URL_RE.sub("]", text)
    return _URL_RE.sub("LINK", text)


def _is_quoted(text, start):
    """A phrase opening right after a quote mark is being talked about, not asserted."""
    return start > 0 and text[start - 1] in _QUOTE_CHARS


def _is_label(text, end):
    """A phrase followed by a colon is a heading or list label ("Not checked:"), not a claim."""
    return text[end:end + 3].lstrip("*").startswith(":")


def _sentence_around(text, start, end):
    s = max((m.end() for m in _SENTENCE_END_RE.finditer(text, 0, start)), default=0)
    e = _SENTENCE_END_RE.search(text, end)
    return text[s:e.start() if e else len(text)]


# --- vague claims -----------------------------------------------------------------------------
# A hedge on something that could be measured, or a disclosure that something wasn't checked. The
# not-checked phrases moved here from hook.py (#89); lowercase-only "untested"/"unverified" so a
# handover card's own "UNTESTED:" marker never trips it.
_HEDGE_RE = re.compile(
    r"(?:\b(?:[Aa]bout|[Aa]round|[Rr]oughly|[Aa]pproximately|[Nn]early|[Aa]lmost)\s+\d[\d,.]*\b"
    r"|~\s?\d[\d,.]*"
    r"|\b[Ss]hould (?:work|be fine|pass)\b(?! (?:from|for|with|like|as|on|in|to)\b)"
    r"|\b[Pp]robably\b"
    r"|\bI think\b"
    r"|\b[Ii]t seems\b"
    r"|\b[Ss]eems to (?:work|pass|be fine)\b)"
)
_NOT_CHECKED_RE = re.compile(
    r"\b((?:[Nn]ot|[Hh]aven't|[Hh]ave not|[Dd]idn't|[Dd]id not|[Ww]asn't|[Ww]as not|[Hh]asn't|"
    r"[Hh]as not) (?:been )?(?:checked|verified|tested|run it|confirmed)|unverified|untested)\b"
)
# A reason in the same sentence makes a hedge or a disclosure the honest kind.
_REASON_RE = re.compile(
    r"\b(because|since|as there|no access|not available|unavailable|not installed|"
    r"not reachable|(?:can't|cannot) (?:reach|run|access|be measured|be counted)|requires|would need|"
    r"needs a|no .{0,20} (?:here|on this machine)|on your machine|prohibitively|had no|has no|"
    r"there (?:is|was) no|does(?:n't| not) have|did(?:n't| not) have|estimated?|isn't written yet)\b",
    re.IGNORECASE,
)


def unreasoned_not_checked(text):
    """'Not checked' phrases whose own sentence gives no reason the check could not run."""
    text = text or ""
    found = []
    for m in _NOT_CHECKED_RE.finditer(text):
        if _is_quoted(text, m.start()) or _is_label(text, m.end()):
            continue
        if _REASON_RE.search(_sentence_around(text, m.start(), m.end())):
            continue
        found.append(m.group(1).lower())
    return found


def vague_claims(text):
    """Hedges ("about 43", "should work", "probably") whose sentence gives no reason they can't be
    measured."""
    text = prose(text)
    found = []
    for m in _HEDGE_RE.finditer(text):
        if _is_quoted(text, m.start()) or _is_label(text, m.end()):
            continue
        if _REASON_RE.search(_sentence_around(text, m.start(), m.end())):
            continue
        found.append(m.group(0).strip())
    return found


# --- bare references --------------------------------------------------------------------------
# "#229" on its own, or "option B" / "choice 2" with no name after it. Allowed: "(#229)" after the
# thing's name, "#229 (title)", "#229: title", "#229, #230 and #231" inside one parenthesis.
_ISSUE_REF_RE = re.compile(r"(?<![\w/&])#(\d+)\b")
_OPTION_REF_RE = re.compile(r"\b([Oo]ption|[Cc]hoice|[Ss]tep)\s+([A-Z]|\d+)\b")

# "question 7" / "answer 1A", alone or after "round 1,", with no words saying what was asked.
_ROUND_REF_RE = re.compile(r"\b([Qq]uestion|[Aa]nswer)\s+(\d+[A-Z]?)\b")


def _inside_parens(text, pos):
    return text.rfind("(", 0, pos) > text.rfind(")", 0, pos)


def _inside_quotes(text, pos):
    """True when pos sits inside a quoted span on its own line: an example, not a reference."""
    line = text[text.rfind("\n", 0, pos) + 1:pos]
    return line.count('"') % 2 == 1 or line.count("“") > line.count("”")


def bare_references(text):
    text = prose(text)
    found = []
    for m in _ISSUE_REF_RE.finditer(text):
        after = text[m.end():m.end() + 3]
        if _inside_parens(text, m.start()) or after.startswith((" (", ":", "(", ' "', " “")):
            continue
        if re.match(r" \*{0,2}[A-Z]", text[m.end():m.end() + 4]):
            continue  # a title follows: "#224 Write the rule"
        if re.match(r",(?: now)? [\"“]", text[m.end():m.end() + 8]):
            continue  # a quoted title follows: #228, "Audit every house rule"
        if _is_quoted(text, m.start()) or _inside_quotes(text, m.start()):
            continue
        found.append(m.group(0))
    for m in _OPTION_REF_RE.finditer(text):
        after = text[m.end():m.end() + 3]
        if after.startswith((":", " (", " ·", " -", " —", "**:", " of")) or _inside_parens(text, m.start()):
            continue
        if _is_quoted(text, m.start()) or _inside_quotes(text, m.start()):
            continue
        found.append(m.group(0))
    for m in _ROUND_REF_RE.finditer(text):
        rest = text[m.end():m.end() + 14]
        if rest.startswith((":", " (", " -", " —")) or _inside_parens(text, m.start()):
            continue
        if re.match(r", (?!(?:question|answer|round)\b)\w", rest, re.I):
            continue  # a description follows: "question 1, where the name comes from"
        if _is_quoted(text, m.start()) or _inside_quotes(text, m.start()):
            continue
        found.append(m.group(0))
    return found


# --- repetition -------------------------------------------------------------------------------
# A four-word phrase used twice in one paragraph or list item, or three sentences in a row opening
# with the same word (not a small one like "the"). Phrases made only of small words don't count,
# nor do quoted words: quoting someone twice isn't repeating yourself. Each line is its own unit,
# so parallel list items that share a shape on purpose aren't flagged.
_QUOTED_RE = re.compile("\"[^\"\\n]*\"|\u201c[^\u201d\\n]*\u201d")
_SMALL = set("a an and are as at be but by for from has have i in is it its it's of on or so that the "
             "then there this to was were what when which will with you your my me we our not no".split())


def repetition(text):
    found = []
    for para in _QUOTED_RE.sub(" QUOTE ", prose(text)).split("\n"):
        words = [w.lower() for w in _WORD_RE.findall(para)]
        seen = {}
        for i in range(len(words) - 3):
            gram = tuple(words[i:i + 4])
            if all(w in _SMALL for w in gram) or {"code", "link", "quote"} & set(gram):
                continue
            if gram in seen and i - seen[gram] >= 4:
                phrase = " ".join(gram)
                if phrase not in found:
                    found.append(phrase)
            else:
                seen.setdefault(gram, i)
        sentences = [s for s in _SENTENCE_SPLIT_RE.split(para) if len(_WORD_RE.findall(s)) >= 4]
        sentences = [s for s in _SENTENCE_SPLIT_RE.split(para) if _WORD_RE.findall(s)]
        openings = [_WORD_RE.findall(s)[0].lower() for s in sentences]
        for i in range(len(openings) - 2):
            word = openings[i]
            if word not in _SMALL and word == openings[i + 1] == openings[i + 2] and word + " ..." not in found:
                found.append(word + " ...")
    return found


# --- jargon and long sentences ----------------------------------------------------------------
def jargon(text):
    text = prose(text)
    return [w for w in BANNED_WORDS if re.search(r"\b%s\b" % re.escape(w), text, re.IGNORECASE)]


def long_sentences(text, limit=LONG_SENTENCE_WORDS):
    out = []
    for s in _SENTENCE_SPLIT_RE.split(prose(text)):
        n = len(_WORD_RE.findall(s))
        if n > limit:
            out.append("%s... (%d words)" % (" ".join(s.split()[:6]), n))
    return out


# --- everything at once -----------------------------------------------------------------------
KINDS = (
    ("vague", vague_claims, "a vague number or claim with no reason it can't be measured"),
    ("not-checked", unreasoned_not_checked, "says something wasn't checked, without saying why it couldn't be"),
    ("bare-ref", bare_references, "a bare number or letter; name the thing it points at"),
    ("repeat", repetition, "the same phrase or opening, repeated"),
    ("jargon", jargon, "jargon a reader may not know"),
    ("long", long_sentences, "a sentence over %d words" % LONG_SENTENCE_WORDS),
)


def findings(text, skip=()):
    """[(kind, phrase, why)] for every finding in text."""
    out = []
    for kind, fn, why in KINDS:
        if kind in skip:
            continue
        for phrase in fn(text):
            out.append((kind, phrase, why))
    return out


# --- issue sections ---------------------------------------------------------------------------
ISSUE_SECTIONS = ("Depends on", "Depended on by", "Done when")


def missing_issue_sections(body):
    """The required issue headings that body lacks, as markdown headings or bold labels."""
    return [s for s in ISSUE_SECTIONS
            if not re.search(r"(?i)(?:#{1,6}\s*|\*\*)%s\b" % re.escape(s), body or "")]


# --- page text --------------------------------------------------------------------------------
_PAGE_BLOCK_RE = re.compile(r"const PAGE = \{(.*?)\n\};", re.DOTALL)
_JS_STRING_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b.*?</\1>", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")


def page_text(html):
    """What a reader sees on an HTML page: the visible text outside scripts and styles, plus the
    strings of a template page's PAGE block. Each string becomes its own paragraph."""
    parts = []
    m = _PAGE_BLOCK_RE.search(html or "")
    if m:
        for s in _JS_STRING_RE.findall(m.group(1)):
            s = s.replace('\\"', '"').replace("\\n", " ")
            if len(_WORD_RE.findall(s)) >= 3:
                parts.append(_TAG_RE.sub("", s))
    body = _TAG_RE.sub("\n", _SCRIPT_STYLE_RE.sub("", html or ""))
    parts.extend(line.strip() for line in body.splitlines() if len(_WORD_RE.findall(line)) >= 3)
    return "\n\n".join(parts)


if __name__ == "__main__":
    import sys
    data = sys.stdin.read()
    if len(sys.argv) > 1 and sys.argv[1] == "--page":
        data = page_text(data)
    for kind, phrase, why in findings(data):
        print("%-11s %s  (%s)" % (kind, phrase, why))
