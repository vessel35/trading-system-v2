#!/usr/bin/env bash
# SessionStart hook. Re-injects active objective + guardrails into context every session
# so agents stay anchored to the goal (anti-drift). Warns if OBJECTIVE.md is still a placeholder.
# SessionStart cannot block (exit 2 has no effect here) — stderr is the only signal.
set -uo pipefail
root="${CLAUDE_PROJECT_DIR:-.}"

echo "=== HARNESS GUARDRAILS (Quant Python backend) ==="
echo "- Single driver = this session, on Sonnet 5.5. Model and effort follow the stage table in .claude/HARNESS.md: Opus 5.5 for design, acceptance testing, money-path implementation, the author-strategy agent, and reclassified work; Haiku 5.5 for QA and marked mechanical changesets. Only this session commits and pushes."
echo "- Designs are mermaid UML (class diagram, sequence diagram, flowchart) plus a test plan table; prose only where a diagram cannot carry the meaning. A mechanical changeset may omit the diagrams but still writes a short design record."
echo "- Codex (gpt-6.2-sol) does design review and code review, never co-drives. See .claude/HARNESS.md 'Who does what'."
echo "- Stages that need another model run in stage agents (Agent tool, model and effort from the stage table); hand-offs are files the next stage reads (repository files, or the QA log in the scratch directory), not summaries. Strategy rounds use their own author-strategy and verify-strategy agents. Never dispatch the retired .claude/agents/ definitions."
echo "- DBs are READ-ONLY except a write the user approves (such as dev signal_db registration) and test fixtures that add and remove their own disposable rows or schemas. Strategies run dry-run. No live orders."
echo "- Do not change the assigned objective. If it's wrong/blocked, report and wait."
echo "- Context discipline: use /compact (not /clear) to shed tokens while keeping working state."
echo "- Docs & reports: complete sentences; no ad-hoc abbreviations or symbol shorthand; plain but exact terms; no forced literal translation."
echo ""

obj="$root/.claude/OBJECTIVE.md"
if [ ! -f "$obj" ]; then
  echo "[!] .claude/OBJECTIVE.md MISSING. Create one before starting work." >&2
  exit 0
fi

if grep -Eq '\(e\.g\.|TODO|<fill[- ]in>|XXX' "$obj"; then
  echo "[!] OBJECTIVE.md appears UNEDITED (placeholder markers detected: '(e.g.' / 'TODO' / '<fill in>' / 'XXX')." >&2
  echo "[!] Agents will anchor to placeholder text. Edit .claude/OBJECTIVE.md and restart this session." >&2
fi

echo "=== CURRENT OBJECTIVE (.claude/OBJECTIVE.md) ==="
cat "$obj"
exit 0
