#!/usr/bin/env bash
# PreToolUse on Write|Edit|MultiEdit. MINIMAL guard — four blocks, by policy:
#   (1) real .env files                  -> secret leakage. Templates (.env.example/.sample/...) allowed.
#   (2) writes under TRADING_SYSTEM_DIR    -> the legacy trading-system repo (signal-service, wallet-service;
#                                            backtest/replay live here too but are removal targets) is
#                                            IMMUTABLE reference (production is touched only in Phase C
#                                            part C7, and never by this harness).
#   (3) writes under CRYPTO_DATA_HUB_DIR   -> the legacy crypto-data-hub repo (collector) is IMMUTABLE reference.
#   (4) writes under DESIGN_DOC_DIR        -> the canonical design docs are IMMUTABLE input.
# Everything else (notably OUTPUT_DIR and the harness's own .claude/) is allowed, to keep latency and
# false-positives low. This hook IS the input-immutability boundary for this preset.
set -uo pipefail
input="$(cat)"

# jq (~10ms) over python3 (a pyenv shim adds ~300ms on EVERY Write/Edit). python3 is the fallback.
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

# (1) .env leakage — allow templates, block real env files.
base="$(basename "$path")"
case "$base" in
  .env.example|.env.sample|.env.template|.env.dist|env.example|env.sample|env.template) exit 0 ;;
esac
if printf '%s' "$path" | grep -E -qi -e '\.env($|\.)'; then
  echo "BLOCKED by write-scope: '$path' is a real .env file (secret leakage). Use a template (.env.example) or ask the human." >&2
  exit 2
fi

# Helper: block if $path is inside directory $1 (literal prefix + realpath-resolved), with label $2.
block_if_under() {
  local dir="$1" label="$2"
  [ -z "$dir" ] && return 0
  dir="${dir%/}"   # strip one trailing slash for clean prefix match
  case "$path" in
    "$dir"|"$dir"/*)
      echo "BLOCKED by write-scope: '$path' is inside $label ('$dir'). It is IMMUTABLE reference in the design phase — write notes under OUTPUT_DIR instead." >&2
      exit 2 ;;
  esac
  # Defense-in-depth ONLY when the literal check above could be evaded — a relative path or one
  # containing '..'. For a clean absolute path the case match is authoritative, so we skip the
  # subshells entirely. This hook runs on EVERY Write/Edit, so the common canonical-absolute case
  # stays fork-free (no dirname/realpath/python3 — all of which would add per-write latency).
  case "$path" in
    *..*) : ;;            # has '..' -> must physically resolve
    /*)   return 0 ;;     # absolute & no '..' -> literal check already decided; skip
  esac
  # Resolve the target's PARENT physically via POSIX `pwd -P` (portable; no GNU `realpath -m`).
  local parent rp rpd
  parent="${path%/*}"; [ "$parent" = "$path" ] && parent="."
  rp="$(cd "$parent" 2>/dev/null && pwd -P)" || rp=""
  rpd="$(cd "$dir" 2>/dev/null && pwd -P)" || rpd=""
  if [ -n "$rp" ] && [ -n "$rpd" ]; then
    case "$rp/" in
      "$rpd"/*)
        echo "BLOCKED by write-scope: '$path' resolves inside $label ('$dir'). It is IMMUTABLE reference in the design phase." >&2
        exit 2 ;;
    esac
  fi
}

# (2)-(4) legacy repos + canonical design docs are immutable inputs.
block_if_under "${TRADING_SYSTEM_DIR:-}"  "TRADING_SYSTEM_DIR (trading-system repo)"
block_if_under "${CRYPTO_DATA_HUB_DIR:-}" "CRYPTO_DATA_HUB_DIR (crypto-data-hub repo)"
block_if_under "${DESIGN_DOC_DIR:-}"      "DESIGN_DOC_DIR (canonical design docs)"

exit 0
