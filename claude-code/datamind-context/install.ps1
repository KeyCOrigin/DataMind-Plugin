# Install DataMind Context as a Claude Code plugin (Windows / PowerShell version).
#
# Mirrors install.sh on Unix:
#   1. Validate the plugin manifest.
#   2. Create a venv under vendor\datamind\.venv and install requirements.txt.
#   3. Replace .claude-plugin\mcp.json with .claude-plugin\mcp.windows.json
#      so Claude Code spawns the .ps1 launcher instead of the .sh launcher.
#   4. Run `claude plugin marketplace add` and `claude plugin install`.
#
# Usage (PowerShell):
#   .\install.ps1
#   .\install.ps1 -Force
#   .\install.ps1 -SkipDeps
#   .\install.ps1 -RepoRoot C:\path\to\DataMind
#   .\install.ps1 -PythonExe C:\Python311\python.exe
#
# Requirements:
#   - Python 3
#   - `claude` CLI in PATH (https://docs.claude.com/claude-code)

[CmdletBinding()]
param(
    [string]$RepoRoot,
    [switch]$Force,
    [switch]$SkipDeps,
    [string]$PythonExe = 'python'
)

$ErrorActionPreference = 'Stop'

$PluginName = 'datamind-context'
$MarketplaceName = 'datamind'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# --- 1. Sanity checks ---
if (-not (Test-Path (Join-Path $ScriptDir '.claude-plugin\plugin.json'))) {
    Write-Error "Cannot find Claude Code plugin manifest in $ScriptDir`nRun this script from inside the unpacked claude-code\datamind-context\ directory."
    exit 1
}

if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    Write-Error "ERROR: 'claude' CLI not found in PATH. Install Claude Code first: https://docs.claude.com/claude-code"
    exit 1
}

function Resolve-BundledRepo($base) {
    foreach ($name in 'datamind', 'DataMind') {
        $candidate = Join-Path $base "vendor\$name"
        if ((Test-Path (Join-Path $candidate 'config.py')) -and (Test-Path (Join-Path $candidate 'core'))) {
            return (Resolve-Path $candidate).Path
        }
    }
    return $null
}

if (-not $RepoRoot) {
    $RepoRoot = Resolve-BundledRepo $ScriptDir
}

if (-not $RepoRoot) {
    Write-Error "Missing DataMind runtime. Use -RepoRoot C:\path\to\DataMind, or run from a release that includes vendor\datamind."
    exit 1
}

$RepoRoot = (Resolve-Path $RepoRoot).Path
if (-not (Test-Path (Join-Path $RepoRoot 'config.py')) -or -not (Test-Path (Join-Path $RepoRoot 'core'))) {
    Write-Error "Not a DataMind repository root: $RepoRoot"
    exit 1
}

# --- 2. Optional: create venv + install dependencies ---
if (-not $SkipDeps) {
    $venvPy = Join-Path $RepoRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path $venvPy)) {
        Write-Host "Creating venv at $RepoRoot\.venv ..."
        & $PythonExe -m venv (Join-Path $RepoRoot '.venv')
    }
    & $venvPy -m pip install --upgrade pip
    & $venvPy -m pip install --prefer-binary -r (Join-Path $RepoRoot 'requirements.txt')
}

if (-not (Test-Path (Join-Path $RepoRoot '.env')) -and (Test-Path (Join-Path $RepoRoot '.env.example'))) {
    Copy-Item -Force (Join-Path $RepoRoot '.env.example') (Join-Path $RepoRoot '.env')
    Write-Host "Created $($RepoRoot)\.env from .env.example. Edit it with your LLM and embedding credentials."
}

# --- 3. Activate the Windows MCP config ---
$WinMcp = Join-Path $ScriptDir '.claude-plugin\mcp.windows.json'
$Mcp = Join-Path $ScriptDir '.claude-plugin\mcp.json'
if (Test-Path $WinMcp) {
    Copy-Item -Force $WinMcp $Mcp
    Write-Host "Activated Windows MCP config: $Mcp"
}

# --- 4. Register and install with Claude Code ---
if ($Force) {
    & claude plugin uninstall "$PluginName@$MarketplaceName" 2>$null
    & claude plugin marketplace remove $MarketplaceName 2>$null
}

$mpList = & claude plugin marketplace list 2>$null
if ($mpList -notmatch [Regex]::Escape($MarketplaceName)) {
    & claude plugin marketplace add $ScriptDir
} else {
    Write-Host "Marketplace '$MarketplaceName' already registered. Use -Force to replace."
}

$pluginList = & claude plugin list 2>$null
if ($pluginList -notmatch ([Regex]::Escape("$PluginName@$MarketplaceName"))) {
    & claude plugin install "$PluginName@$MarketplaceName"
} else {
    Write-Host "Plugin '$PluginName@$MarketplaceName' already installed. Use -Force to reinstall."
}

# --- 5. Friendly summary ---
Write-Host ""
Write-Host "Installed $PluginName for Claude Code."
Write-Host "Plugin source:  $ScriptDir"
Write-Host "DataMind repo:  $RepoRoot"
if (Test-Path (Join-Path $RepoRoot '.env')) {
    Write-Host "Env file:       $RepoRoot\.env  (edit to add LLM/embedding credentials)"
}
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Edit $RepoRoot\.env if you have not already."
Write-Host "  2. Restart Claude Code (or run /reload-plugins in an active session)."
Write-Host "  3. Verify: claude mcp list  # should show plugin:datamind-context:datamind-context Connected"
