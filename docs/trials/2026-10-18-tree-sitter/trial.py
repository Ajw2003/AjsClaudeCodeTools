"""Trial for the docs context layer's code map (#306, decisions log "Docs map and freshness: aj's
answers"): can tree-sitter-language-pack find every definition and reference in aj's real code?

Run with a Python that has tree-sitter-language-pack 1.22.1 installed:
    python trial.py <corpus-name>=<folder> ...        prints a summary per corpus
    python trial.py --file <path>                     prints every definition and reference in one file
Read-only: it never writes to the folders it reads.
"""
import collections
import os
import sys
import time

import tree_sitter_language_pack as tslp
from tree_sitter import Query, QueryCursor

EXT = {".py": "python", ".js": "javascript", ".mjs": "javascript", ".ts": "typescript",
       ".tsx": "tsx", ".html": "html", ".htm": "html", ".css": "css", ".cs": "csharp"}
SKIP_DIRS = {".git", "node_modules", "Library", "Temp", "obj", "bin", "__pycache__", ".venv"}

# Our own queries: each @def capture is a definition, each @ref a reference to a name.
QUERIES = {
    "python": """
        (function_definition name: (identifier) @def)
        (class_definition name: (identifier) @def)
        (call function: [(identifier) @ref (attribute attribute: (identifier) @ref)])
    """,
    "javascript": """
        (function_declaration name: (identifier) @def)
        (generator_function_declaration name: (identifier) @def)
        (class_declaration name: (identifier) @def)
        (method_definition name: (property_identifier) @def)
        (variable_declarator name: (identifier) @def value: [(arrow_function) (function_expression)])
        (call_expression function: [(identifier) @ref (member_expression property: (property_identifier) @ref)])
        (new_expression constructor: (identifier) @ref)
        (import_statement source: (string) @ref)
    """,
    "csharp": """
        (class_declaration name: (identifier) @def)
        (struct_declaration name: (identifier) @def)
        (interface_declaration name: (identifier) @def)
        (enum_declaration name: (identifier) @def)
        (record_declaration name: (identifier) @def)
        (method_declaration name: (identifier) @def)
        (constructor_declaration name: (identifier) @def)
        (property_declaration name: (identifier) @def)
        (delegate_declaration name: (identifier) @def)
        (invocation_expression function: [(identifier) @ref
            (member_access_expression name: (identifier) @ref)
            (generic_name (identifier) @ref)
            (member_access_expression name: (generic_name (identifier) @ref))])
        (object_creation_expression type: [(identifier) @ref (generic_name (identifier) @ref)])
        (invocation_expression function: (conditional_access_expression
            (member_binding_expression name: (identifier) @ref)))
        (assignment_expression operator: ["+=" "-="] right: (identifier) @ref)
    """,
    "html": """
        (element (start_tag (tag_name) @t (attribute (attribute_name) @a (quoted_attribute_value (attribute_value) @ref))))
        (script_element (start_tag (tag_name) @t (attribute (attribute_name) @a (quoted_attribute_value (attribute_value) @ref))))
        (attribute (attribute_name) @idname (quoted_attribute_value (attribute_value) @def))
    """,
    "css": """
        (rule_set (selectors) @def)
        (import_statement (string_value) @ref)
    """,
}
# TypeScript names classes with type_identifier; everything else matches the JavaScript query.
QUERIES["typescript"] = QUERIES["javascript"].replace("(class_declaration name: (identifier) @def)",
                                                      "(class_declaration name: (type_identifier) @def)")
QUERIES["tsx"] = QUERIES["typescript"]
HTML_REF_ATTRS = {"src", "href"}


_TOOLS = {}


def _tools(lang):
    """One parser and one compiled query per language, reused for every file."""
    if lang not in _TOOLS:
        _TOOLS[lang] = (tslp.get_parser(lang), Query(tslp.get_language(lang), QUERIES[lang]))
    return _TOOLS[lang]


def _text(node, src):
    return src[node.start_byte:node.end_byte].decode("utf-8", "replace")


def symbols(path):
    """(language, defs, refs, seconds): defs and refs are lists of (name, line)."""
    lang = EXT[os.path.splitext(path)[1].lower()]
    with open(path, "rb") as f:
        src = f.read()
    start = time.perf_counter()
    parser, query = _tools(lang)
    tree = parser.parse(src)
    caps = QueryCursor(query).captures(tree.root_node)
    defs, refs = [], []
    if lang == "html":
        for node in caps.get("ref", []):
            attr = node.parent.parent.child(0)
            if _text(attr, src) in HTML_REF_ATTRS:
                refs.append((_text(node, src), node.start_point[0] + 1))
        for node in caps.get("def", []):
            attr = node.parent.parent.child(0)
            if _text(attr, src) == "id":
                defs.append(("#" + _text(node, src), node.start_point[0] + 1))
    else:
        defs = [(_text(n, src).strip(), n.start_point[0] + 1) for n in caps.get("def", [])]
        refs = [(_text(n, src).strip(), n.start_point[0] + 1) for n in caps.get("ref", [])]
    errors = tree.root_node.has_error
    return lang, sorted(set(defs), key=lambda d: d[1]), sorted(set(refs), key=lambda r: r[1]), \
        time.perf_counter() - start, errors


def corpus(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if os.path.splitext(name)[1].lower() in EXT:
                yield os.path.join(dirpath, name)


def summary(label, root):
    per_lang = collections.defaultdict(lambda: {"files": 0, "defs": 0, "refs": 0, "secs": 0.0, "errors": 0})
    def_names = collections.Counter()
    ref_names = []
    for path in corpus(root):
        lang, defs, refs, secs, errors = symbols(path)
        s = per_lang[lang]
        s["files"] += 1; s["defs"] += len(defs); s["refs"] += len(refs); s["secs"] += secs
        s["errors"] += 1 if errors else 0
        def_names.update(n for n, _ in defs)
        ref_names.extend(n for n, _ in refs)
    print("== %s (%s)" % (label, root))
    for lang, s in sorted(per_lang.items()):
        print("  %-10s files %4d  defs %6d  refs %6d  parse+query %.2fs  files with parse errors %d"
              % (lang, s["files"], s["defs"], s["refs"], s["secs"], s["errors"]))
    resolved = [n for n in ref_names if def_names[n] == 1]
    ambiguous = [n for n in ref_names if def_names[n] > 1]
    external = [n for n in ref_names if def_names[n] == 0]
    total = len(ref_names) or 1
    print("  references by name: %d resolve to exactly one definition (%.0f%%), %d to several (%.0f%%), "
          "%d to none in this corpus (%.0f%%)" % (len(resolved), 100 * len(resolved) / total, len(ambiguous),
                                                  100 * len(ambiguous) / total, len(external),
                                                  100 * len(external) / total))
    print("  most-shared definition names: %s" % ", ".join("%s x%d" % kv for kv in def_names.most_common(8)))


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")  # the Windows console's cp1252 can't print emoji in pages
    if argv[:1] == ["--file"]:
        lang, defs, refs, secs, errors = symbols(argv[1])
        print("%s  %s  parse errors: %s" % (argv[1], lang, errors))
        print("DEFS (%d): %s" % (len(defs), ", ".join("%s:%d" % d for d in defs)))
        print("REFS (%d): %s" % (len(refs), ", ".join("%s:%d" % r for r in refs)))
        return 0
    for arg in argv:
        label, _, root = arg.partition("=")
        summary(label, root)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
