# A reported update is not a completed one


"Already up to date," "already installed," "success," a version string, a status code — these
report what the tool compared, not what I need to know. A check can be entirely honest about its
own comparison and still wrong about whether anything actually changed, if the thing it compared
didn't move for a reason that has nothing to do with whether new content exists.

- Before I tell the user an install, update, sync, or deploy took effect, I verify the actual
  target changed — diff the content, compare a hash, read the file — rather than trusting the
  tool's own status message.
- A version-gated updater is the sharpest case: it reports against one field (a version number),
  and if that field didn't move, it reports no-op regardless of what changed underneath it.
  Trusting the message instead of the target is how a comparison that is locally correct becomes
  an answer that is globally wrong.

**Why:** a plugin's own updater reported "already at the latest version" after the source it
installs from had genuinely changed, because the one field it compared — a version string — had
not been bumped alongside the content. The message was true about what it checked and false about
what the reader needed to know. Nothing was broken in the tool; the gap was between what it
verified and what "updated" was taken to mean.

