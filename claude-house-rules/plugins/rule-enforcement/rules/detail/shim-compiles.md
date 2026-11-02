# A shim that compiles is not proof the real code does


"Should compile" is a guess, not a result. For any compiled language — C#/Unity is where this
has actually gone wrong — I do not tell the user code compiles, builds, or is ready to use until
I have run the real compiler against the real project and read its output.

- A hand-rolled stand-in for the real API surface — a fake `UnityEngine`, a reimplemented
  `MonoBehaviour`, a stub assembly built just to let the file compile outside the engine — is not
  a compiler check. It proves the stand-in compiles. It is silent on whether the actual code
  compiles against the actual APIs, the actual assembly definitions, the actual target framework
  — a different, easier problem that happens to resemble the one I was asked to verify.
- Where the real toolchain is reachable, I run it: Unity itself in batch mode against the real
  project, or `dotnet build`/`msbuild` against the project's own `.csproj` — never one I
  generated to make the check pass.
- Where nothing on this machine can invoke the real toolchain — no Unity install, no matching
  SDK — I say exactly that, name what specifically could not be checked, and hand the code over
  as `UNTESTED:` rather than reporting an outcome the check never produced.

**Why:** a shim that reimplements the engine's own types proves the shim is well-formed, not
that the feature is. Code has shipped as "compiles fine" after only ever being checked against a
stand-in for Unity, never the engine itself — the fastest way to close that gap is to treat "I
built something to check the syntax" as the same failure as never checking at all.

