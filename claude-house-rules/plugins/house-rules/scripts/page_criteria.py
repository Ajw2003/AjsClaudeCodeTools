#!/usr/bin/env python3
"""page_criteria.py - reads a page's HTML and names each failed basic, one plain sentence per miss.

    page_criteria.py <page.html> [--type proposal|build-plan|qa|review|art] [--visual]

The type comes from --type, else <meta name="house-rules-page" content="...">. A page that make_page.py
built (its builder mark in the first 4096 characters) is not read. Basic 7 (phone width, light and dark)
is not in check(); --visual runs make_page.py's visual check on the file.

Exit codes: 0 all basics met, 1 some failed, 2 unreadable file.

STDLIB ONLY, Python 3.8+.
"""

import os
import re
import sys
from html.parser import HTMLParser

MAX_BLOCK_WORDS = 60  # docs/page-style.json overrides it via check(max_block_words=)
MAX_SUMMARY_WORDS = 40
TYPES = ("proposal", "build-plan", "qa", "review", "art")
# #594: the review stamp. Pages of these types need none.
STAMP_EXEMPT = ("review", "qa")
STAMP_MAX_ROUNDS = 2
_STAMP_LINE_RE = re.compile(r'^<meta name="house-rules-reviewed" content="([^"]*)">[ \t]*\r?\n?', re.M)
_PAGE_META_RE = re.compile(r'<meta name="house-rules-page" content="([^"]*)"')


def _stamp_hash(html):
    import hashlib
    # CRLF and LF hash alike: a page saved with Windows line endings is not a changed page.
    body = _STAMP_LINE_RE.sub("", html, count=1).replace("\r\n", "\n")
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def stamp_line(html, verdict, rounds):
    """The stamp meta line for this final HTML (the hash skips the line itself)."""
    return '<meta name="house-rules-reviewed" content="%s;%s;%d">\n' % (_stamp_hash(html), verdict, rounds)


def stamp_problem(html):
    """"" when the page needs no stamp or carries a current one; else the reason it is owed."""
    m = _PAGE_META_RE.search(html)
    if m and m.group(1).strip() in STAMP_EXEMPT:
        return ""
    s = _STAMP_LINE_RE.search(html)
    if not s:
        return "no review stamp"
    parts = s.group(1).split(";")
    try:
        ok = len(parts) == 3 and parts[1] in ("clean", "open-risks") and 1 <= int(parts[2]) <= STAMP_MAX_ROUNDS
    except ValueError:
        ok = False
    if not ok:
        return "review stamp is invalid (needs <sha256>;clean|open-risks;1|2)"
    if parts[0] != _stamp_hash(html):
        return "stamp is stale: the page changed after review"
    return ""
BUILDER_MARK = re.compile(r"<!--\s*house-rules make_page\b")
PICTURES = ("img", "svg", "canvas", "video", "picture")
BLOCKS = ("p", "li", "td", "th", "blockquote", "figcaption", "div")
INLINE = ("a", "b", "i", "em", "strong", "span", "code", "small", "br", "u", "mark", "sub", "sup", "abbr")
VOID = ("img", "br", "hr", "input", "meta", "link", "source", "wbr", "col", "area", "base", "embed", "track")
EXTRA = {"proposal": ("exists", "suggested"), "build-plan": ("done-when",), "qa": ("unverified",)}
EXTRA_HELP = {"exists": "what already exists", "suggested": "what is suggested", "done-when": "when the step is done",
              "unverified": "what is still unverified"}


