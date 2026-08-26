<#
.SYNOPSIS
  Strips the house-rules plugin off this machine and reinstalls it from GitHub the way the
  README tells a new device to, then proves the fresh copy works.

.DESCRIPTION
  This exists because "it works on my machine" is not evidence: the working repo on disk is
  not what a new device gets. A new device gets whatever is on GitHub, installed through the
  two documented CLI commands. This script tests exactly that path.

  It runs in PowerShell 5.1, which is the shell this machine actually has. Every step prints
  what it did and PASS or FAIL. Nothing is hidden and nothing is written to a log only an
  agent reads.

  SAFETY: settings.json, installed_plugins.json and known_marketplaces.json are copied to a
  timestamped backup folder BEFORE anything is removed, and the path is printed. Unrelated
  config in those files (theme, enableWorkflows, the claude-plugins-official marketplace) is
  preserved, not clobbered. Everything plugin-side is recoverable from GitHub regardless.

.PARAMETER Force
  Skip the "type STRIP to continue" confirmation. For when you have already read what it is
  about to remove.

.PARAMETER SkipStrip
  Re-run only the verification half against whatever is currently installed. Removes nothing.

.EXAMPLE
  .\tools\clean-install-test.ps1
#>
[CmdletBinding()]
param(
  [switch]$Force,
  [switch]$SkipStrip
)

$ErrorActionPreference = 'Continue'

