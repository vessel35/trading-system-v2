#!/usr/bin/env bash
# PreToolUse on Write|Edit|MultiEdit. Blocks edits to protected zones (config/CI/infra/secrets).
# 'secret|credential' is narrowed to directory and config-file patterns to avoid false
# positives on normal source files like secrets_helper.py or test_credentials.py.
#
# v1.0.2 precision changes:
#   - Env *templates* (.env.example/.sample/.template/.dist) are allowed — they hold no secrets
#     and agents legitimately scaffold them. Real env files (.env, .env.local, .env.test) stay blocked.
#   - Dropped blanket folder blocks on generic `infra/` and `deploy/` (too name-collisiony; editing
#     deploy/run_backtest.py is in-lane). Real infra is still covered by terraform/k8s/helm folders
#     and the .tf/.tfvars/.tfstate extensions, plus the secrets?/credentials? folders.
set -uo pipefail
input="$(cat)"

# JSON extraction via jq (~10ms startup) instead of python3 — a pyenv shim adds ~300ms
# per python3 call, which lands on EVERY Write/Edit. python3 stays as a fallback
# for hosts without jq. PATCH-P003-APPLIED
if command -v jq >/dev/null 2>&1; then
  path="$(printf '%s' "$input" | jq -r '.tool_input.file_path // ""' 2>/dev/null)"
else
  path="$(INPUT="$input" python3 -c '
import os, json, sys
try:
    d = json.loads(os.environ.get("INPUT","") or "{}")
except Exception:
    print(""); sys.exit(0)
print((d.get("tool_input",{}) or {}).get("file_path",""))
')"
fi

[ -z "$path" ] && exit 0

# Allow env *templates* (no secrets by definition).
base="$(basename "$path")"
case "$base" in
  .env.example|.env.sample|.env.template|.env.dist|env.example|env.sample|env.template) exit 0 ;;
esac

protected=(
  '\.env($|\.)'
  '\.mcp\.json$'
  '\.claude/settings\.json$'
  '\.claude/hooks/'
  '(^|/)\.github/'
  '(^|/)(terraform|k8s|helm)/'
  '\.(pem|key|p12|keystore|tfvars|tfstate)$'
  '(^|/)secrets?/'
  '(^|/)credentials?/'
  '(^|/)(secrets?|credentials?)\.(ya?ml|json|env|toml)$'
  '\.codex/config\.toml$'
  '\.claude\.json$'
)
for p in "${protected[@]}"; do
  if printf '%s' "$path" | grep -E -qi -e "$p"; then
    echo "BLOCKED by write-scope: '$path' is a protected zone (/$p/). Outside any agent's lane. Stop and ask the human to make this change." >&2
    exit 2
  fi
done
exit 0
