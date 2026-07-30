#!/usr/bin/env bash
# Stop hook. Blocks stop if tests fail. Loop-safe via stop_hook_active.
# Fast path: --lf (last-failed) when cache exists, otherwise full sweep with
# "not slow" marker + -x (stop on first failure) + line traceback + soft timeout.
#
# Interruption guards (v1.0.2):
#   - Escape hatch: env TEST_GATE_OFF=1, or a `.claude/.test-gate-off` file -> skip entirely.
#   - A TIMEOUT is NOT a failure: if the run exceeds the cap, warn on stderr and DO NOT block
#     (a slow suite must not trap the agent at Stop). Real test failures still block.
#   - `timeout` is optional: falls back to `gtimeout`, else runs uncapped.
#
# Requires pytest to recognize the 'slow' marker in pyproject.toml or pytest.ini:
#   [tool.pytest.ini_options]
#   markers = ["slow: long-running backtests; excluded by test-gate"]
set -uo pipefail
input="$(cat)"

# JSON extraction via jq (~10ms startup) instead of python3 — a pyenv shim adds ~300ms
# per python3 call, which lands on EVERY Stop. python3 stays as a fallback for hosts
# without jq. PATCH-P003-APPLIED
if command -v jq >/dev/null 2>&1; then
  active="$(printf '%s' "$input" | jq -r '.stop_hook_active // false' 2>/dev/null)"
else
  active="$(INPUT="$input" python3 -c '
import os, json
try: d = json.loads(os.environ.get("INPUT","") or "{}")
except Exception: print("false")
else: print(str(d.get("stop_hook_active", False)).lower())
')"
fi
[ "$active" = "true" ] && exit 0

root="${CLAUDE_PROJECT_DIR:-.}"
cd "$root" 2>/dev/null || exit 0

# Escape hatch (env var or marker file) — lets a human silence the gate during triage.
[ "${TEST_GATE_OFF:-}" = "1" ] && { echo "[test-gate] disabled via TEST_GATE_OFF=1." >&2; exit 0; }
[ -f .claude/.test-gate-off ] && { echo "[test-gate] disabled via .claude/.test-gate-off file." >&2; exit 0; }

# Skip if no .py files changed — avoids running pytest on analysis/design/dispatch turns
# where no code was written. Falls through (no skip) if not a git repo.
# PATCH-P002-APPLIED
if git rev-parse --git-dir >/dev/null 2>&1; then
  if ! { git diff --name-only HEAD 2>/dev/null; git diff --name-only --cached 2>/dev/null; } \
       | grep -q '\.py$'; then
    echo "[test-gate] no .py files changed — skipping." >&2
    exit 0
  fi
fi

has_pytest=0
if [ -d tests ] || [ -f pytest.ini ] || grep -q "\[tool.pytest" pyproject.toml 2>/dev/null; then
  has_pytest=1
fi
[ "$has_pytest" -eq 1 ] || exit 0

# Prefer the project virtualenv. A bare `pytest` resolves to whatever is on PATH
# (a pyenv shim here), which lacks this repository's editable service installs and
# fails every collection with ModuleNotFoundError instead of reporting real failures.
if [ -x .venv/bin/pytest ]; then
  PYTEST=".venv/bin/pytest"
elif command -v pytest >/dev/null 2>&1; then
  PYTEST="pytest"
else
  exit 0
fi

# Optional timeout wrapper — GNU coreutils `timeout`, macOS `gtimeout`, else uncapped.
TO=""
if command -v timeout >/dev/null 2>&1; then TO="timeout"
elif command -v gtimeout >/dev/null 2>&1; then TO="gtimeout"; fi
run_to() {  # run_to <secs> <cmd...>; returns the command's exit code (124 on timeout)
  local secs="$1"; shift
  if [ -n "$TO" ]; then "$TO" "$secs" "$@"; else "$@"; fi
}

# Fast path: if a previous failure cache exists, run only those.
if [ -f .pytest_cache/v/cache/lastfailed ] && [ -s .pytest_cache/v/cache/lastfailed ]; then
  run_to 120 "$PYTEST" -q --no-header --lf -m "not slow" --tb=line >/tmp/_testgate.log 2>&1
  rc=$?
  if [ "$rc" -eq 124 ]; then
    echo "[test-gate] --lf run exceeded 120s and was stopped; NOT blocking. Run the suite manually." >&2
    exit 0
  fi
  # Exit 5 means pytest collected nothing to run (every last-failed test was
  # deselected by the marker filter). That is not a failure.
  if [ "$rc" -eq 5 ]; then
    exit 0
  fi
  if [ "$rc" -ne 0 ]; then
    tail -n 30 /tmp/_testgate.log >&2
    echo "BLOCKED by test-gate (--lf): previously failing tests still red. Fix, or set TEST_GATE_OFF=1 / touch .claude/.test-gate-off to override." >&2
    exit 2
  fi
  exit 0
fi

# Full sweep, slow marker excluded, line tracebacks, stop on first failure.
run_to 180 "$PYTEST" -q --no-header -m "not slow" --tb=line -x >/tmp/_testgate.log 2>&1
rc=$?
if [ "$rc" -eq 124 ]; then
  echo "[test-gate] full run exceeded 180s and was stopped; NOT blocking. Run the suite manually, or mark long tests 'slow'." >&2
  exit 0
fi
if [ "$rc" -eq 5 ]; then
  exit 0
fi
if [ "$rc" -ne 0 ]; then
  tail -n 30 /tmp/_testgate.log >&2
  echo "BLOCKED by test-gate: tests failing (-m 'not slow'). Fix, or set TEST_GATE_OFF=1 / touch .claude/.test-gate-off to override." >&2
  exit 2
fi
exit 0
