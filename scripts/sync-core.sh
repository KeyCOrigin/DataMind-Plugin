#!/usr/bin/env bash
# sync-core.sh — keep the three plugin variants in sync.
#
# `codex/datamind-context/` is the source of truth. This script copies the
# files that should be IDENTICAL across all three variants into the other two.
#
# Files synced (identical across variants):
#   src/datamind_mcp.py
#   src/datamind_task.py
#   src/memory_store.py
#   vendor/datamind/                      (entire tree)
#   assets/datamind-context.svg
#
# Files NOT synced (intentionally per-variant):
#   src/run_datamind_mcp.sh               (Claude Code has extra venv probes)
#   skills/datamind-context/SKILL.md      (uses "Codex"/"Claude Code"/"Cursor")
#   install.sh                            (per-IDE install logic)
#   .codex-plugin/  .claude-plugin/  .cursor-plugin/
#   .mcp.json  /  mcp.json  /  .claude-plugin/mcp.json
#   .claude-plugin/marketplace.json
#   hooks/  scripts/bootstrap_claude.sh   (Claude Code only)
#   .cursor/rules/datamind.mdc            (Cursor only)
#   README.md  INSTALL.md  USAGE.md  RELEASE_NOTES.md
#
# Usage:
#   ./scripts/sync-core.sh             # apply sync
#   ./scripts/sync-core.sh --check     # dry run; show diffs without writing

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
SOURCE="${REPO_ROOT}/codex/datamind-context"
TARGETS=(
  "${REPO_ROOT}/claude-code/datamind-context"
  "${REPO_ROOT}/cursor/datamind-context"
)

SHARED_FILES=(
  "src/datamind_mcp.py"
  "src/datamind_task.py"
  "src/memory_store.py"
  "assets/datamind-context.svg"
)
SHARED_DIRS=(
  "vendor/datamind"
)

CHECK_ONLY="false"
case "${1:-}" in
  --check) CHECK_ONLY="true" ;;
  -h|--help)
    sed -n '2,/^set -euo/p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
    ;;
  "") ;;
  *) echo "Unknown argument: $1" >&2; exit 1 ;;
esac

if [[ ! -d "${SOURCE}" ]]; then
  echo "Source not found: ${SOURCE}" >&2
  exit 1
fi

drift_count=0

for target in "${TARGETS[@]}"; do
  if [[ ! -d "${target}" ]]; then
    echo "WARN: target missing: ${target}" >&2
    continue
  fi

  echo
  echo "=== ${target} ==="

  for f in "${SHARED_FILES[@]}"; do
    if [[ ! -f "${SOURCE}/${f}" ]]; then
      echo "  SKIP (no source): ${f}"
      continue
    fi
    if ! diff -q "${SOURCE}/${f}" "${target}/${f}" >/dev/null 2>&1; then
      drift_count=$((drift_count + 1))
      if [[ "${CHECK_ONLY}" == "true" ]]; then
        echo "  DRIFT: ${f}"
      else
        mkdir -p "$(dirname "${target}/${f}")"
        cp "${SOURCE}/${f}" "${target}/${f}"
        echo "  SYNC: ${f}"
      fi
    fi
  done

  for d in "${SHARED_DIRS[@]}"; do
    if [[ ! -d "${SOURCE}/${d}" ]]; then
      echo "  SKIP (no source dir): ${d}"
      continue
    fi
    # Use rsync to compare and (optionally) copy. -n is dry-run.
    if [[ "${CHECK_ONLY}" == "true" ]]; then
      drift=$(rsync -an --delete --itemize-changes \
        --exclude '__pycache__' --exclude '.venv' --exclude '.env' \
        "${SOURCE}/${d}/" "${target}/${d}/" 2>/dev/null \
        | grep -v '^\.[fdL]' | grep -v '^$' || true)
      if [[ -n "${drift}" ]]; then
        drift_count=$((drift_count + 1))
        echo "  DRIFT in ${d}/:"
        echo "${drift}" | sed 's/^/    /'
      fi
    else
      rsync -a --delete \
        --exclude '__pycache__' --exclude '.venv' --exclude '.env' \
        "${SOURCE}/${d}/" "${target}/${d}/"
      echo "  SYNC: ${d}/"
    fi
  done
done

echo
if [[ "${CHECK_ONLY}" == "true" ]]; then
  if [[ ${drift_count} -gt 0 ]]; then
    echo "Found ${drift_count} drift point(s). Run without --check to fix."
    exit 1
  fi
  echo "All variants in sync."
else
  echo "Sync complete."
fi
