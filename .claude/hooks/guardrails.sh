#!/usr/bin/env bash
# SessionStart hook. Re-injects the active design-stage objective + hard rules every session. By
# policy this is one of only TWO hooks in this preset, doing exactly the two jobs hooks are allowed
# to do here: (1) keep the agent ON-GOAL (anti-drift), (2) suppress HALLUCINATION ("don't claim you
# read a file / extracted a contract you didn't"). SessionStart runs once per session — no per-tool
# cost. SessionStart cannot block (exit 2 has no effect here) — stderr is the only signal.
set -uo pipefail
root="${CLAUDE_PROJECT_DIR:-.}"
stage="${DESIGN_STAGE:-}"

echo "=== HARNESS GUARDRAILS (Backtest v2 Design — Phase A + B) ==="
echo "- Single driver = this session (Opus). Subagents stay in lane; out-of-lane work -> STOP and escalate."
echo "- This is the DESIGN phase: 8 SEPARATE sessions a-domain -> a-infra -> b-skeleton -> b-components -> b-corelib-classes -> b-service-classes -> b-database -> b-adoption. One stage per session. Phase B builds ONE top-down doc 'backtest_v2_detailed_design.md' section by section (§1 services -> §2 tree -> §3 components -> §4 classes -> §5 DB ERD -> appendix). Do NOT start any b-* stage before both a-* stages are done (dev_plan §0 order A->B->C; §4 'Phase B takes Phase A inventories as input'. 원칙 1 extends this to forbid C before A+B)."
echo "- INPUTS ARE IMMUTABLE: TRADING_SYSTEM_DIR (signal-service + wallet-service; backtest/replay live here but are removal targets, not referenced), CRYPTO_DATA_HUB_DIR (collector), and DESIGN_DOC_DIR (canonical design docs) are READ-ONLY reference — never Write/Edit them. Notes go under OUTPUT_DIR ONLY. (write-scope.sh enforces this.)"
echo "- DESIGN DOCS, NOT CODE: produce full self-contained contracts / fields / formulas / pseudocode in Markdown. No product .py, no live DB connection, no executed DDL."
echo "- SELF-CONTAINED (TOP RULE): each design doc must be implementable ALONE — a Phase C implementer builds from it without ever opening the guideline. Write every field (name/type/constraint/default), every formula (expression/units/edge cases), every threshold (number + where tuned), every port signature, and every touched invariant OUT IN FULL. The guideline (DESIGN_DOC_DIR) is the STANDARD to ABSORB and comply with, NOT a reference the reader consults. NO foreign-document label in the deliverable — not architecture §N/#N, not dev_plan AN/BN/마이그N, not 다이어그램 §N; refer by ACTUAL NAME + the design doc's OWN §1-§5 numbers. The closing Traceability table NAMES each requirement it satisfies (e.g. 'look-ahead prevention'), never labels it. 'finalize the §9.3 fields' or any foreign label in the body is a DEFECT."
echo "- TOP-DOWN, DIAGRAM-DRIVEN STRUCTURE: every design doc leads with 제약사항·방향 (constraints + direction only), then descends service diagram·정의서 -> component diagram·정의서 (per service) -> class diagram·정의서 (per component) -> sequence/flow (inside the class definition). Shared components/classes in their own 공통 section. DB entities as ER diagrams. ALL UML in mermaid (classDiagram/sequenceDiagram/flowchart/erDiagram). Big structure BEFORE detail; the reader never jumps to another doc/chapter. B1 is the entry doc (service diagram + component map + reading map). Full standard: skills/backtest-v2-design/references/design-doc-standard.md."
echo "- PRESERVE THE INVARIANTS — never re-decide them: look-ahead (§11.1); feature_ts <= decision_ts < execution_ts (§7/§11.1); indicator finalization close_time<=T (§3.3); the Decimal single-cast gate at Broker.submit() (§11.2); all P&L net-of-cost (§8); sizing 1R<=1% (§8); Adaptee stateless / config immutable (§4.1#3/#10); deterministic normalized Evidence hash, wall-clock excluded (§11.2); same-touch stop-before-TP (§7); Phase-2/production immutability. If a design seems to require weakening one -> STOP and escalate."
echo "- FINALIZE THE DEFERRED ITEMS, don't re-scope them: backtest_db meta fields (§9.3), SQLite Entity fields (§9.6), the port list (§4.3 table + §4.1#7 'do not pre-fix the list'), the trailing-parity tolerance (§14/diagram 4). For Phase B Entity/port work the rule is 용도 불변, 필드만 확정 — keep each item's stated purpose."
echo "- CLOSE EACH STAGE on 설계-정합 (spec-consistency-auditor PASS) + 리뷰 게이트 (cto-reviewer APPROVE; on b-corelib-classes/b-service-classes/b-database also cross-model-reviewer). NOT on parity — parity is a Phase C (implementation) gate, there is no code here."
echo "- ANTI-HALLUCINATION: if you did not actually read the file / see the symbol / verify the section, do NOT report it as extracted or confirmed. Reference facts come from reference-scout citations (file:symbol), not memory."
echo "- No mid-run questions. If uncertain, prefer the canonical design doc (backtest_v2_architecture.md), else make a conservative assumption, record it + impact, and continue."
echo "- Reports obey Markdown-stability rules: BEGIN_JSON/END_JSON, BEGIN_SQL/END_SQL, BEGIN_PSEUDOCODE/END_PSEUDOCODE markers; no nested triple-backtick fences; long JSON/SQL/pseudocode out of tables."
echo ""

