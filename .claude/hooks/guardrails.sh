#!/usr/bin/env bash
# SessionStart hook. Re-injects active objective + guardrails into context every session
# so agents stay anchored to the goal (anti-drift). Warns if OBJECTIVE.md is still a placeholder.
# SessionStart cannot block (exit 2 has no effect here) — stderr is the only signal.
set -uo pipefail
root="${CLAUDE_PROJECT_DIR:-.}"

echo "=== HARNESS GUARDRAILS (Quant Python backend) ==="
echo "- Single driver = this session (Opus). Codex/GPT-5.5 reviews, never co-drives."
echo "- Each subagent stays in its lane. Out-of-lane work -> STOP and escalate to the human."
echo "- DBs are READ-ONLY. Strategies run dry-run. No live orders."
echo "- Do not change the assigned objective. If it's wrong/blocked, report and wait."
echo "- Context discipline: use /compact (not /clear); delegate to subagents to preserve orchestrator state."
echo "- Docs & reports: complete sentences; no ad-hoc abbreviations or symbol shorthand; plain but exact terms; no forced literal translation."
echo ""

obj="$root/.claude/OBJECTIVE.md"
if [ ! -f "$obj" ]; then
  echo "[!] .claude/OBJECTIVE.md MISSING. Create one before dispatching any subagent." >&2
  exit 0
fi

if grep -Eq '\(e\.g\.|TODO|<fill[- ]in>|XXX' "$obj"; then
  echo "[!] OBJECTIVE.md appears UNEDITED (placeholder markers detected: '(e.g.' / 'TODO' / '<fill in>' / 'XXX')." >&2
  echo "[!] Agents will anchor to placeholder text. Edit .claude/OBJECTIVE.md and restart this session." >&2
fi

echo "=== CURRENT OBJECTIVE (.claude/OBJECTIVE.md) ==="
cat "$obj"
exit 0
