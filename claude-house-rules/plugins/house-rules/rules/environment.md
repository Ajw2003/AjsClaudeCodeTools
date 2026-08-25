# This machine

Discovered, not assumed. Recorded 2026-08-25 by running the commands in the last section.
If a fact here is wrong or missing, re-run those commands and correct this file — do not guess,
and do not build for an environment that is not written down here.

## Operating system and shells

| | |
|---|---|
| OS | Microsoft Windows 11 Pro, version 10.0.26100 (build 26100), 64-bit |
| PowerShell | Windows PowerShell **5.1**.26100.7920, Desktop edition |
| PowerShell 7 (`pwsh`) | **not installed** |
| POSIX shell | Git Bash, from Git for Windows 2.45.1 |
| WSL | `wsl.exe` present, but not used for this work |

**PowerShell 5.1 means:** no `&&` or `||` chaining, no ternary `? :`, no null-coalescing `??`,
no `?.`, no `ConvertFrom-Json -AsHashtable`. Use `;` with `if ($?)` to chain.

## The `sh` trap — read this before writing instructions

`sh` and `bash` are **NOT on PATH**. Git for Windows only puts `C:\Program Files\Git\cmd` on
PATH, which contains `git.exe` and nothing else useful here. The shells exist but must be
called by full path:

    C:\Program Files\Git\bin\sh.exe
    C:\Program Files\Git\usr\bin\sh.exe
    C:\Program Files\Git\git-bash.exe

So a bare `sh some-script.sh` **fails in PowerShell**, which is the shell aj actually uses.
From PowerShell, invoke it as:

    & "C:\Program Files\Git\bin\sh.exe" path/to/script.sh

The short `sh path/to/script.sh` form only works inside a Git Bash window.

Claude Code's own hooks still work, because Claude Code locates Git Bash itself rather than
relying on PATH. The PATH gap affects instructions given to aj, not the hooks.

## Hardware

| | |
|---|---|
| CPU | AMD Ryzen 5 9600X, 6 physical / 12 logical cores |
| RAM | 31.1 GB |
| GPU | NVIDIA GeForce RTX 5070 (plus AMD Radeon integrated graphics) |
| Virtual displays | Parsec Virtual Display Adapter, Virtual Desktop Monitor — the machine is used remotely |
| Storage | single C: volume, 1862 GB |

## Toolchain on PATH

| Tool | Path |
|---|---|
| `git` | `C:\Program Files\Git\cmd\git.exe` (2.45.1) |
| `claude` | `C:\Users\aj\.local\bin\claude.exe` (2.1.238, native binary — not an npm install) |
| `node` | `C:\Program Files\nodejs\node.exe` |
| `python` | `C:\Python313\python.exe` |
| `npm` | `C:\Program Files\nodejs\npm.ps1` |

`node` and `python` exist, but the house-rules hooks deliberately do not use them — see the
README for why.

## Git configuration that affects shipped files

`core.autocrlf = true`, with no `.gitattributes` in the repo. Blobs are stored LF and the
working tree is currently LF, so nothing is broken today. It is worth re-checking after any
fresh clone, because a `.sh` file checked out with CRLF would break under some shells.

## How to regenerate this file

Run these in PowerShell and update the tables above from the output:

    Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber, OSArchitecture
    Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors
    Get-CimInstance Win32_ComputerSystem | Select-Object TotalPhysicalMemory
    Get-CimInstance Win32_VideoController | Select-Object Name
    $PSVersionTable
    foreach ($c in 'git','sh','bash','pwsh','node','python','npm','claude','wsl') { Get-Command $c -ErrorAction SilentlyContinue }
    git config --get core.autocrlf
