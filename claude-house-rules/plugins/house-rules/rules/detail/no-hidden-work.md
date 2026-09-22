# Never hide work in a background window or a silent process


Nothing runs where the user cannot see it. Banned: `-WindowStyle Hidden`, detached
`Start-Process`, background jobs, `nohup`/`setsid`/`disown`, a trailing `&`, and any spawn whose
output only lands in a log I read back. "It's running, I'll check on it" is not a substitute for
them watching it run.

Long work runs in the foreground, in their terminal, printing live progress as it happens.

**Why:** a test the user cannot observe is not a test — it is me asserting a result, which is
exactly the thing they are trying to verify.

