# Objective Index — Backtest v2 Design (5 grouped stages: Phase A + B)

> This harness runs as FIVE sequential sessions (Phase A analysis → Phase B detailed design). Pick
> the stage with `DESIGN_STAGE` and `guardrails.sh` injects that stage's full objective (from
> `.claude/objectives/`) at SessionStart. Register that stage's Done-when block as a `/goal`.
>
> ```bash
> DESIGN_STAGE=a-domain claude --model opus   # then a-infra, b-corelib, b-engine-eval, b-adoption
> ```

| Stage | File | dev_plan | Output |
|---|---|---|---|
| a-domain | `objectives/a-domain.md` | A1·A2·A3 | port-source inventory: indicators / strategies / execution·costs·sizing |
| a-infra | `objectives/a-infra.md` | A4·A5·A6 | types·config·DB inventory / collector scope / reconciliation baseline |
| b-corelib | `objectives/b-corelib.md` | B1·B2·B3·B4 | core-lib contracts: topology+ports / types / indicator contracts / config·manager |
| b-engine-eval | `objectives/b-engine-eval.md` | B5·B6·B7 | engine+1m+look-ahead / Evidence+backtest_db fields / metrics+Hard-Gate+Decision |
| b-adoption | `objectives/b-adoption.md` | B8 | core-lib adoption / shim / reconciliation / wallet regression / credential rotation |

## Shared inputs (every stage — set per run; do NOT hardcode absolute paths in committed docs)

- `DESIGN_STAGE` = <a-domain|a-infra|b-corelib|b-engine-eval|b-adoption>  — the active stage
- `TRADING_SYSTEM_DIR` = <fill in>   — trading-system repo root: signal-service + wallet-service (backtest/replay live here but are removal targets, NOT referenced) — READ-ONLY
- `CRYPTO_DATA_HUB_DIR` = <fill in>  — crypto-data-hub repo root: collector service (A5 internalization scope) — READ-ONLY
- `DESIGN_DOC_DIR` = <fill in>       — dir with backtest_v2_architecture.md / _diagrams.md / _dev_plan.md — READ-ONLY canonical input
- `OUTPUT_DIR` = <fill in>           — where this stage writes its notes (the ONLY writable target)
- `OPENAI_API_KEY` = <optional>      — cross-model-reviewer (Codex); b-corelib / b-engine-eval only

## Run order (each stage's notes are the next stage's input)

```
a-domain ──▶ a-infra ──▶ b-corelib ──▶ b-engine-eval ──▶ b-adoption
  (A1-A3)     (A4-A6)     (B1-B4)        (B5-B7)            (B8)
   └──────── Phase A ───────┘  └──────────── Phase B ───────────┘
```

Do not start any b-* stage before both a-* stages are complete (dev_plan §0 stage order A→B→C; §4
"Phase B takes Phase A inventories as input" — 원칙 1 itself gates Phase C, this extends its logic to A→B).

## Invariants that hold across all five stages

- SELF-CONTAINED deliverables (TOP RULE): each design doc is standalone-implementable — a Phase C
  implementer builds from it ALONE, never opening the guideline. Every field/formula/threshold/
  signature/rule is written OUT IN FULL; the guideline is the STANDARD to absorb, not a reference to
  cite. §-citations only in each doc's closing Traceability table, never as a content-substitute.
- Inputs are IMMUTABLE: never Write/Edit under `TRADING_SYSTEM_DIR`, `CRYPTO_DATA_HUB_DIR`, or `DESIGN_DOC_DIR`; notes go under `OUTPUT_DIR`.
- Design NOTES only (contracts / fields / pseudocode) — no product code, no live DB, no executed DDL.
- Preserve every hard invariant (look-ahead, decision_ts<execution_ts, Decimal single-cast gate,
  net-of-cost, 1R≤1%, immutability, deterministic Evidence hash) — the design never re-decides them.
- Finalize the doc's deferred items (backtest_db fields §9.3, SQLite Entity fields §9.6, port list
  §4.3, trailing-parity tolerance) without changing their stated 용도.
- Close each stage on 설계-정합 (spec-consistency-auditor PASS) + 리뷰 게이트 (cto-reviewer APPROVE),
  not on parity — parity is a Phase C (implementation) gate.
- Don't claim you read a file / extracted a contract you didn't actually read (anti-hallucination).