$Repo          = 'Ajw2003/AjsClaudeCodeTools'
$Marketplace   = 'aj-house-rules'
$PluginId      = "house-rules@$Marketplace"
$ClaudeDir     = Join-Path $env:USERPROFILE '.claude'
$PluginsDir    = Join-Path $ClaudeDir 'plugins'
$SettingsPath  = Join-Path $ClaudeDir 'settings.json'
$InstalledPath = Join-Path $PluginsDir 'installed_plugins.json'
$KnownPath     = Join-Path $PluginsDir 'known_marketplaces.json'
$ClonePath     = Join-Path $PluginsDir ('marketplaces\' + $Marketplace)
$CachePath     = Join-Path $PluginsDir ('cache\' + $Marketplace)
$InstallPath   = $null

$script:StepNo   = 0
$script:Failures = 0

function Step([string]$title) {
  $script:StepNo++
  Write-Host ''
  Write-Host ('{0,2}. {1}' -f $script:StepNo, $title) -ForegroundColor Cyan
}
function Pass([string]$m) { Write-Host "     PASS  $m" -ForegroundColor Green }
function Fail([string]$m) { $script:Failures++; Write-Host "     FAIL  $m" -ForegroundColor Red }
function Info([string]$m) { Write-Host "     $m" -ForegroundColor DarkGray }

Write-Host ''
Write-Host 'house-rules - clean install test' -ForegroundColor White
Write-Host '================================' -ForegroundColor White
Write-Host "Source repo : https://github.com/$Repo"
Write-Host "Plugin      : $PluginId"
Write-Host "Claude dir  : $ClaudeDir"

# ---------------------------------------------------------------- 1. preflight
Step 'Preflight: the tools this test needs'
$sh = $null
foreach ($c in @('C:\Program Files\Git\bin\sh.exe', 'C:\Program Files\Git\usr\bin\sh.exe')) {
  if (Test-Path $c) { $sh = $c; break }
}
$claude = Get-Command claude -ErrorAction SilentlyContinue
$git    = Get-Command git -ErrorAction SilentlyContinue

if ($claude) { Pass "claude  $($claude.Source)" } else { Fail 'claude is not on PATH - cannot install anything' }
if ($git)    { Pass "git     $($git.Source)" }    else { Fail 'git is not on PATH - cannot clone the marketplace' }
if ($sh)     { Pass "sh      $sh" }               else { Fail 'no sh.exe found - install Git for Windows' }
if ($script:Failures -gt 0) {
  Write-Host ''
  Write-Host 'Stopping: the environment cannot run this test.' -ForegroundColor Red
  exit 1
}

# ---------------------------------------------------------------- 2. what is on the remote
Step 'What a new device would actually get'
$remoteLine = & git ls-remote ("https://github.com/$Repo.git") refs/heads/main
$remote = $null
if ($remoteLine) { $remote = ($remoteLine -split '\s+')[0] }
if ($remote) { Pass "remote main is $($remote.Substring(0,7))" } else { Fail 'could not reach the remote' }

# ---------------------------------------------------------------- 3. current state
Step 'What is installed right now, before touching anything'
if (Test-Path $InstalledPath) {
  $inst = Get-Content $InstalledPath -Raw | ConvertFrom-Json
  $entry = $inst.plugins.$PluginId
  if ($entry) {
    $sha = $entry[0].gitCommitSha
    Info "version   $($entry[0].version)"
    Info "commit    $($sha.Substring(0,7))"
    Info "path      $($entry[0].installPath)"
    if ($remote -and ($sha -eq $remote)) { Info 'this is already current' }
    elseif ($remote) { Info "STALE - behind remote $($remote.Substring(0,7))" }
  } else { Info 'not currently installed' }
} else { Info 'no installed_plugins.json yet' }

if ($SkipStrip) {
  Write-Host ''
  Write-Host '-SkipStrip given: skipping the strip and install, verifying what is here now.' -ForegroundColor Yellow
}

if (-not $SkipStrip) {

  # -------------------------------------------------------------- 4. backup
  Step 'Back up the config files that are about to be edited'
  $stamp     = Get-Date -Format 'yyyyMMdd-HHmmss'
  $BackupDir = Join-Path $ClaudeDir ('backups\house-rules-clean-install-' + $stamp)
  New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
  foreach ($f in @($SettingsPath, $InstalledPath, $KnownPath)) {
    if (Test-Path $f) {
      Copy-Item $f -Destination $BackupDir -Force
      Pass "saved $(Split-Path $f -Leaf)"
    } else {
      Info "$(Split-Path $f -Leaf) does not exist, nothing to save"
    }
  }
  Info "backup folder: $BackupDir"

  # -------------------------------------------------------------- 5. confirm
  Step 'Confirm the strip-down'
  Write-Host '     This will remove:' -ForegroundColor Yellow
  Write-Host "       - the installed plugin $PluginId"
  Write-Host "       - the marketplace clone at $ClonePath"
  Write-Host "       - the extracted copy at   $CachePath"
  Write-Host "       - the keys enabledPlugins and extraKnownMarketplaces from settings.json"
  Write-Host "       - the $Marketplace entry from known_marketplaces.json"
  Write-Host '     It will NOT touch your theme, enableWorkflows, autoUpdatesChannel, the' -ForegroundColor Yellow
  Write-Host '     claude-plugins-official marketplace, or any CLAUDE.md file.' -ForegroundColor Yellow
  if (-not $Force) {
    $answer = Read-Host '     Type STRIP to continue, anything else to abort'
    if ($answer -ne 'STRIP') {
      Write-Host '     Aborted. Nothing was changed.' -ForegroundColor Yellow
      exit 2
    }
  } else {
    Info '-Force given, not asking'
  }

  # -------------------------------------------------------------- 6. strip
  Step 'Uninstall through the CLI'
  & claude plugin uninstall $PluginId 2>&1 | ForEach-Object { Info $_ }
  & claude plugin marketplace remove $Marketplace 2>&1 | ForEach-Object { Info $_ }

  Step 'Strip the declarative keys out of settings.json, keeping everything else'
  if (Test-Path $SettingsPath) {
    $s = Get-Content $SettingsPath -Raw | ConvertFrom-Json
    $kept = @($s.PSObject.Properties.Name | Where-Object { @('enabledPlugins','extraKnownMarketplaces') -notcontains $_ })
    foreach ($k in @('enabledPlugins','extraKnownMarketplaces')) {
      if ($s.PSObject.Properties.Name -contains $k) { $s.PSObject.Properties.Remove($k) }
    }
    $s | ConvertTo-Json -Depth 20 | Set-Content $SettingsPath -Encoding utf8
    Pass "removed the two plugin keys; kept: $($kept -join ', ')"
  } else {
    Info 'no settings.json'
  }

  Step 'Remove any leftover files on disk'
  foreach ($d in @($ClonePath, $CachePath)) {
    if (Test-Path $d) {
      Remove-Item $d -Recurse -Force -Confirm:$false
      Pass "removed $d"
    } else {
      Info "already gone: $d"
    }
  }
  if (Test-Path $KnownPath) {
    $k = Get-Content $KnownPath -Raw | ConvertFrom-Json
    if ($k.PSObject.Properties.Name -contains $Marketplace) {
      $k.PSObject.Properties.Remove($Marketplace)
      $k | ConvertTo-Json -Depth 20 | Set-Content $KnownPath -Encoding utf8
      Pass "removed $Marketplace from known_marketplaces.json"
    } else {
      Info "$Marketplace was not in known_marketplaces.json"
    }
  }

  # -------------------------------------------------------------- 7. prove it is gone
  Step 'Prove the machine is actually clean'
  $dirty = @()
  if (Test-Path $ClonePath) { $dirty += 'marketplace clone still present' }
  if (Test-Path $CachePath) { $dirty += 'plugin cache still present' }
  if (Test-Path $SettingsPath) {
    $s2 = Get-Content $SettingsPath -Raw | ConvertFrom-Json
    if ($s2.PSObject.Properties.Name -contains 'enabledPlugins') { $dirty += 'enabledPlugins still in settings.json' }
  }
  if ($dirty.Count -eq 0) {
    Pass 'nothing left behind - this is now a fresh machine'
  } else {
    foreach ($d in $dirty) { Fail $d }
  }

  # -------------------------------------------------------------- 8. install as documented
  Step 'Install using the two commands the README gives a new device'
  Info "claude plugin marketplace add $Repo"
  & claude plugin marketplace add $Repo 2>&1 | ForEach-Object { Info $_ }
  Info "claude plugin install $PluginId -y"
  & claude plugin install $PluginId -y 2>&1 | ForEach-Object { Info $_ }
}

# ---------------------------------------------------------------- 9. is it current
Step 'Did the install land on the commit that is actually on GitHub?'
if (Test-Path $InstalledPath) {
  $inst2 = Get-Content $InstalledPath -Raw | ConvertFrom-Json
  $e2 = $inst2.plugins.$PluginId
  if ($e2) {
    $sha2 = $e2[0].gitCommitSha
    if ($remote -and ($sha2 -eq $remote)) {
      Pass "installed at $($sha2.Substring(0,7)), matching remote"
    } elseif ($remote) {
      Fail "installed at $($sha2.Substring(0,7)) but remote is $($remote.Substring(0,7))"
    }
    $InstallPath = $e2[0].installPath
    Info "installed to $InstallPath"
  } else {
    Fail 'the plugin is not registered as installed'
  }
} else {
  Fail 'no installed_plugins.json after install'
}

# ---------------------------------------------------------------- 10. files present
Step 'Does the installed copy contain every file the hooks need?'
$expected = @(
  'hooks\hooks.json',
  'rules\house-rules.md',
  'rules\environment.md',
  'scripts\guard.sh',
  'scripts\inject.sh',
  'scripts\scope.sh',
  'scripts\artifact.sh',
  'scripts\verify.sh'
)
if ($InstallPath -and (Test-Path $InstallPath)) {
  foreach ($f in $expected) {
    if (Test-Path (Join-Path $InstallPath $f)) { Pass $f } else { Fail "$f is MISSING from the installed copy" }
  }
} else {
  Fail 'cannot find the installed copy on disk'
}

# ---------------------------------------------------------------- 11. hooks wired
Step 'Are all four hook events wired in the installed hooks.json?'
if ($InstallPath -and (Test-Path (Join-Path $InstallPath 'hooks\hooks.json'))) {
  $h = Get-Content (Join-Path $InstallPath 'hooks\hooks.json') -Raw | ConvertFrom-Json
  foreach ($evt in @('SessionStart','UserPromptSubmit','PreToolUse','PostToolUse')) {
    if ($h.hooks.PSObject.Properties.Name -contains $evt) { Pass $evt } else { Fail "$evt is not wired" }
  }
} else {
  Fail 'no hooks.json in the installed copy'
}

# ---------------------------------------------------------------- 12. full suite, fresh clone
Step 'Run the 34-check suite against the freshly cloned copy'
$freshVerify = Join-Path $ClonePath 'claude-house-rules\plugins\house-rules\scripts\verify.sh'
if (Test-Path $freshVerify) {
  Info "running: $freshVerify"
  Write-Host ''
  & $sh $freshVerify
  $code = $LASTEXITCODE
  Write-Host ''
  if ($code -eq 0) { Pass 'all 34 checks passed against the fresh clone' }
  else { Fail "the suite exited $code - read the FAIL lines above" }
} else {
  Fail "verify.sh not found in the fresh clone at $freshVerify"
}

# ---------------------------------------------------------------- 13. hooks run
Step 'Run each hook directly out of the installed copy'
if ($InstallPath -and (Test-Path (Join-Path $InstallPath 'scripts\inject.sh'))) {
  $out = (& $sh (Join-Path $InstallPath 'scripts\inject.sh')) | Out-String
  if ($out -match 'Never commit without asking') { Pass 'inject.sh emits the rules' } else { Fail 'inject.sh did not emit the rules' }
  if ($out -match 'This machine') { Pass 'inject.sh emits the machine profile' } else { Fail 'inject.sh did not emit the machine profile' }
} else {
  Fail 'inject.sh missing from the installed copy'
}
if ($InstallPath -and (Test-Path (Join-Path $InstallPath 'scripts\scope.sh'))) {
  $out2 = (& $sh (Join-Path $InstallPath 'scripts\scope.sh')) | Out-String
  if ($out2 -match 'UserPromptSubmit') { Pass 'scope.sh emits the per-prompt reminder' } else { Fail 'scope.sh produced nothing usable' }
} else {
  Fail 'scope.sh missing from the installed copy'
}

# ---------------------------------------------------------------- verdict
Write-Host ''
Write-Host '--------------------------------' -ForegroundColor White
if ($script:Failures -eq 0) {
  Write-Host "RESULT: PASS - all $script:StepNo steps passed. The published plugin installs and runs." -ForegroundColor Green
} else {
  Write-Host "RESULT: FAIL - $script:Failures check(s) failed across $script:StepNo steps." -ForegroundColor Red
}

Write-Host ''
Write-Host 'ONE STEP IS LEFT, AND ONLY YOU CAN DO IT:' -ForegroundColor Yellow
Write-Host ''
Write-Host '  Everything above tests files on disk. It cannot test that Claude Code loads them,'
Write-Host '  because hooks are read at startup. So:'
Write-Host ''
Write-Host '    1. Fully quit Claude Code - close every window.'
Write-Host '    2. Start it again, in any project.'
Write-Host '    3. Ask it:  what are my house rules, and what machine am I on?'
Write-Host ''
Write-Host '       If SessionStart fired it answers both without opening a file: it names the'
Write-Host '       rules and says Ryzen 5 9600X / Windows 11 / PowerShell 5.1. If it starts'
Write-Host '       searching for files instead, the injection did not happen.'
Write-Host ''
Write-Host '    4. Ask it to run:  git status'
Write-Host '       That must run with NO permission prompt.'
Write-Host ''
Write-Host '    5. The guard test needs an uncommitted change to be meaningful.' -ForegroundColor Yellow
Write-Host '       On a clean worktree, git add -A stages nothing whether the guard'
Write-Host '       intercepted it or not, so the result looks the same either way and'
Write-Host '       proves nothing. Give it something real to stage first:'
Write-Host ''
Write-Host '         echo scratch > guard-test.txt'
Write-Host ''
Write-Host '       Then ask Claude to run:  git add -A'
Write-Host '       That MUST raise a prompt naming "Never commit without asking".'
Write-Host '       Deny it, then clean up:'
Write-Host ''
Write-Host '         del guard-test.txt'
Write-Host ''
if ($script:Failures -ne 0) { exit 1 }
exit 0
