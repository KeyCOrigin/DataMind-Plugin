# PowerShell launcher for the DataMind MCP server (Claude Code variant).
#
# Mirrors src/run_datamind_mcp.sh on Unix, with Claude-Code-specific probes:
#   1. $env:DATAMIND_PYTHON                                 (explicit override)
#   2. $env:CLAUDE_PLUGIN_DATA\.venv                        (persistent across plugin updates)
#   3. <CODEX install>\vendor\datamind\.venv                (~/.codex/marketplaces/*/plugins/datamind-context/...)
#   4. <bundled vendor/datamind>\.venv                      (this plugin's own copy)
#   5. system `python` / `py`
#
# Designed to be invoked via .claude-plugin/mcp.json with:
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File <path-to-this-script>

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PluginDir = (Resolve-Path (Join-Path $ScriptDir '..')).Path

$RepoRoot = $env:DATAMIND_REPO_ROOT
$BundledRepoRoot = Join-Path $PluginDir 'vendor\datamind'
$RepoMarker = Join-Path $PluginDir '.datamind-repo-root'

# Codex install location: probe under %USERPROFILE%\.codex\marketplaces\*\plugins\datamind-context\vendor\datamind
$CodexInstallRepo = $null
$CodexMarketplaces = Join-Path $env:USERPROFILE '.codex\marketplaces'
if (Test-Path $CodexMarketplaces) {
    foreach ($mp in (Get-ChildItem -Path $CodexMarketplaces -Directory -ErrorAction SilentlyContinue)) {
        $candidate = Join-Path $mp.FullName 'plugins\datamind-context\vendor\datamind'
        $py = Join-Path $candidate '.venv\Scripts\python.exe'
        if ((Test-Path $py) -and (Test-Path (Join-Path $candidate 'config.py'))) {
            $CodexInstallRepo = $candidate
            break
        }
    }
}

if (-not $RepoRoot -and (Test-Path $RepoMarker)) {
    $RepoRoot = (Get-Content -Path $RepoMarker -TotalCount 1).Trim()
}

if (-not $RepoRoot -and (Test-Path (Join-Path $BundledRepoRoot 'config.py')) -and (Test-Path (Join-Path $BundledRepoRoot 'core'))) {
    $RepoRoot = $BundledRepoRoot
}

# Claude Code copies plugins to a cache dir on each update, so a venv inside
# the bundled vendor would be wiped. Prefer a Codex install if one was found
# (uses the same vendor/datamind/.venv layout).
$RepoVenvPy = if ($RepoRoot) { Join-Path $RepoRoot '.venv\Scripts\python.exe' } else { $null }
if (-not $RepoRoot -or -not (Test-Path $RepoVenvPy)) {
    if ($CodexInstallRepo) {
        $RepoRoot = $CodexInstallRepo
        $RepoVenvPy = Join-Path $CodexInstallRepo '.venv\Scripts\python.exe'
    }
}

if (-not $RepoRoot) {
    $RepoRoot = (Resolve-Path (Join-Path $PluginDir '..\..')).Path
    $RepoVenvPy = Join-Path $RepoRoot '.venv\Scripts\python.exe'
}

# Allow callers (typically the SessionStart hook) to keep a long-lived venv
# under $env:CLAUDE_PLUGIN_DATA. That directory survives plugin updates;
# the plugin source dir does not.
$DataVenvPy = $null
if ($env:CLAUDE_PLUGIN_DATA) {
    $candidate = Join-Path $env:CLAUDE_PLUGIN_DATA '.venv\Scripts\python.exe'
    if (Test-Path $candidate) { $DataVenvPy = $candidate }
}

$McpScript = Join-Path $PluginDir 'src\datamind_mcp.py'

if ($env:DATAMIND_PYTHON -and (Test-Path $env:DATAMIND_PYTHON)) {
    & $env:DATAMIND_PYTHON $McpScript
    exit $LASTEXITCODE
}

if ($DataVenvPy) {
    & $DataVenvPy $McpScript
    exit $LASTEXITCODE
}

if ($RepoVenvPy -and (Test-Path $RepoVenvPy)) {
    & $RepoVenvPy $McpScript
    exit $LASTEXITCODE
}

$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
    $Python = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $Python) {
    Write-Error "No Python interpreter found. Set `$env:DATAMIND_PYTHON or install Python 3."
    exit 1
}

if ($Python.Name -eq 'py.exe' -or $Python.Name -eq 'py') {
    & $Python.Source -3 $McpScript
} else {
    & $Python.Source $McpScript
}
exit $LASTEXITCODE
