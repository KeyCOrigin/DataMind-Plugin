#!/usr/bin/env bash
# SessionStart hook for the Claude Code DataMind plugin.
#
# Goal: make sure a usable Python environment exists for vendor/datamind.
# Strategy:
#   1. If a Codex install under ~/.codex/marketplaces/*/plugins/datamind-context/vendor/datamind
#      already has a venv, do nothing: run_datamind_mcp.sh will discover and reuse it.
#   2. Otherwise, lazily create a persistent venv under ${CLAUDE_PLUGIN_DATA}
#      and install requirements.txt. Re-run pip install only when the bundled
#      requirements.txt has changed since the last install.
#
# This hook is best-effort. It prints to stderr so it shows up in `claude --debug`
# but never blocks the session if it fails (the MCP server will surface the
# real error on first call).

set -uo pipefail

eprint() { printf '[datamind-context] %s\n' "$*" >&2; }

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-}"
DATA_DIR="${CLAUDE_PLUGIN_DATA:-}"

if [[ -z "${PLUGIN_ROOT}" || -z "${DATA_DIR}" ]]; then
  # Variables only get set when the plugin is loaded by Claude Code; if we are
  # invoked outside that, just bail quietly.
  exit 0
fi

REPO_BUNDLED="${PLUGIN_ROOT}/vendor/datamind"

# Find a Codex install under ~/.codex/marketplaces/*/plugins/datamind-context/vendor/datamind
REPO_CODEX=""
if [[ -d "${HOME}/.codex/marketplaces" ]]; then
  for d in "${HOME}/.codex/marketplaces"/*/plugins/datamind-context/vendor/datamind; do
    if [[ -x "${d}/.venv/bin/python" && -f "${d}/config.py" ]]; then
      REPO_CODEX="${d}"
      break
    fi
  done
fi

if [[ -n "${REPO_CODEX}" ]]; then
  eprint "reusing Codex install at ${REPO_CODEX}"
  exit 0
fi

if [[ ! -f "${REPO_BUNDLED}/requirements.txt" ]]; then
  eprint "no bundled vendor/datamind/requirements.txt; nothing to bootstrap"
  exit 0
fi

mkdir -p "${DATA_DIR}"
VENV_DIR="${DATA_DIR}/.venv"
STAMP_PATH="${DATA_DIR}/requirements.txt"

needs_install="false"
if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  needs_install="true"
elif ! diff -q "${REPO_BUNDLED}/requirements.txt" "${STAMP_PATH}" >/dev/null 2>&1; then
  needs_install="true"
fi

if [[ "${needs_install}" != "true" ]]; then
  exit 0
fi

PYTHON_BIN="${DATAMIND_PYTHON:-python3}"
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  eprint "python3 not found; install Python 3 or set DATAMIND_PYTHON"
  exit 0
fi

eprint "creating venv at ${VENV_DIR} (this runs once per requirements change)"
if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  if ! "${PYTHON_BIN}" -m venv "${VENV_DIR}"; then
    eprint "failed to create venv; will fall back to system python at runtime"
    exit 0
  fi
fi

if ! "${VENV_DIR}/bin/python" -m pip install --upgrade pip >&2; then
  eprint "pip upgrade failed; continuing anyway"
fi

if ! "${VENV_DIR}/bin/python" -m pip install -r "${REPO_BUNDLED}/requirements.txt" >&2; then
  eprint "pip install failed; remove ${VENV_DIR} and re-open Claude Code to retry"
  rm -f "${STAMP_PATH}"
  exit 0
fi

cp "${REPO_BUNDLED}/requirements.txt" "${STAMP_PATH}"
eprint "venv ready"
exit 0
