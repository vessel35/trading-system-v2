#!/usr/bin/env bash
# PreToolUse on Write|Edit|MultiEdit|Bash. Blocks LITERAL secrets (API keys, PEM).
# Allows env-var references like ${OPENAI_API_KEY} or os.environ[...].
# Scope: backtest-only — wallet seed / private-key patterns intentionally NOT included
# (separate preset if live trading is ever added).
set -uo pipefail
input="$(cat)"

# JSON extraction via jq (~10ms startup) instead of python3 — a pyenv shim adds ~300ms
# per python3 call, which lands on EVERY Write/Edit/Bash. python3 stays as a fallback
# for hosts without jq. PATCH-P003-APPLIED
if command -v jq >/dev/null 2>&1; then
  payload="$(printf '%s' "$input" | jq -r '
    (.tool_input // {}) as $ti |
    [($ti.command // ""), ($ti.content // ""), ($ti.new_string // ""), ($ti.new_str // "")]
    + [($ti.edits // [])[] | ((.new_string // ""), (.new_str // ""))]
    | map(select(type == "string")) | join("\n")' 2>/dev/null)"
else
  payload="$(INPUT="$input" python3 -c '
import os, json, sys
try:
    d = json.loads(os.environ.get("INPUT","") or "{}")
except Exception:
    print(""); sys.exit(0)
ti = d.get("tool_input", {}) or {}
parts = [ti.get("command",""), ti.get("content",""), ti.get("new_string",""), ti.get("new_str","")]
for e in (ti.get("edits") or []):
    parts.append(e.get("new_string","")); parts.append(e.get("new_str",""))
print("\n".join(p for p in parts if isinstance(p, str)))
')"
fi

# Strip lines that are env-var references (allowed)
scan="$(printf '%s' "$payload" | grep -v -E '\$\{[A-Z0-9_]+\}|os\.environ|getenv\(' || true)"

patterns=(
  'sk-[A-Za-z0-9]{16,}'
  'pplx-[A-Za-z0-9]{16,}'
  '-----BEGIN [A-Z ]*PRIVATE KEY-----'
  'AKIA[0-9A-Z]{16}'
  '(OPENAI_API_KEY|PERPLEXITY_API_KEY|API_KEY|SECRET|TOKEN|PASSWORD)[[:space:]]*[:=][[:space:]]*[A-Za-z0-9/+_-]{16,}'
)
for p in "${patterns[@]}"; do
  if printf '%s' "$scan" | grep -E -q -e "$p"; then
    echo "BLOCKED by secret-scan: literal credential matched /$p/. Use an env var reference (\${VAR}); never commit secrets." >&2
    exit 2
  fi
done
exit 0
