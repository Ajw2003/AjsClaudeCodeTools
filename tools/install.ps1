<#
.SYNOPSIS
  Installs the house-rules plugin on this device and applies the settings it expects.

.DESCRIPTION
  The two `claude plugin` commands in the README install the plugin, but a plugin can only
  ship hooks, rules and agents — it cannot set anything the Claude Code harness reads from
  ~/.claude/settings.json. Two of those matter here:

    verbose  the verbose transcript view, rendered by the harness, so no rule text can turn
             it on.
    model    'opusplan' — Opus while planning, automatically switching to Sonnet to execute.
             Hooks cannot set a model at all (a SessionStart hook may be told which model is
             running; none can change it), so this is the only place it can be set.

  This script does both halves, so a new device is configured in one command instead of two
  commands plus a hand edit.

  Idempotent. Re-running it on a machine that already has the plugin re-adds the marketplace
  (a no-op), re-installs at the current remote commit, and leaves a setting alone when it
  already holds the wanted value. Every other key in settings.json is preserved.

.PARAMETER NoVerbose
  Install the plugin but do not touch the verbose setting.

.PARAMETER NoModel
  Install the plugin but do not touch the model setting, for a device that deliberately runs
  on something other than opusplan.

.EXAMPLE
  .\tools\install.ps1
#>
[CmdletBinding()]
param(
  [switch]$NoVerbose,
  [switch]$NoModel
)

$ErrorActionPreference = 'Continue'

$Repo         = 'Ajw2003/AjsClaudeCodeTools'
$Marketplace  = 'aj-house-rules'
$PluginId     = "house-rules@$Marketplace"
$ClaudeDir    = Join-Path $env:USERPROFILE '.claude'
$SettingsPath = Join-Path $ClaudeDir 'settings.json'

$script:Failures = 0
function Pass([string]$m) { Write-Host "  PASS  $m" -ForegroundColor Green }
function Fail([string]$m) { $script:Failures++; Write-Host "  FAIL  $m" -ForegroundColor Red }
function Info([string]$m) { Write-Host "        $m" -ForegroundColor DarkGray }

Write-Host ''
Write-Host 'house-rules - install' -ForegroundColor White
Write-Host '=====================' -ForegroundColor White

# ------------------------------------------------------------------ 1. preflight
Write-Host ''
Write-Host '1. Preflight' -ForegroundColor Cyan
$claude = Get-Command claude -ErrorAction SilentlyContinue
if ($claude) { Pass "claude  $($claude.Source)" } else { Fail 'claude is not on PATH - nothing can be installed' }
if ($script:Failures -gt 0) { exit 1 }

# ------------------------------------------------------------------ 2. plugin
Write-Host ''
Write-Host '2. Install the plugin' -ForegroundColor Cyan
Info "claude plugin marketplace add $Repo"
& claude plugin marketplace add $Repo 2>&1 | ForEach-Object { Info $_ }
Info "claude plugin install $PluginId -y"
& claude plugin install $PluginId -y 2>&1 | ForEach-Object { Info $_ }

$InstalledPath = Join-Path $ClaudeDir 'plugins\installed_plugins.json'
if (Test-Path $InstalledPath) {
  $inst = Get-Content $InstalledPath -Raw | ConvertFrom-Json
  if ($inst.plugins.$PluginId) { Pass "$PluginId is registered as installed" }
  else { Fail "$PluginId did not register - read the lines above" }
} else {
  Fail 'no installed_plugins.json after install'
}

# ------------------------------------------------------------------ 3. settings
# One table, one loop. Each entry is a key the plugin cannot ship and this script therefore
# writes, preserving every other key in the file. Adding a third setting is a row here, not
# another copy of the read/compare/write/read-back block.
Write-Host ''
Write-Host '3. Settings the plugin cannot set itself' -ForegroundColor Cyan

$Wanted = @(
  [pscustomobject]@{ Name = 'verbose'; Value = $true;       Skip = $NoVerbose; SkipNote = '-NoVerbose given, leaving the transcript view setting alone'; Why = 'default to the verbose transcript view' }
  [pscustomobject]@{ Name = 'model';   Value = 'opusplan';  Skip = $NoModel;   SkipNote = '-NoModel given, leaving the model setting alone';           Why = 'Opus while planning, Sonnet to execute' }
)

$ToApply = @($Wanted | Where-Object { -not $_.Skip })
foreach ($skipped in @($Wanted | Where-Object { $_.Skip })) { Info $skipped.SkipNote }

if ($ToApply.Count -gt 0) {
  if (Test-Path $SettingsPath) {
    $s = Get-Content $SettingsPath -Raw | ConvertFrom-Json
  } else {
    New-Item -ItemType Directory -Path $ClaudeDir -Force | Out-Null
    $s = New-Object PSObject
  }

  $changed = $false
  foreach ($w in $ToApply) {
    $has = $s.PSObject.Properties.Name -contains $w.Name
    if ($has -and $s.($w.Name) -eq $w.Value) {
      Pass "$($w.Name) is already $($w.Value) - nothing to change"
      continue
    }
    if ($has) { $s.PSObject.Properties.Remove($w.Name) }
    $s | Add-Member -MemberType NoteProperty -Name $w.Name -Value $w.Value
    $changed = $true
    Pass "set $($w.Name) = $($w.Value) ($($w.Why))"
  }

  if ($changed) {
    $kept = @($s.PSObject.Properties.Name | Where-Object { $ToApply.Name -notcontains $_ })
    $s | ConvertTo-Json -Depth 20 | Set-Content $SettingsPath -Encoding utf8
    if ($kept.Count -gt 0) { Info "kept: $($kept -join ', ')" }
  }

  # Read it back off disk rather than trusting the object we just wrote.
  $check = Get-Content $SettingsPath -Raw | ConvertFrom-Json
  foreach ($w in $ToApply) {
    if ($check.($w.Name) -eq $w.Value) { Pass "settings.json still parses and reads back $($w.Name) = $($w.Value)" }
    else { Fail "settings.json does not read back $($w.Name) = $($w.Value)" }
  }
}

# ------------------------------------------------------------------ verdict
Write-Host ''
Write-Host '---------------------' -ForegroundColor White
if ($script:Failures -eq 0) {
  Write-Host 'RESULT: PASS - plugin installed and settings applied.' -ForegroundColor Green
} else {
  Write-Host "RESULT: FAIL - $script:Failures check(s) failed." -ForegroundColor Red
}
Write-Host ''
Write-Host 'Fully quit Claude Code and start it again. Hooks, agents, the transcript view and' -ForegroundColor Yellow
Write-Host 'the model setting are all read at startup, so none takes effect in a running session.' -ForegroundColor Yellow
Write-Host ''
if ($script:Failures -ne 0) { exit 1 }
exit 0
