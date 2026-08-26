<#
.SYNOPSIS
  Installs the house-rules plugin on this device and applies the settings it expects.

.DESCRIPTION
  The two `claude plugin` commands in the README install the plugin, but a plugin can only
  ship hooks and rules — it cannot set anything the Claude Code UI reads. `verbose` is one of
  those: the verbose transcript view is rendered by the harness from ~/.claude/settings.json,
  so no rule text can turn it on. This script does both halves, so a new device is configured
  in one command instead of two commands plus a hand edit.

  Idempotent. Re-running it on a machine that already has the plugin re-adds the marketplace
  (a no-op), re-installs at the current remote commit, and leaves settings.json alone if
  verbose is already true. Every other key in settings.json is preserved.

.PARAMETER NoVerbose
  Install the plugin but do not touch the verbose setting.

.EXAMPLE
  .\tools\install.ps1
#>
[CmdletBinding()]
param(
  [switch]$NoVerbose
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
Write-Host ''
Write-Host '3. Settings the plugin cannot set itself' -ForegroundColor Cyan
if ($NoVerbose) {
  Info '-NoVerbose given, leaving the transcript view setting alone'
} else {
  if (Test-Path $SettingsPath) {
    $s = Get-Content $SettingsPath -Raw | ConvertFrom-Json
  } else {
    New-Item -ItemType Directory -Path $ClaudeDir -Force | Out-Null
    $s = New-Object PSObject
  }

  if ($s.PSObject.Properties.Name -contains 'verbose' -and $s.verbose -eq $true) {
    Pass 'verbose is already true - nothing to change'
  } else {
    $kept = @($s.PSObject.Properties.Name | Where-Object { $_ -ne 'verbose' })
    if ($s.PSObject.Properties.Name -contains 'verbose') { $s.PSObject.Properties.Remove('verbose') }
    $s | Add-Member -MemberType NoteProperty -Name 'verbose' -Value $true
    $s | ConvertTo-Json -Depth 20 | Set-Content $SettingsPath -Encoding utf8
    Pass 'set verbose = true (default to the verbose transcript view)'
    if ($kept.Count -gt 0) { Info "kept: $($kept -join ', ')" }
  }

  $check = Get-Content $SettingsPath -Raw | ConvertFrom-Json
  if ($check.verbose -eq $true) { Pass 'settings.json still parses and reads back verbose = true' }
  else { Fail 'settings.json does not read back verbose = true' }
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
Write-Host 'Fully quit Claude Code and start it again. Hooks are read at startup, and the' -ForegroundColor Yellow
Write-Host 'transcript view is read at startup, so neither takes effect in a running session.' -ForegroundColor Yellow
Write-Host ''
if ($script:Failures -ne 0) { exit 1 }
exit 0
