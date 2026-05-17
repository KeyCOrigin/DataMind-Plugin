#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PLUGIN_NAME="datamind-context"
TARGET_PARENT="${HOME}/.cursor/plugins/local"
TARGET_DIR="${TARGET_PARENT}/${PLUGIN_NAME}"
REPO_ROOT=""
FORCE="false"
SKIP_DEPS="false"
PYTHON_BIN="${PYTHON_BIN:-python3}"

usage() {
  cat <<'EOF'
Install DataMind Context as a local Cursor plugin.

Usage:
  ./install.sh [--repo-root /path/to/DataMind] [--force] [--skip-deps]

Options:
  --repo-root PATH   Existing DataMind repository root. Optional when this
                     release package includes vendor/datamind.
  --force            Replace an existing ~/.cursor/plugins/local/datamind-context
                     directory.
  --skip-deps        Do not create a venv or install Python dependencies.
  --python PATH      Python interpreter to use for venv creation.
  -h, --help         Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-root)
      REPO_ROOT="${2:-}"
      shift 2
      ;;
    --force)
      FORCE="true"
      shift
      ;;
    --skip-deps)
      SKIP_DEPS="true"
      shift
      ;;
    --python)
      PYTHON_BIN="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

detect_bundled_repo() {
  local base="$1"
  if [[ -f "${base}/vendor/datamind/config.py" && -d "${base}/vendor/datamind/core" ]]; then
    printf "%s\n" "$(cd "${base}/vendor/datamind" && pwd -P)"
    return 0
  fi
  if [[ -f "${base}/vendor/DataMind/config.py" && -d "${base}/vendor/DataMind/core" ]]; then
    printf "%s\n" "$(cd "${base}/vendor/DataMind" && pwd -P)"
    return 0
  fi
  return 1
}

if [[ -z "${REPO_ROOT}" ]]; then
  if BUNDLED_REPO="$(detect_bundled_repo "${SCRIPT_DIR}")"; then
    REPO_ROOT="${BUNDLED_REPO}"
  fi
fi

if [[ -z "${REPO_ROOT}" ]]; then
  CANDIDATE="$(cd "${SCRIPT_DIR}/../.." && pwd -P)"
  if [[ -f "${CANDIDATE}/config.py" && -d "${CANDIDATE}/core" ]]; then
    REPO_ROOT="${CANDIDATE}"
  fi
fi

if [[ -z "${REPO_ROOT}" ]]; then
  echo "Missing DataMind runtime." >&2
  echo "Use --repo-root /path/to/DataMind, or install from a release package that includes vendor/datamind." >&2
  exit 1
fi

REPO_ROOT="$(cd "${REPO_ROOT}" && pwd -P)"
if [[ ! -f "${REPO_ROOT}/config.py" || ! -d "${REPO_ROOT}/core" ]]; then
  echo "Not a DataMind repository root: ${REPO_ROOT}" >&2
  exit 1
fi

if [[ ! -f "${SCRIPT_DIR}/.cursor-plugin/plugin.json" ]]; then
  echo "Cannot find Cursor plugin manifest in ${SCRIPT_DIR}" >&2
  exit 1
fi

mkdir -p "${TARGET_PARENT}"

if [[ "${SCRIPT_DIR}" != "${TARGET_DIR}" ]]; then
  if [[ -e "${TARGET_DIR}" && "${FORCE}" != "true" ]]; then
    echo "Target already exists: ${TARGET_DIR}" >&2
    echo "Rerun with --force to replace it." >&2
    exit 1
  fi
  rm -rf "${TARGET_DIR}"
  mkdir -p "${TARGET_DIR}"
  rsync -a \
    --exclude ".DS_Store" \
    --exclude ".datamind-repo-root" \
    --exclude "__pycache__" \
    --exclude ".pytest_cache" \
    --exclude ".venv" \
    --exclude "vendor/datamind/.venv" \
    "${SCRIPT_DIR}/" "${TARGET_DIR}/"
fi

if [[ "${SCRIPT_DIR}" != "${TARGET_DIR}" ]]; then
  if [[ "${REPO_ROOT}" == "${SCRIPT_DIR}/"* ]]; then
    if BUNDLED_REPO="$(detect_bundled_repo "${TARGET_DIR}")"; then
      REPO_ROOT="${BUNDLED_REPO}"
    fi
  fi
fi

printf "%s\n" "${REPO_ROOT}" > "${TARGET_DIR}/.datamind-repo-root"
chmod +x "${TARGET_DIR}/install.sh" "${TARGET_DIR}/src/run_datamind_mcp.sh"

if [[ ! -f "${REPO_ROOT}/.env" && -f "${REPO_ROOT}/.env.example" ]]; then
  cp "${REPO_ROOT}/.env.example" "${REPO_ROOT}/.env"
  echo "Created ${REPO_ROOT}/.env from .env.example. Edit it with your LLM and embedding credentials."
fi

if [[ "${SKIP_DEPS}" != "true" ]]; then
  if [[ ! -x "${REPO_ROOT}/.venv/bin/python" ]]; then
    "${PYTHON_BIN}" -m venv "${REPO_ROOT}/.venv"
  fi
  "${REPO_ROOT}/.venv/bin/python" -m pip install --upgrade pip
  "${REPO_ROOT}/.venv/bin/python" -m pip install --prefer-binary -r "${REPO_ROOT}/requirements.txt"
fi

# Install the Cursor Rules file globally so the Agent auto-triggers DataMind
# in any Cursor workspace. Cursor only auto-loads rules from ~/.cursor/rules/
# (global) or <workspace>/.cursor/rules/ (project) — not from the installed
# plugin directory itself.
RULE_SRC="${TARGET_DIR}/.cursor/rules/datamind.mdc"
RULE_DST_DIR="${HOME}/.cursor/rules"
RULE_DST="${RULE_DST_DIR}/datamind.mdc"

if [[ -f "${RULE_SRC}" ]]; then
  mkdir -p "${RULE_DST_DIR}"
  if [[ -f "${RULE_DST}" && "${FORCE}" != "true" ]]; then
    if ! cmp -s "${RULE_SRC}" "${RULE_DST}"; then
      echo
      echo "Note: ${RULE_DST} already exists and differs from the bundled rule."
      echo "      Re-run with --force to overwrite, or merge it manually."
    fi
  else
    cp "${RULE_SRC}" "${RULE_DST}"
    echo "Installed Cursor Rule: ${RULE_DST}"
  fi
fi

echo "Installed ${PLUGIN_NAME} for Cursor."
echo "Plugin path: ${TARGET_DIR}"
echo "DataMind repo root: ${REPO_ROOT}"
echo
if [[ -f "${REPO_ROOT}/.env" ]]; then
  echo "Before first use, make sure ${REPO_ROOT}/.env contains valid LLM and embedding credentials."
fi
echo "Next step: restart Cursor, then enable 'DataMind Context' from Settings -> Plugins -> Local Plugins."
