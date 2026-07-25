---
name: git-pr
description: >
  Use when committing, branching, or preparing a pull request for the quant backend.
  Covers commit message style, branch naming, and the push gate: review passes first,
  then push through the permission prompt (which is the human checkpoint).
---

# Git & PR conventions (preset-private)

## Hard rule
- `git push` is allowed once the push gate below passes. Every push goes through the
  permission prompt (`settings.json` lists `Bash(git push:*)` under `permissions.ask`) —
  an approved prompt IS the human confirmation; a denied prompt is a final answer.
  Never retry a denied push or route around the prompt.
- Never commit secrets. `${ENV_VAR}` references only (secret-scan backstops this).
- Commits stay as bounded changesets (one concern). No mixed refactor + feature commits.

## Branches
- `fix/<short-desc>`, `feat/<short-desc>`, `chore/<short-desc>`. Include an issue id if one exists.

## Commit messages (Conventional Commits)
- `fix(strategy): correct re-entry cooldown off-by-one`
- `feat(backtest): add slippage model`
- `test(signal): cover stale-indicator guard`
- Body: what changed and why. Reference the design doc / OBJECTIVE.md when relevant.

## Push gate (in this order — QA first, review once on the final diff)
1. Tests pass (test-gate will block stop otherwise).
2. mech-agent ruff + mypy exit 0.
3. review-agent (Codex/GPT-5.5, reasoning_effort xhigh) reviewed the final, test-passing
   diff; zero Blocking findings. One review pass — no re-review for mechanical fixes.
4. No secrets in the diff (secret-scan backstops this).
5. Then push — the permission prompt that follows is the human confirmation.

## Relationship to myclaude/skills/git-conventions
- `git-conventions` (cross-cutting myclaude skill) covers global conventions.
- This `git-pr` (preset-private) adds the human-checkpoint rule and review-agent dependency
  specific to the quant-backend harness.
