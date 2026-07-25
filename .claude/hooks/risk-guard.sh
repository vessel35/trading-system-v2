#!/usr/bin/env bash
# PreToolUse on Bash and mcp__*__query. Backtest-only scope:
#   (1) MCP query field (sql/query): broad non-SELECT keyword block — that field IS SQL.
#   (2) Bash command: block SQL writes only when there is REAL SQL context:
#         - a DB client is invoked (psql/mysql/sqlite3/...)  -> broad keyword block, OR
#         - genuine DML/DDL *syntax* is present (DELETE FROM, UPDATE ... SET=, DROP TABLE ...).
#       Bare keywords alone (git MERGE, rg UPDATE, stash DROP, "update" in a commit msg,
#       pytest -k delete) DO NOT trigger — they are not SQL.
#   (3) Bash writes into protected zones (.env / .mcp.json / settings / hooks / .github / *.pem).
# Live-execution / exchange-SDK / fund-movement patterns are intentionally OUT
# (no live trading in this preset; add a separate preset if needed).
set -uo pipefail
input="$(cat)"

# JSON extraction via jq (~10ms startup) instead of python3 — a pyenv shim adds ~300ms
# per python3 call, and this script needed TWO of them on EVERY Bash command.
# python3 stays as a fallback for hosts without jq. PATCH-P003-APPLIED
if command -v jq >/dev/null 2>&1; then
  cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // ""' 2>/dev/null)"
  sql="$(printf '%s' "$input" | jq -r '
    .tool_input // {} | (.sql // "") as $s |
    if $s != "" then $s else (.query // "") end' 2>/dev/null)"
else
  cmd="$(INPUT="$input" python3 -c '
import os, json, sys
try: d = json.loads(os.environ.get("INPUT","") or "{}")
except Exception: print(""); sys.exit(0)
print((d.get("tool_input",{}) or {}).get("command",""))
')"
  sql="$(INPUT="$input" python3 -c '
import os, json, sys
try: d = json.loads(os.environ.get("INPUT","") or "{}")
except Exception: print(""); sys.exit(0)
ti = d.get("tool_input",{}) or {}
print(ti.get("sql","") or ti.get("query",""))
')"
fi

block(){ echo "BLOCKED by risk-guard: $1 Stop and escalate to the human in chat." >&2; exit 2; }

# Broad keyword set — used ONLY where the input is genuinely SQL:
#   the MCP query field, or a bash command that invokes a DB client.
sql_keywords=(
  '\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|GRANT|MERGE|UPSERT)\b'
  '\bCOPY[[:space:]]+[^[:space:]]+[[:space:]]+FROM\b'
  '\bWITH\b.*\b(INSERT|UPDATE|DELETE)\b'
)

# Syntax-anchored DML/DDL — used for generic bash commands. These require SQL grammar
# around the keyword, so ordinary shell commands that merely contain the word do not match.
dml_syntax=(
  '\bDELETE[[:space:]]+FROM\b'
  '\bINSERT[[:space:]]+INTO\b'
  '\bUPDATE\b[^;|]+\bSET\b[^;|]*='
  '\bDROP[[:space:]]+(TABLE|DATABASE|INDEX|VIEW|SCHEMA|SEQUENCE|MATERIALIZED|ROLE|USER)\b'
  '\bALTER[[:space:]]+(TABLE|DATABASE|INDEX|VIEW|SCHEMA|SEQUENCE|TYPE|ROLE|USER)\b'
  '\bTRUNCATE[[:space:]]+(TABLE|ONLY)\b'
  '\bGRANT\b[^;|]*[[:space:]]+ON\b'
  '\bMERGE[[:space:]]+INTO\b'
  '\bUPSERT[[:space:]]+INTO\b'
  '\bCOPY[[:space:]]+[^[:space:]]+[[:space:]]+FROM\b'
  '\bWITH\b.*\b(INSERT|UPDATE|DELETE)\b.*\b(INTO|SET|FROM)\b'
)

# SQL client invocations (whole-word). If present in a bash command, treat the command as SQL.
db_client='\b(psql|mysql|mariadb|sqlite3|clickhouse-client|clickhouse|duckdb|cockroach|pgcli|mycli|usql|pg_dump|pg_restore)\b'

# (1) MCP query field — always broad (this field is SQL by definition).
if [ -n "$sql" ]; then
  for p in "${sql_keywords[@]}"; do
    printf '%s' "$sql" | grep -E -qi -e "$p" && block "non-SELECT SQL (/$p/) - databases are READ-ONLY."
  done
fi

# (2) Bash command.
if [ -n "$cmd" ]; then
  if printf '%s' "$cmd" | grep -E -qi -e "$db_client"; then
    # A DB client is being invoked from the shell — apply the broad keyword set.
    for p in "${sql_keywords[@]}"; do
      printf '%s' "$cmd" | grep -E -qi -e "$p" && block "non-SELECT SQL via DB client (/$p/) - databases are READ-ONLY."
    done
  else
    # Generic shell command — only genuine DML/DDL *syntax* triggers (no bare-keyword false positives).
    for p in "${dml_syntax[@]}"; do
      printf '%s' "$cmd" | grep -E -qi -e "$p" && block "non-SELECT SQL syntax (/$p/) - databases are READ-ONLY."
    done
  fi

  # Bash writes to protected zones (redirect / tee / sed -i / cp / mv / rm).
  prot='\.env([^A-Za-z0-9]|$)|\.mcp\.json|\.claude/settings\.json|\.claude/hooks/|/\.github/|\.codex/config\.toml|\.claude\.json|\.(pem|key|p12|keystore)([^A-Za-z0-9]|$)'
  writeop='>>?[[:space:]]|[[:space:]]tee[[:space:]]|sed[[:space:]]+-i|dd[[:space:]]+of=|[[:space:]]rm[[:space:]]|[[:space:]]mv[[:space:]]|[[:space:]]cp[[:space:]]'
  if printf '%s' "$cmd" | grep -E -q -e "$prot" && printf '%s' "$cmd" | grep -E -q -e "$writeop"; then
    block "bash write to a protected zone (config/CI/infra/secrets)."
  fi
fi
exit 0
