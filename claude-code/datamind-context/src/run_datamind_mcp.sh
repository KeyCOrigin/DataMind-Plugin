#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PLUGIN_DIR="$(cd "${SCRIPT_DIR}/.." && pwd -P)"
REPO_ROOT="${DATAMIND_REPO_ROOT:-}"
BUNDLED_REPO_ROOT="${PLUGIN_DIR}/vendor/datamind"

# Codex install location (created by ./install.sh in the Codex flow).
CODEX_INSTALL_REPO="${HOME}/plugins/datamind-context/vendor/datamind"

if [[ -z "${REPO_ROOT}" && -f "${PLUGIN_DIR}/.datamind-repo-root" ]]; then
  REPO_ROOT="$(head -n 1 "${PLUGIN_DIR}/.datamind-repo-root")"
fi

if [[ -z "${REPO_ROOT}" && -f "${BUNDLED_REPO_ROOT}/config.py" && -d "${BUNDLED_REPO_ROOT}/core" ]]; then
  REPO_ROOT="${BUNDLED_REPO_ROOT}"
fi

# Claude Code copies plugins into ~/.claude/plugins/cache on each update,
# so a venv inside ${BUNDLED_REPO_ROOT} would be wiped. Prefer a Codex-style
# install at ~/plugins/datamind-context/vendor/datamind when available.
if [[ -z "${REPO_ROOT}" || ! -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  if [[ -x "${CODEX_INSTALL_REPO}/.venv/bin/python" && -f "${CODEX_INSTALL_REPO}/config.py" ]]; then
    REPO_ROOT="${CODEX_INSTALL_REPO}"
  fi
fi

if [[ -z "${REPO_ROOT}" ]]; then
  REPO_ROOT="$(cd "${PLUGIN_DIR}/../.." && pwd -P)"
fi

# Allow callers (or a one-shot Claude install hook) to keep a long-lived venv
# under ${CLAUDE_PLUGIN_DATA}. CLAUDE_PLUGIN_DATA survives plugin updates,
# while the plugin source dir does not.
DATA_VENV_PY=""
if [[ -n "${CLAUDE_PLUGIN_DATA:-}" && -x "${CLAUDE_PLUGIN_DATA}/.venv/bin/python" ]]; then
  DATA_VENV_PY="${CLAUDE_PLUGIN_DATA}/.venv/bin/python"
fi

if [[ -n "${DATAMIND_PYTHON:-}" && -x "${DATAMIND_PYTHON}" ]]; then
  exec "${DATAMIND_PYTHON}" "${PLUGIN_DIR}/src/datamind_mcp.py"
fi

if [[ -n "${DATA_VENV_PY}" ]]; then
  exec "${DATA_VENV_PY}" "${PLUGIN_DIR}/src/datamind_mcp.py"
fi

if [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  exec "${REPO_ROOT}/.venv/bin/python" "${PLUGIN_DIR}/src/datamind_mcp.py"
fi

exec python3 "${PLUGIN_DIR}/src/datamind_mcp.py"
