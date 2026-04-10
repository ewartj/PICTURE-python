#!/usr/bin/env bash
# PICTURE AI code review script
# Usage:
#   ./review.sh                        # review all staged changes
#   ./review.sh --commit <sha>         # review a specific commit
#   ./review.sh --branch <branch>      # review branch diff against master
#   ./review.sh --folder <path>        # review all Python files in a folder
#   ./review.sh --block-on-issues      # exit 1 if any BLOCK found (used by pre-commit hook)

set -uo pipefail

CLAUDE=$(find ~/.vscode/extensions -name "claude" -path "*/native-binary/claude" -type f 2>/dev/null | sort -V | tail -1)

if [ -z "$CLAUDE" ]; then
  echo "Claude Code binary not found. Is the Claude Code VS Code extension installed?"
  exit 0  # Don't block — degrade gracefully
fi

# --- Parse arguments ---
MODE="staged"
TARGET=""
BLOCK_ON_ISSUES=0

while [[ $# -gt 0 ]]; do
  case $1 in
    --commit)         MODE="commit";  TARGET="$2"; shift 2 ;;
    --branch)         MODE="branch";  TARGET="$2"; shift 2 ;;
    --folder)         MODE="folder";  TARGET="$2"; shift 2 ;;
    --block-on-issues) BLOCK_ON_ISSUES=1; shift ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

# --- Build content to review ---
case $MODE in
  staged)
    CONTENT=$(git diff --cached)
    LABEL="staged changes"
    if [ -z "$CONTENT" ]; then
      exit 0  # Nothing staged, skip silently
    fi
    ;;
  commit)
    CONTENT=$(git show "$TARGET")
    LABEL="commit $TARGET"
    ;;
  branch)
    CONTENT=$(git diff "master...$TARGET")
    LABEL="branch $TARGET vs master"
    ;;
  folder)
    CONTENT=$(find "$TARGET" -name "*.py" | sort | while read -r f; do
      echo "=== $f ==="
      cat "$f"
      echo ""
    done)
    LABEL="folder $TARGET"
    ;;
esac

echo ""
echo "PICTURE AI Code Review — $LABEL"
echo "============================================================"
echo ""
echo "Running 3 agents in parallel..."
echo ""

# --- Temp files to capture output and detect BLOCKs ---
TMP_SECURITY=$(mktemp)
TMP_ARCH=$(mktemp)
TMP_QUALITY=$(mktemp)
cleanup() { rm -f "$TMP_SECURITY" "$TMP_ARCH" "$TMP_QUALITY"; }
trap cleanup EXIT

run_agent() {
  local outfile="$1"
  local name="$2"
  local role="$3"
  local focus="$4"

  "$CLAUDE" -p \
    "You are the PICTURE $role. Review the following for $focus.
PICTURE architecture rules: core/ must never import fastapi/streamlit/uvicorn. api/ does no computation. Analytics modules implement AnalysisBase (compute/plot/to_dict).
If you find a BLOCK-level issue start that line with 'BLOCK:'. If minor, start with 'WARN:'. If clean, start with 'OK:'. Be concise, under 8 lines.

$LABEL:
$CONTENT" \
    --allowedTools "" \
    --max-turns 1 \
    2>/dev/null | sed "s/^/[$name] /" | tee "$outfile"
}

# Run all three in parallel
run_agent "$TMP_SECURITY" "SECURITY"     "security & PHI reviewer"  \
  "hardcoded secrets, PHI in logs, unvalidated inputs, unsafe patient data exposure" &
PID1=$!

run_agent "$TMP_ARCH"     "ARCHITECTURE" "backend architect"         \
  "core/ isolation violations, api/ doing computation, missing AnalysisBase methods, Pydantic v2 schema issues" &
PID2=$!

run_agent "$TMP_QUALITY"  "QUALITY"      "code quality reviewer"     \
  "bare except clauses, missing None checks on RDV inputs, silent data failures, black formatting violations (line-length 100, py311)" &
PID3=$!

wait $PID1; wait $PID2; wait $PID3

echo ""
echo "============================================================"

# --- Block commit if --block-on-issues and any BLOCK found ---
if [ "$BLOCK_ON_ISSUES" -eq 1 ]; then
  if grep -q "^\[.*\] BLOCK:" "$TMP_SECURITY" "$TMP_ARCH" "$TMP_QUALITY" 2>/dev/null; then
    echo "Commit BLOCKED by Claude review. Fix the issues above and try again."
    echo "To skip (not recommended): git commit --no-verify"
    exit 1
  else
    echo "Claude review passed. Proceeding with commit."
    exit 0
  fi
fi

echo "Review complete."
