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
[CmdletBinding()]
param()

function Test-Interpreter {
  param([string[]]$Candidate)
  try {
    $out = & $Candidate[0] $Candidate[1..($Candidate.Length - 1)] -c 'print(9)' 2>$null
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

& $found[0] $found[1..($found.Length - 1)] $installPy @args
exit $LASTEXITCODE