class _Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []        # open tags, innermost last
        self.frames = []       # open block frames: [tag, [text pieces], is_leaf]
        self.basic = {}        # data-basic value -> text of its first element, or None while unknown
        self.open_basic = []   # (stack depth, value) of data-basic elements still open
        self.meta_type = None
        self.pictures = 0
        self.has_ol = False
        self.has_checkbox = False
        self.max_words = MAX_BLOCK_WORDS
        self.long = None       # first words of the first block over the limit

    def _hidden(self):
        tags = self.stack
        if "script" in tags or "style" in tags:
            return True
        # text under <details> counts only inside its <summary>
        last = lambda n: max((i for i, x in enumerate(tags) if x == n), default=-1)
        return last("details") > last("summary")

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if self.frames and tag not in INLINE:
            self.frames[-1][2] = False
        if tag == "meta" and a.get("name") == "house-rules-page":
            self.meta_type = (a.get("content") or "").strip()
        if tag in PICTURES:
            self.pictures += 1
        if tag == "ol":
            self.has_ol = True
        if tag == "input" and (a.get("type") or "").lower() == "checkbox":
            self.has_checkbox = True
        b = a.get("data-basic")
        if b:
            self.basic.setdefault(b, "")
            if tag not in VOID:
                self.open_basic.append((len(self.stack), b))
        if tag in VOID:
            return
        self.stack.append(tag)
        if tag in BLOCKS:
            self.frames.append([tag, [], True, self._hidden()])

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag not in self.stack:
            return
        while self.stack:
            t = self.stack.pop()
            while self.open_basic and self.open_basic[-1][0] >= len(self.stack):
                self.open_basic.pop()
            if t in BLOCKS and self.frames:
                tg, parts, leaf, hidden = self.frames.pop()
                words = " ".join(parts).split()
                if not hidden and (tg != "div" or leaf) and len(words) > self.max_words and self.long is None:
                    self.long = " ".join(words[:8])
            if t == tag:
                break

    def handle_data(self, data):
        if self._hidden():
            return
        if self.frames:
            self.frames[-1][1].append(data)
        for _, b in self.open_basic:
            self.basic[b] = (self.basic[b] + " " + data).strip()


def check(html_text, page_type=None, max_block_words=None):
    if BUILDER_MARK.search(html_text[:4096]):
        return []
    p = _Page()
    p.max_words = MAX_BLOCK_WORDS if max_block_words is None else max_block_words
    p.feed(html_text)
    p.close()
    t = page_type or p.meta_type
    out = []
    if t not in TYPES:
        out.append("This page has no known type (got %r); say which it is with <meta name=\"house-rules-page\" "
                "content=\"...\"> or --type, using one of: %s." % (t, ", ".join(TYPES)))
    summary = p.basic.get("summary")
    if not summary:
        out.append("Basic 1 (summary): the page has no summary of 40 words or fewer; add a short element marked "
                   "data-basic=\"summary\" that says what this page is and what it needs.")
    elif len(summary.split()) > MAX_SUMMARY_WORDS:
        out.append("Basic 1 (summary): the summary is %d words; cut it to %d or fewer."
                   % (len(summary.split()), MAX_SUMMARY_WORDS))
    # shortcut: only checks the marker exists; that it stays on screen is not checked statically, use --visual or look
    if "next" not in p.basic:
        out.append("Basic 2 (next): the page does not say what to do next; add an element marked data-basic=\"next\" "
                   "and keep it on screen.")
    if not p.pictures:
        out.append("Basic 3 (picture): the page has no picture; add an img, svg, canvas, video or picture.")
    if p.long:
        out.append("Basic 4 (short blocks): a block starting \"%s\" is over %d words; split it up or move the detail "
                   "inside a details element." % (p.long, p.max_words))
    if t != "art" and not (p.has_ol or "steps" in p.basic):
        out.append("Basic 5 (steps): the page has no numbered steps; add an ol, or mark the steps data-basic=\"steps\".")
    need_list = t not in TYPES or t in ("proposal", "build-plan", "qa") or "you-act" in p.basic
    if need_list and not (p.has_checkbox or "checklist" in p.basic):
        out.append("Basic 6 (checklist): the page asks aj to act but has no checklist; add checkboxes "
                   "(input type=checkbox) or mark the list data-basic=\"checklist\".")
    for k in EXTRA.get(t, ()):
        if k not in p.basic:
            out.append("Type %s: the page does not show %s; add an element marked data-basic=\"%s\"."
                       % (t, EXTRA_HELP[k], k))
    if t == "review" and "finding" not in p.basic:
        out.append("Type review: the page has no finding; add at least one element marked data-basic=\"finding\".")
    return out


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    visual = "--visual" in args
    if visual:
        args.remove("--visual")
    ptype = None
    if "--type" in args:
        i = args.index("--type")
        ptype = args[i + 1] if i + 1 < len(args) else None
        del args[i:i + 2]
    if len(args) != 1:
        print("usage: page_criteria.py <page.html> [--type T] [--visual]", file=sys.stderr)
        return 2
    try:
        with open(args[0], encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError) as e:
        print("page_criteria: cannot read %s: %s" % (args[0], e), file=sys.stderr)
        return 2
    msgs = check(text, ptype)
    print("\n".join(msgs) if msgs else "page_criteria: all basics met")
    if visual:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from make_page import visual_check  # prints "visual check did not run: ..." when playwright is missing
        visual_check(os.path.abspath(args[0]), {})  # exits 2 itself when it finds problems
    return 1 if msgs else 0


if __name__ == "__main__":
    sys.exit(main())
