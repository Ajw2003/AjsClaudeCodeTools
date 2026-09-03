<#
.SYNOPSIS
  Thin bootstrap: find a working Python, then hand off to tools/install.py.

.DESCRIPTION
  All real install logic lives in Python (tools/install.py). This file's only job is finding
  an interpreter that actually runs code, the same way run.sh does for the hooks - PROBED, not
  just found on PATH, because `python3` can be the Windows Store App Execution Alias stub: on
  PATH, found by Get-Command, but it prints an install nag and exits 0 instead of running
  anything.

  If nothing probes successfully, this prints the one install command for Windows
  (winget install Python.Python.3.12) and stops - there is no working install path without
  Python, and this repo does not ask you to run a manual prerequisite step first without
  telling you exactly what to run.
#>
param(
  # Everything after the script name is forwarded verbatim to install.py (--no-verbose,
  # --no-model). Without ValueFromRemainingArguments an empty param() block makes PowerShell
  # reject any argument outright, so no flag could ever reach the installer.
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Passthru = @()
)

function Test-Interpreter {
  param([string[]]$Candidate)
  try {
    # Select-Object -Skip 1, not $Candidate[1..($n-1)]: for a ONE-element candidate that
    # range is 1..0, which PowerShell reverses, handing back the element itself instead of an
    # empty tail. That turned the probe into `python python -c ...`, so the bare `python` and
    # `python3` candidates could never succeed and only `py -3` ever resolved.
    $tail = @($Candidate | Select-Object -Skip 1)
    $out = & $Candidate[0] @tail -c 'print(9)' 2>$null
    return ($out -eq '9')
  } catch {
    return $false
  }
}

$candidates = @(
  ,@('python3')
  ,@('python')
  ,@('py', '-3')
)

if ($env:HOUSE_RULES_PYTHON) {
  $candidates = ,@($env:HOUSE_RULES_PYTHON -split '\s+') + $candidates
}

$found = $null
foreach ($c in $candidates) {
  if (Test-Interpreter $c) {
    $found = $c
    break
  }
}

if (-not $found) {
  Write-Host ''
  Write-Host 'No working Python interpreter found on PATH.' -ForegroundColor Red
  Write-Host 'Run this, then re-run tools\bootstrap.ps1:' -ForegroundColor Yellow
  Write-Host ''
  Write-Host '  winget install Python.Python.3.12'
  Write-Host ''
  exit 1
}

Write-Host "Using interpreter: $($found -join ' ')" -ForegroundColor DarkGray

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$installPy = Join-Path $scriptDir 'install.py'

$foundTail = @($found | Select-Object -Skip 1)
& $found[0] @foundTail $installPy @Passthru
exit $LASTEXITCODE
