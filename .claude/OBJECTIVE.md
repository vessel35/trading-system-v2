# Objective Index — Backtest v2 Design (8 grouped stages: Phase A + B)

> This harness runs as EIGHT sequential sessions (Phase A analysis → Phase B top-down detailed
> design). Pick the stage with `DESIGN_STAGE` and `guardrails.sh` injects that stage's full objective
> (from `.claude/objectives/`) at SessionStart. Register that stage's Done-when block as a `/goal`.
> Phase B builds ONE document `backtest_v2_detailed_design.md` section by section.
>
> ```bash
> DESIGN_STAGE=a-domain claude --model opus   # then a-infra, b-skeleton, b-components, ... b-adoption
> ```

| Stage | File | dev_plan | 설계서 절 | Output |
|---|---|---|---|---|
| a-domain | `objectives/a-domain.md` | A1·A2·A3 | — | inventory: indicators / strategies / execution·costs·sizing |
| a-infra | `objectives/a-infra.md` | A4·A5·A6 | — | inventory: types·config·DB-creation / collector scope / removal + reconciliation-waiver |
| b-skeleton | `objectives/b-skeleton.md` | B1·B2 | §1·§2 | service diagram + code tree (creates the design doc + reading map) |
| b-components | `objectives/b-components.md` | B3·B4·B5 | §3.1-§3.3 | component diagrams: core-lib / backtest-service / adoption |
| b-corelib-classes | `objectives/b-corelib-classes.md` | B6·B7·B8 | §4.1-§4.3 | core-lib classes: types·indicators / strategy+config / execution·eval (+ config/judgment flow) |
| b-service-classes | `objectives/b-service-classes.md` | B9·B10 | §4.4-§4.5 | backtest-service classes: Engine + output (+ candle-loop/1m/run-save sequence) |
| b-database | `objectives/b-database.md` | B11·B12·B13 | §5.1-§5.3 | DB ER diagrams: crypto_data/signal_db / backtest_db / Evidence SQLite (deferred fields) |
| b-adoption | `objectives/b-adoption.md` | B14 | appendix | adoption + shim / regression / credential rotation (reconciliation WAIVED) |

## Shared inputs (every stage — set per run; do NOT hardcode absolute paths in committed docs)

- `DESIGN_STAGE` = <a-domain|a-infra|b-skeleton|b-components|b-corelib-classes|b-service-classes|b-database|b-adoption>  — the active stage
- `TRADING_SYSTEM_DIR` = <fill in>   — trading-system repo root: signal-service + wallet-service (backtest/replay live here but are removal targets, NOT referenced) — READ-ONLY
- `CRYPTO_DATA_HUB_DIR` = <fill in>  — crypto-data-hub repo root: collector service (A5 internalization scope) — READ-ONLY
- `DESIGN_DOC_DIR` = <fill in>       — dir with backtest_v2_architecture.md / _diagrams.md / _dev_plan.md — READ-ONLY canonical input
- `OUTPUT_DIR` = <fill in>           — where the design doc / inventories are written (the ONLY writable target)
- `OPENAI_API_KEY` = <optional>      — cross-model-reviewer (Codex); b-corelib-classes / b-service-classes / b-database only

## Run order (Phase A feeds Phase B; Phase B builds ONE doc top-down, §1 → §5 → appendix)

```
a-domain ─▶ a-infra ─▶ b-skeleton ─▶ b-components ─▶ b-corelib-classes ─▶ b-service-classes ─▶ b-database ─▶ b-adoption
 (A1-A3)   (A4-A6)     (§1·§2)        (§3.1-3.3)      (§4.1-4.3)            (§4.4-4.5)             (§5.1-5.3)     (appendix)
  └──── Phase A ────┘  └───────────────────────────── Phase B: backtest_v2_detailed_design.md ─────────────────────────┘
```

Do not start any b-* stage before both a-* stages are complete (dev_plan §0 stage order A→B→C; §4
"Phase B takes Phase A inventories as input" — 원칙 1 itself gates Phase C, this extends its logic to A→B).

## Invariants that hold across all eight stages

- SELF-CONTAINED deliverables (TOP RULE): each design doc is standalone-implementable — a Phase C
  implementer builds from it ALONE, never opening the guideline. Every field/formula/threshold/
  signature/rule is written OUT IN FULL; the guideline is the STANDARD to absorb, not a reference to
  cite. NO foreign-document label in the deliverable (architecture §N / dev_plan AN·BN·마이그N /
  diagrams §N) — actual names + the design doc's own §1-§5; the closing Traceability table NAMES each
  requirement it satisfies, never labels it.
- TOP-DOWN UML-FIRST structure: every design doc leads with 제약사항·방향, then descends
  service→component→class→sequence/flow (one component diagram per service, one class diagram per
  component; shared elements separated); DB entities as ER diagrams; ALL UML in mermaid. UML-first —
  the diagram is the primary representation: attributes+types, signatures, relationships+cardinality,
  ER fields+keys, and flow order go INSIDE the diagram; prose supplies ONLY what UML cannot encode
  (constraints, defaults, formulas, thresholds, enforced invariants, semantics, responsibility,
  rationale). Never restate the diagram in prose; never hide structure in prose. Big structure before
  detail; the reader never jumps to another doc/chapter. B1 is the entry doc.
- Inputs are IMMUTABLE: never Write/Edit under `TRADING_SYSTEM_DIR`, `CRYPTO_DATA_HUB_DIR`, or `DESIGN_DOC_DIR`; notes go under `OUTPUT_DIR`.
- Design NOTES only (contracts / fields / pseudocode) — no product code, no live DB, no executed DDL.
- Preserve every hard invariant (look-ahead, decision_ts<execution_ts, Decimal single-cast gate,
  net-of-cost, 1R≤1%, immutability, deterministic Evidence hash) — the design never re-decides them.
- Finalize the doc's deferred items (backtest_db fields §9.3, SQLite Entity fields §9.6, port list
  §4.3, trailing-parity tolerance) without changing their stated 용도.
- Close each stage on 설계-정합 (spec-consistency-auditor PASS) + 리뷰 게이트 (cto-reviewer APPROVE),
  not on parity — parity is a Phase C (implementation) gate.
- Don't claim you read a file / extracted a contract you didn't actually read (anti-hallucination).
