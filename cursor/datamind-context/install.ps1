# Install DataMind Context as a Cursor plugin (Windows / PowerShell version).
#
# Mirrors install.sh on Unix:
#   1. Validate the plugin manifest.
#   2. Create a venv under <repo>\.venv and install requirements.txt.
#   3. Copy this folder to %USERPROFILE%\.cursor\plugins\local\datamind-context.
#   4. Replace mcp.json with mcp.windows.json so Cursor spawns the .ps1 launcher.
#   5. Copy .cursor\rules\datamind.mdc to %USERPROFILE%\.cursor\rules\datamind.mdc
#      so the Cursor Agent auto-triggers DataMind in any workspace.
#
# Usage (PowerShell):
#   .\install.ps1
#   .\install.ps1 -Force
#   .\install.ps1 -SkipDeps
#   .\install.ps1 -RepoRoot C:\path\to\DataMind
#   .\install.ps1 -PythonExe C:\Python311\python.exe

[CmdletBinding()]
param(
    [string]$RepoRoot,
    [switch]$Force,
    [switch]$SkipDeps,
    [string]$PythonExe = 'python'
)

$ErrorActionPreference = 'Stop'

$PluginName = 'datamind-context'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$TargetParent = Join-Path $env:USERPROFILE '.cursor\plugins\local'
$TargetDir = Join-Path $TargetParent $PluginName

function Resolve-BundledRepo($base) {
    foreach ($name in 'datamind', 'DataMind') {
        $candidate = Join-Path $base "vendor\$name"
        if ((Test-Path (Join-Path $candidate 'config.py')) -and (Test-Path (Join-Path $candidate 'core'))) {
            return (Resolve-Path $candidate).Path
        }
    }
    return $null
}

# --- 1. Resolve DataMind runtime root ---
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

if (-not (Test-Path (Join-Path $ScriptDir '.cursor-plugin\plugin.json'))) {
    Write-Error "Cannot find Cursor plugin manifest in $ScriptDir"
    exit 1
}

# --- 2. Copy plugin to ~/.cursor/plugins/local/datamind-context ---
New-Item -ItemType Directory -Force -Path $TargetParent | Out-Null

if ($ScriptDir -ne $TargetDir) {
    if ((Test-Path $TargetDir) -and -not $Force) {
        Write-Error "Target already exists: $TargetDir`nRerun with -Force to replace it."
        exit 1
    }
    if (Test-Path $TargetDir) { Remove-Item -Recurse -Force $TargetDir }
    New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null

    $exclusions = @('.DS_Store', '.datamind-repo-root', '__pycache__', '.pytest_cache', '.venv')
    Get-ChildItem -Path $ScriptDir -Force | Where-Object {
        $exclusions -notcontains $_.Name
    } | ForEach-Object {
        Copy-Item -Recurse -Force -Path $_.FullName -Destination $TargetDir
    }

    if ($RepoRoot.StartsWith($ScriptDir, [StringComparison]::OrdinalIgnoreCase)) {
        $bundled = Resolve-BundledRepo $TargetDir
        if ($bundled) { $RepoRoot = $bundled }
    }
}

Set-Content -Path (Join-Path $TargetDir '.datamind-repo-root') -Value $RepoRoot

# --- 3. Activate the Windows MCP config ---
$WinMcp = Join-Path $TargetDir 'mcp.windows.json'
$Mcp = Join-Path $TargetDir 'mcp.json'
if (Test-Path $WinMcp) {
    Copy-Item -Force $WinMcp $Mcp
    Write-Host "Activated Windows MCP config: $Mcp"
}

# --- 4. Create venv and install Python deps ---
if (-not (Test-Path (Join-Path $RepoRoot '.env')) -and (Test-Path (Join-Path $RepoRoot '.env.example'))) {
    Copy-Item -Force (Join-Path $RepoRoot '.env.example') (Join-Path $RepoRoot '.env')
    Write-Host "Created $($RepoRoot)\.env from .env.example. Edit it with your LLM and embedding credentials."
}

if (-not $SkipDeps) {
    $venvPy = Join-Path $RepoRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path $venvPy)) {
        & $PythonExe -m venv (Join-Path $RepoRoot '.venv')
    }
    & $venvPy -m pip install --upgrade pip
    & $venvPy -m pip install --prefer-binary -r (Join-Path $RepoRoot 'requirements.txt')
}

# --- 5. Install Cursor Rule globally ---
$RuleSrc = Join-Path $TargetDir '.cursor\rules\datamind.mdc'
$RuleDstDir = Join-Path $env:USERPROFILE '.cursor\rules'
$RuleDst = Join-Path $RuleDstDir 'datamind.mdc'

if (Test-Path $RuleSrc) {
    New-Item -ItemType Directory -Force -Path $RuleDstDir | Out-Null
    if ((Test-Path $RuleDst) -and -not $Force) {
        $srcHash = (Get-FileHash -Algorithm SHA256 $RuleSrc).Hash
        $dstHash = (Get-FileHash -Algorithm SHA256 $RuleDst).Hash
        if ($srcHash -ne $dstHash) {
            Write-Host ""
            Write-Host "Note: $RuleDst already exists and differs from the bundled rule."
            Write-Host "      Re-run with -Force to overwrite, or merge it manually."
        }
    } else {
        Copy-Item -Force $RuleSrc $RuleDst
        Write-Host "Installed Cursor Rule: $RuleDst"
    }
}

# --- 6. Friendly summary ---
Write-Host ""
Write-Host "Installed $PluginName for Cursor."
Write-Host "Plugin path:    $TargetDir"
Write-Host "DataMind repo:  $RepoRoot"
Write-Host ""
if (Test-Path (Join-Path $RepoRoot '.env')) {
    Write-Host "Before first use, make sure $RepoRoot\.env contains valid LLM and embedding credentials."
}
Write-Host "Next step: restart Cursor, then enable 'DataMind Context' from Settings -> Plugins -> Local Plugins."