# Warn if the immutability guard is unarmed (write-scope needs these exported to protect inputs).
[ -z "${TRADING_SYSTEM_DIR:-}" ]  && echo "[!] TRADING_SYSTEM_DIR not set — write-scope cannot protect the trading-system repo (signal-service/wallet-service), and reference-scout has no root to read. Export it." >&2
[ -z "${CRYPTO_DATA_HUB_DIR:-}" ] && echo "[!] CRYPTO_DATA_HUB_DIR not set — write-scope cannot protect the crypto-data-hub repo (collector), and A5 has no collector root to read. Export it." >&2
[ -z "${DESIGN_DOC_DIR:-}" ]      && echo "[!] DESIGN_DOC_DIR not set — write-scope cannot protect the canonical design docs, and you have no doc root to cite. Export it." >&2
[ -z "${OUTPUT_DIR:-}" ]          && echo "[!] OUTPUT_DIR not set — the stage has no writable target for its notes. Export it." >&2

# Footgun: if OUTPUT_DIR sits under a protected input dir, write-scope will block EVERY note write.
# Best-effort physical resolve via POSIX `pwd -P` (portable; no GNU `realpath -m`, no python3). Runs
# once at SessionStart, so cost is a non-issue — this just keeps it dependency-clean. OUTPUT_DIR may
# not exist yet, so fall back to resolving its parent + leaf.
_resolve() {
  local p="${1%/}" par leaf
  { cd "$p" 2>/dev/null && pwd -P; } && return 0
  par="${p%/*}"; leaf="${p##*/}"; [ "$par" = "$p" ] && par="."
  if cd "$par" 2>/dev/null; then printf '%s/%s\n' "$(pwd -P)" "$leaf"; else printf '%s\n' "$p"; fi
}
if [ -n "${OUTPUT_DIR:-}" ]; then
  outrp="$(_resolve "$OUTPUT_DIR")"
  for pv in TRADING_SYSTEM_DIR CRYPTO_DATA_HUB_DIR DESIGN_DOC_DIR; do
    pd="${!pv:-}"; [ -z "$pd" ] && continue
    pdrp="$(_resolve "$pd")"; pdrp="${pdrp%/}"
    case "$outrp" in
      "$pdrp"|"$pdrp"/*)
        echo "[!] OUTPUT_DIR ('$OUTPUT_DIR') resolves inside $pv ('$pd') — write-scope will BLOCK every note write there. Point OUTPUT_DIR outside the read-only inputs." >&2 ;;
    esac
  done
fi

obj="$root/.claude/OBJECTIVE.md"
if [ ! -f "$obj" ]; then
  echo "[!] .claude/OBJECTIVE.md MISSING. Create one before dispatching any subagent." >&2
  exit 0
fi
echo "=== OBJECTIVE INDEX (.claude/OBJECTIVE.md) ==="
cat "$obj"

# Inject the ACTIVE stage objective if DESIGN_STAGE is set.
if [ -n "$stage" ]; then
  case "$stage" in
    a-domain)          f="$root/.claude/objectives/a-domain.md" ;;
    a-infra)           f="$root/.claude/objectives/a-infra.md" ;;
    b-skeleton)        f="$root/.claude/objectives/b-skeleton.md" ;;
    b-components)      f="$root/.claude/objectives/b-components.md" ;;
    b-corelib-classes) f="$root/.claude/objectives/b-corelib-classes.md" ;;
    b-service-classes) f="$root/.claude/objectives/b-service-classes.md" ;;
    b-database)        f="$root/.claude/objectives/b-database.md" ;;
    b-adoption)        f="$root/.claude/objectives/b-adoption.md" ;;
    *)                 f="" ; echo "[!] DESIGN_STAGE='$stage' is not one of a-domain/a-infra/b-skeleton/b-components/b-corelib-classes/b-service-classes/b-database/b-adoption." >&2 ;;
  esac
  if [ -n "$f" ] && [ -f "$f" ]; then
    echo ""
    echo "=== ACTIVE STAGE OBJECTIVE ($stage -> $(basename "$f")) ==="
    cat "$f"
    if grep -Eq '<fill[- ]in>|TODO|XXX' "$f"; then
      echo "[!] $(basename "$f") still has placeholder markers ('<fill in>'/'TODO'/'XXX'). Edit it (esp. turn budget) before dispatching." >&2
    fi
  elif [ -n "$f" ]; then
    echo "[!] Stage objective file missing: $f" >&2
  fi
else
  echo ""
  echo "[!] DESIGN_STAGE not set. Export DESIGN_STAGE=a-domain|a-infra|b-skeleton|b-components|b-corelib-classes|b-service-classes|b-database|b-adoption so the active stage objective is injected and /goal can anchor to it." >&2
fi
exit 0
