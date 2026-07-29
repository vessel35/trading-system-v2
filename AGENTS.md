# Repository Agent Instructions

## Trading strategy and money-management work

Before designing, implementing, or reviewing any change that touches trading strategy
decisions, strategy metadata or configuration, sizing, leverage, protection prices,
money-management policy selection, strategy runtime composition, or related API, UI,
Evidence, and tests:

1. Read `docs/strategy-authoring-contract.md` completely.
2. Read and follow `.claude/skills/develop-trading-strategies/SKILL.md`.
3. State whether the touched code still uses the legacy `TradingSignal` contract or the
   target `DecisionIntent` and `MoneyManagementPolicy` contract.
4. Keep strategy edge changes separate from money-management and execution refactors
   unless an approved design explicitly requires both.
5. Preserve legacy behavior through the manual compatibility policy before enabling
   Turtle mode or changing any default.

The canonical contract owns the detailed responsibility boundaries, compatibility rules,
Evidence requirements, test matrix, and completion checklist. Do not duplicate or weaken
those rules in local implementation notes.
