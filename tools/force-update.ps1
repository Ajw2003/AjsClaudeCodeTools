#Requires -Version 5.1
<#
.SYNOPSIS
    Force the installed house-rules plugin to match the marketplace source.

.DESCRIPTION
    `claude plugin update` is version-gated: if plugin.json still declares the
    same version, it reports "already at the latest version" and copies nothing.
    That is the normal case while iterating on a branch, so the only reliable
    way to re-sync is uninstall + reinstall.

    This refreshes the marketplace clone, reinstalls the plugin, and verifies
    the installed cache matches the source tree file-for-file.

.PARAMETER Plugin
    Plugin id as `name@marketplace`. Defaults to house-rules@aj-house-rules.

.PARAMETER SkipMarketplaceUpdate
    Skip the marketplace refresh and reinstall from the clone as it stands.
    Use when you have local commits you have not pushed yet.

.EXAMPLE
    .\tools\force-update.ps1

.EXAMPLE
    .\tools\force-update.ps1 -SkipMarketplaceUpdate
#>
[CmdletBinding()]
param(
    [string] $Plugin = 'house-rules@aj-house-rules',
    [switch] $SkipMarketplaceUpdate
)

$ErrorActionPreference = 'Stop'

if ($Plugin -notmatch '^(?<name>[^@]+)@(?<market>[^@]+)$') {
    throw "Plugin must be in 'name@marketplace' form. Got: $Plugin"
}
$name   = $Matches['name']
$market = $Matches['market']

if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    throw "'claude' is not on PATH."
}

function Invoke-Claude {
    param([string[]] $ClaudeArgs, [string] $Activity)

    Write-Host "==> $Activity" -ForegroundColor Cyan
    # stderr is left alone on purpose: redirecting a native command's stderr in
    # PowerShell 5.1 wraps each line in an ErrorRecord and flips $? to false.
    & claude @ClaudeArgs
    if ($LASTEXITCODE -ne 0) {
        throw "$Activity failed (exit $LASTEXITCODE)."
    }
}

function Get-TreeHash {
    param([string] $Root)

    if (-not (Test-Path -LiteralPath $Root)) { return $null }
    Get-ChildItem -LiteralPath $Root -Recurse -File |
        # .in_use holds per-session lock files, not plugin content.
        Where-Object { $_.FullName -notmatch '\\\.in_use\\' } |
        ForEach-Object {
            [pscustomobject]@{
                Path = $_.FullName.Substring($Root.Length).TrimStart('\')
                Hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm MD5).Hash
            }
        } | Sort-Object Path
}

$pluginsRoot = Join-Path $env:USERPROFILE '.claude\plugins'
$marketRoot  = Join-Path $pluginsRoot "marketplaces\$market"

if (-not $SkipMarketplaceUpdate) {
    Invoke-Claude -ClaudeArgs @('plugin','marketplace','update',$market) `
                  -Activity "Refreshing marketplace '$market'"
} else {
    Write-Host "==> Skipping marketplace refresh (-SkipMarketplaceUpdate)" -ForegroundColor Yellow
}

# Report the commit being installed, and warn about unpushed work, so a reinstall
# that quietly ships local-only commits is visible rather than surprising.
if (Test-Path -LiteralPath (Join-Path $marketRoot '.git')) {
    $head = (& git -C $marketRoot rev-parse --short HEAD).Trim()
    $subj = (& git -C $marketRoot log -1 --format=%s).Trim()
    Write-Host "    source commit: $head  $subj"

    $ahead = (& git -C $marketRoot rev-list --count '@{upstream}..HEAD' 2>$null)
    if ($LASTEXITCODE -eq 0 -and [int]$ahead -gt 0) {
        Write-Warning "$ahead local commit(s) are not pushed to the upstream branch."
    }
    $LASTEXITCODE = 0

    $dirty = & git -C $marketRoot status --porcelain
    if ($dirty) {
        Write-Warning "Marketplace clone has uncommitted changes; installing them as-is."
    }
}

Invoke-Claude -ClaudeArgs @('plugin','uninstall',$Plugin) `
              -Activity "Uninstalling $Plugin"
Invoke-Claude -ClaudeArgs @('plugin','install',$Plugin,'-y') `
              -Activity "Reinstalling $Plugin"

# Verify: locate the freshly installed cache and the source tree, then compare.
$cacheRoot = Join-Path $pluginsRoot "cache\$market\$name"
$installed = Get-ChildItem -LiteralPath $cacheRoot -Directory -ErrorAction SilentlyContinue |
             Sort-Object LastWriteTime -Descending | Select-Object -First 1

$source = Get-ChildItem -LiteralPath $marketRoot -Recurse -Directory -Filter '.claude-plugin' -ErrorAction SilentlyContinue |
          Where-Object { Test-Path (Join-Path $_.FullName 'plugin.json') } |
          Where-Object {
              (Get-Content (Join-Path $_.FullName 'plugin.json') -Raw | ConvertFrom-Json).name -eq $name
          } | Select-Object -First 1

if (-not $installed -or -not $source) {
    Write-Warning "Reinstalled, but could not locate both trees to verify."
    Write-Host "Restart Claude Code to load the new version." -ForegroundColor Green
    return
}

$diff = Compare-Object -ReferenceObject (Get-TreeHash $source.Parent.FullName) `
                       -DifferenceObject (Get-TreeHash $installed.FullName) `
                       -Property Path, Hash

if ($diff) {
    Write-Host ""
    Write-Warning "Installed cache does NOT match source:"
    $diff | Sort-Object Path | Format-Table @{
        L='Where'; E={ if ($_.SideIndicator -eq '<=') { 'source only' } else { 'cache only' } }
    }, Path, Hash -AutoSize
    exit 1
}

Write-Host ""
Write-Host "OK: $name $($installed.Name) matches source, file-for-file." -ForegroundColor Green
Write-Host "Restart Claude Code to load it - a running session keeps the old hooks and rules." -ForegroundColor Green
