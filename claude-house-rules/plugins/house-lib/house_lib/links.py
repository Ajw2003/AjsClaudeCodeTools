"""house_lib.links - the hook-link registry shared by every plugin (#439).

Moved verbatim from house_rules/core.py. STDLIB ONLY. Source: claude-house-rules/plugins/house-lib/house_lib/."""


# ---------------------------------------------------------------------------------------
# The core links (#357). The core never imports hook.py or a part module, so where one of its
# handlers needs code that belongs to another part, that code registers itself here and the
# handler loops over the list. Three lists, one register function each:
#   SESSION_START_HOOKS  (consumer, fn): inject asks fn(body) -> body, profile asks fn() -> text
#   PROMPT_HOOKS         fn(payload, field) -> (clause, note)   scope runs each on every message;
#                        field is the prompt JSON field or None; clause is added straight after
#                        the reminder, note after it (a later hook's note goes in front)
#   POST_TOOL_HOOKS      (consumer, fn): artifact asks fn(file_path) -> note text, promptran
#                        asks fn(data) -> report text; each handler runs only its own consumer's
# Step 2b adds three more, read by the safe git part (#358):
#   GUARD_ISSUE_HOOKS    fn(subject, payload) -> None or (kind, reason, context); guard asks each,
#                        in order, after its own attribution check, and takes the first answer
#   GITHUB_WRITE_HOOKS   fn(payload, raw) -> True when it handled the call (and emitted);
#                        guardgithub asks each before its own credit check
#   DOCS_STATUS_HOOKS    fn(subject, elsewhere, root) -> (status, detail); guard asks the first
# ---------------------------------------------------------------------------------------

SESSION_START_HOOKS = []
PROMPT_HOOKS = []
POST_TOOL_HOOKS = []
GUARD_ISSUE_HOOKS = []
GITHUB_WRITE_HOOKS = []
DOCS_STATUS_HOOKS = []


def _register(hooks, entry):
    # Replace an earlier registration of the same name instead of adding a second one:
    # verify.py loads hook.py several times in one process, and a plain append would make
    # every later load run each hook twice. The module loaded last is the one in use.
    name = (entry[0], entry[-1].__name__) if isinstance(entry, tuple) else entry.__name__
    for i, old in enumerate(hooks):
        if ((old[0], old[-1].__name__) if isinstance(old, tuple) else old.__name__) == name:
            hooks[i] = entry
            return
    hooks.append(entry)


def register_session_start(consumer, fn):
    _register(SESSION_START_HOOKS, (consumer, fn))
    return fn


def register_prompt(fn):
    _register(PROMPT_HOOKS, fn)
    return fn


def register_post_tool(consumer, fn):
    _register(POST_TOOL_HOOKS, (consumer, fn))
    return fn


def _session_start_hooks(consumer):
    return [fn for name, fn in SESSION_START_HOOKS if name == consumer]


def _post_tool_hooks(consumer):
    return [fn for name, fn in POST_TOOL_HOOKS if name == consumer]


def register_guard_issue(fn):
    _register(GUARD_ISSUE_HOOKS, fn)
    return fn


def register_github_write(fn):
    _register(GITHUB_WRITE_HOOKS, fn)
    return fn


def register_docs_status(fn):
    _register(DOCS_STATUS_HOOKS, fn)
    return fn
