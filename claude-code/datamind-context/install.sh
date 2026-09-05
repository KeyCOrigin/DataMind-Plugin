#!/usr/bin/env bash
set -euo pipefail

# Install DataMind Context as a Claude Code plugin via the local marketplace.
#
# What this script does:
#   1. Validate that the directory looks like a Claude Code plugin.
#   2. (Default) Create a Python venv under vendor/datamind/ and install
#      requirements.txt, so Claude Code's SessionStart hook does not have to.
#   3. Run `claude plugin marketplace add` and `claude plugin install` so the
#      plugin shows up after the next Claude Code restart.
#
# Usage:
#   ./install.sh [--force] [--skip-deps] [--python /path/to/python3]
#
# After running, restart Claude Code and confirm:
#   claude plugin list           # should include datamind-context@datamind
#   claude mcp list              # should show plugin:datamind-context:datamind-context ✓ Connected

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PLUGIN_NAME="datamind-context"
MARKETPLACE_NAME="datamind"
REPO_ROOT=""
FORCE="false"
SKIP_DEPS="false"
PYTHON_BIN="${PYTHON_BIN:-python3}"

usage() {
  cat <<'EOF'
Install DataMind Context as a Claude Code plugin.

Usage:
  ./install.sh [--repo-root /path/to/DataMind] [--force] [--skip-deps] [--python PATH]

Options:
  --repo-root PATH   Existing DataMind runtime (defaults to bundled vendor/datamind).
  --force            If a previous install exists, replace it.
  --skip-deps        Do not create venv or install Python dependencies.
                     The SessionStart hook will lazily install them on first use.
  --python PATH      Python interpreter to use for venv creation.
  -h, --help         Show this help.

Requirements:
  - Python 3
  - `claude` CLI in PATH (https://docs.claude.com/claude-code)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-root)  REPO_ROOT="${2:-}"; shift 2 ;;
    --force)      FORCE="true"; shift ;;
    --skip-deps)  SKIP_DEPS="true"; shift ;;
    --python)     PYTHON_BIN="${2:-}"; shift 2 ;;
    -h|--help)    usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done

# --- 1. Sanity checks ----------------------------------------------------

if [[ ! -f "${SCRIPT_DIR}/.claude-plugin/plugin.json" ]]; then
  echo "Cannot find Claude Code plugin manifest in ${SCRIPT_DIR}" >&2
  echo "Run this script from inside the unpacked claude-code/datamind-context/ directory." >&2
  exit 1
fi

if ! command -v claude >/dev/null 2>&1; then
  echo "ERROR: 'claude' CLI not found in PATH." >&2
  echo "Install Claude Code first: https://docs.claude.com/claude-code" >&2
  exit 1
fi

detect_bundled_repo() {
  local base="$1"
  if [[ -f "${base}/vendor/datamind/config.py" && -d "${base}/vendor/datamind/core" ]]; then
    printf "%s\n" "$(cd "${base}/vendor/datamind" && pwd -P)"
    return 0
  fi
  return 1
}

if [[ -z "${REPO_ROOT}" ]]; then
  if BUNDLED="$(detect_bundled_repo "${SCRIPT_DIR}")"; then
    REPO_ROOT="${BUNDLED}"
  fi
fi

if [[ -z "${REPO_ROOT}" ]]; then
  echo "Missing DataMind runtime." >&2
  echo "Use --repo-root /path/to/DataMind, or run from a release that includes vendor/datamind." >&2
  exit 1
fi

REPO_ROOT="$(cd "${REPO_ROOT}" && pwd -P)"
if [[ ! -f "${REPO_ROOT}/config.py" || ! -d "${REPO_ROOT}/core" ]]; then
  echo "Not a DataMind repository root: ${REPO_ROOT}" >&2
  exit 1
fi

# --- 2. Optional: create venv + install dependencies ---------------------

if [[ "${SKIP_DEPS}" != "true" ]]; then
  if [[ ! -x "${REPO_ROOT}/.venv/bin/python" ]]; then
    echo "Creating venv at ${REPO_ROOT}/.venv ..."
    "${PYTHON_BIN}" -m venv "${REPO_ROOT}/.venv"
  fi
  "${REPO_ROOT}/.venv/bin/python" -m pip install --upgrade pip
  "${REPO_ROOT}/.venv/bin/python" -m pip install --prefer-binary -r "${REPO_ROOT}/requirements.txt"
fi

if [[ ! -f "${REPO_ROOT}/.env" && -f "${REPO_ROOT}/.env.example" ]]; then
  cp "${REPO_ROOT}/.env.example" "${REPO_ROOT}/.env"
  echo "Created ${REPO_ROOT}/.env from .env.example. Edit it with your LLM and embedding credentials."
fi

chmod +x "${SCRIPT_DIR}/src/run_datamind_mcp.sh" "${SCRIPT_DIR}/scripts/bootstrap_claude.sh"

# --- 3. Register and install with Claude Code ---------------------------

# If a previous install exists and --force was passed, remove it first.
if [[ "${FORCE}" == "true" ]]; then
  claude plugin uninstall "${PLUGIN_NAME}@${MARKETPLACE_NAME}" 2>/dev/null || true
  claude plugin marketplace remove "${MARKETPLACE_NAME}" 2>/dev/null || true
fi

# Add this directory as a local marketplace.
if ! claude plugin marketplace list 2>/dev/null | grep -q "^[[:space:]]*❯[[:space:]]\+${MARKETPLACE_NAME}\b"; then
  claude plugin marketplace add "${SCRIPT_DIR}"
else
  echo "Marketplace '${MARKETPLACE_NAME}' already registered. Use --force to replace."
fi

# Install the plugin.
if ! claude plugin list 2>/dev/null | grep -q "${PLUGIN_NAME}@${MARKETPLACE_NAME}"; then
  claude plugin install "${PLUGIN_NAME}@${MARKETPLACE_NAME}"
else
  echo "Plugin '${PLUGIN_NAME}@${MARKETPLACE_NAME}' already installed. Use --force to reinstall."
fi

# --- 4. Friendly summary ------------------------------------------------

echo
echo "Installed ${PLUGIN_NAME} for Claude Code."
echo "Plugin source:   ${SCRIPT_DIR}"
echo "DataMind repo:   ${REPO_ROOT}"
if [[ -f "${REPO_ROOT}/.env" ]]; then
  echo "Env file:        ${REPO_ROOT}/.env  (edit to add LLM/embedding credentials)"
fi
echo
echo "Next steps:"
echo "  1. Edit ${REPO_ROOT}/.env if you have not already."
echo "  2. Restart Claude Code (or run /reload-plugins in an active session)."
echo "  3. Verify: claude mcp list  # should show plugin:datamind-context:datamind-context ✓ Connected"
