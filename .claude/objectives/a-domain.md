# Stage a-domain Objective — Port-Source Inventory: domain logic (read-only)

> Set `DESIGN_STAGE=a-domain`. Register the Done-when block below as a `/goal`.

**Goal:** Inventory the PURE domain logic that will be ported into `core_lib` — indicators (A1),
strategy `analyze` judgment (A2), and execution/costs/sizing/trailing (A3) — from the legacy repos.
Separate what to PORT from what to DROP (reference-frozen) and what is a GAP (new). Output is the
port-source map + gap list, not code and not design.

**Inputs:** architecture §3.2·§3.3·§4.1#3-6·§5.8·§6·§7·§8; dev_plan A1·A2·A3 + 이식 원천 맵;
legacy (READ-ONLY, under `TRADING_SYSTEM_DIR`): `services/signal-service/domain/indicators/{technical.py,
extended.py}`, `services/signal-service/domain/strategies/`,
`application/scheduler/strategy_executor.py`, `application/services/strategy_service.py`,
`services/wallet-service/domain/services/{futures_calculator.py, slippage_calculator.py}`,
`application/services/{trailing_stop_update_service.py, slippage_validator.py}`, paper fill-decision
logic. (backtest/replay under `TRADING_SYSTEM_DIR` are removal targets — do NOT read them.) Dispatch
`reference-scout` to extract the actual contracts (it resolves the repo's exact layout).

**In scope:**
- **A1 indicators:** list the signal-service implemented indicators → tabulate the 82-target gap
  (`§12` pinned, `§7` breadth, `§8` Ehlers, Donchian, `adx_14`, weekly ATR) → identify the ~10-15
  commercial indicators the Vessel line actually references. (No backtest-copy drift compare — the
  old backtest is a removal target, not referenced.) Deliver `A1_indicator_inventory.md`
  (implemented / gap / commercial).
- **A2 strategies:** describe `AbstractStrategy`·Registry·Factory·inheritance chain (NOT ported —
  redesigned) → per Vessel strategy, the pure `analyze` contract (input / output / depended
  indicators) as the Adaptee port scope → collect `required_indicators`·timeframe·profile
  declarations → relation to wallet trailing. Deliver `A2_strategy_inventory.md` (per-strategy
  analyze contract + depended indicators).
- **A3 execution/costs/sizing:** the fill-decision logic, cost formulas, sizing, sub-candle trailing
  → their port scope + contract into `core_lib.execution`/`costs`/`sizing`/`strategy.trailing` →
  confirm current `fill_timing` (immediate) → scan the wallet regression (1175) blast radius for the
  C7a adoption. Deliver `A3_execution_cost_sizing_inventory.md` (port-source map).

**Out of scope (escalate / do NOT do):**
- Writing any design contract (that is Phase B) or any code; modifying any legacy file.
- Deciding the 82-indicator final list or port signatures (B3); deciding the Adaptee Protocol (B4).

**Done when:**
- `A1_indicator_inventory.md`, `A2_strategy_inventory.md`, `A3_execution_cost_sizing_inventory.md`
  exist under `OUTPUT_DIR`, each with the port / gap classification.
- Each inventory is SELF-CONTAINED: it states the actual extracted contract (the real signature,
  indicator list, formula, or field) inline with its `file:symbol` provenance — not a bare pointer —
  so the Phase B stages design from the inventory itself without re-reading the legacy code.
- `reference-scout` extractions are cited (file:symbol), not guessed.
- `spec-consistency-auditor` returned PASS (inventory matches "구현은 전부·계산은 설정" §5.8,
  Adaptee=판단 전용 §4.1#3, 동작 보존 마이그5) in this transcript.
- `cto-reviewer` returned APPROVE on inventory completeness + separation (port vs drop vs gap).
- Complete enough that b-components / b-corelib-classes (indicators B6, strategy/config B7) and
  b-service-classes (Engine/execution B9 from A3) design from the inventory without re-inventorying.
- Turn budget: ≤ <fill in> orchestrator turns. If exceeded → STOP and escalate.

**Register with /goal (example):**

Stage a-domain is complete only when the three inventory notes (A1 indicators, A2 strategies, A3
execution/costs/sizing) exist under OUTPUT_DIR with port/drop/gap classification cited to
file:symbol, spec-consistency-auditor returned PASS and cto-reviewer returned APPROVE in this
transcript, and no legacy file was modified. Until then, continue the named gaps. Do not declare
completion from a feeling of "enough".
