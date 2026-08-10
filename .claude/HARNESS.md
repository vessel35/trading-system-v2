# Quant Backend Harness — Working Policy

> Imported into the project's CLAUDE.md via `@.claude/HARNESS.md`.
> Read every session. This is the **working brain** for this repository.

You plan, design, implement, and verify **yourself, in this session**. You do not route
implementation to subagents. The only work that leaves this session is **review**, and it
goes to Codex — a different model family, so it fails differently than you do.

**Why direct implementation.** A subagent implements from a written spec and reports back a
summary; you then have to reconstruct what it actually did before you can judge it. Doing
the work here removes that round trip and keeps the person who decided the design
accountable for the code that came out of it.

**`.claude/agents/` still holds six subagent definitions and none of them are used.** They
are kept for history, not as an option. Do not dispatch them, and do not read the split they
describe as current — this document is what is current.

## Who does what (2026-08-10)

| Work | Owner |
|---|---|
| Planning, design | you |
| **Design review, before implementation starts** | **Codex** |
| Implementation | you |
| Self-review, QA (tests, ruff, format, mypy) | you |
| **Code review, after QA passes** | **Codex** |
| Acceptance testing | you |

**Review sits at two points and Codex holds both.** One before implementation begins, one
after it is green. Implementation and review never sit on the same side — that separation is
the reason the split is shaped this way.

## The loop

1. **Design.** Write the design document. State what is wrong now, what you verified, what
   changes, what you will not do, and what has to be true to call it closed. Verify every
   factual claim against the repository before you write it down.
2. **Design review — Codex.** Ask it adversarially: which of these claims does the repository
   contradict, what is missing, what cannot be tested. **A factual error in the design is the
   most valuable finding**, so ask for it by name.
3. **Reconcile.** Check each finding against the code yourself before accepting it. Fix the
   design. Say plainly which findings were yours to own.
4. **Implement.** One bounded changeset per concern — a reviewable diff, no mixed refactor
   and feature. Implement exactly what the approved design says.
5. **QA.** Repository-root `.venv/bin/python -m pytest services -q`, `ruff check`,
   `ruff format --check`, and **mypy from inside each changed service directory** (mypy is
   configured per service; running it from the root is wrong). Web changes also run
   `npm test` and `npm run typecheck` in `apps/web`. Make it green before review.
6. **Code review — Codex.** Once, on the final green diff. Address Blocking findings; re-run
   only the check the fix touched. Re-review only if a fix changed design-level behavior,
   never for mechanical fixes.
7. **Acceptance test.** **Break things on purpose and confirm a test catches each one.** This
   is not a checklist walk. If a mutation passes, either the test is missing or your mutation
   was invalid — determine which before moving on, and say which it was.
8. **Commit.** Follow `git-conventions` and `git-pr`. Work on a branch, not `main`.

## Reaching Codex

`mcp__codex-cli__codex` is refused by this account for every model it offers
(`... is not supported when using Codex with a ChatGPT account`). **The working path is an
Orca worker terminal** running Codex, driven through `orca orchestration`: create a task,
dispatch it with `--inject`, then wait for `worker_done`.

Two failure modes recur and both are silent:

- **The prompt lands in the composer but is never submitted.** `input_accepted` does not mean
  it started. Read the terminal; if nothing is running, set the task back to `ready` and
  dispatch again.
- **`check --wait` returns immediately and empty** when a waiter already exists on the run,
  or when an earlier delivery was never acknowledged. Acknowledge the delivery, then wait
  again.

Never claim a review happened without the returned findings in hand.

## Skills

Skills load into this session by description and by `paths:` glob. `genius-thinking` for
problem reframing and design evaluation, `develop-trading-strategies` for the strategy and
money-management contracts, `quant-backtest` for engine work, `statistical-validation` for
evidence claims, `decimal-arithmetic-discipline` for anything touching money, position size,
price, fees, or slippage, `execution-modeling` for fills and costs, `risk-and-hedging`,
`crypto-derivatives`, `ml-strategy`, `behavioral-finance`, `clean-code`, `python`,
`backend-principles`, and `git-conventions` / `git-pr` for branch, commit, and push.

## Context discipline

- Use `/compact` (NOT `/clear`) to shed tokens while keeping working state.
- `/clear` or a fresh session **only** for genuinely unrelated work.
- Use `/context` to inspect token usage when deciding whether to act.
- **Review economy**: one review pass per artifact, at the right stage. Cheap checks — tests,
  lint, types — always run before the expensive cross-model review. Never re-verify what a
  hook or an earlier step already verified.

## Documentation & report style (every document, report, and summary)

- Write complete sentences. Never compress findings into arrow chains (`A → B → C`),
  slash strings, or symbol shorthand — state the relationship in prose.
- Do not coin internal abbreviations. Expand every abbreviation at first use; after that
  the short form is fine. Widely established terms (API, PR, CI, SQL) need no expansion.
- Use plain language with exact terminology: pick the simplest wording that is still
  technically precise, and never trade correctness for simplicity.
- Do not force literal translations. In Korean output keep established technical terms in
  their original form (slippage, walk-forward, funding rate); never translate quoted logs,
  error messages, or code identifiers.
- Cite files with the filename included, never a bare `NN:NN`.

## Waiting on things

**Waiting on Codex** goes through `orca orchestration check --wait`, as above.

**Waiting on an external condition** — a CI run, a file another process writes, a dev server
coming up — uses `Monitor`, or a backgrounded `until <check>; do sleep 2; done`. That is the
only valid sleep-polling pattern.

## Goal anchoring

- The current sprint goal lives in `.claude/OBJECTIVE.md`. `guardrails.sh` re-injects it
  at SessionStart.
- After editing OBJECTIVE.md, register its **Done when:** block as a `/goal` so each turn is
  auto-evaluated. Don't proceed without a registered goal.
- Done-when criteria must be **transcript-verifiable** (a failing test that passes, a
  zero-Blocking review verdict, an exit-0 lint run — all observable in this transcript), with
  a **turn cap** to prevent runaway loops.

## Hard rules

- **Single source of truth = this session.** Codex reviews; it never co-drives and never
  holds state you rely on. Never sync state two ways with it.
- **Backtest-only scope.** All DB access is READ-ONLY. Strategies run dry-run. No live
  orders / withdrawals / wallet writes in this preset (separate preset if needed). A write
  happens only when the user authorizes that specific write.
- **Secrets** never get written to files or committed. `${ENV_VAR}` references only.
- **Bounded changesets.** No mixed refactor + feature commits.
- **Push gate.** `git push` is permitted only after the code review returns zero Blocking
  findings and QA is green. Every push still goes through the permission prompt
  (`permissions.ask`) — that prompt is the human checkpoint, and a denied prompt is a final
  answer, not something to retry or work around.
- **Hooks** run automatically — never bypass them. Three are registered: `guardrails.sh`
  (re-injects the objective at SessionStart), `secret-scan.sh`, and `test-gate.sh`.
  `risk-guard.sh` and `write-scope.sh` still exist as files but were deliberately
  unregistered on 2026-07-24; do not re-register them.

## When you are the one who was wrong

Design review and code review exist to catch your errors, and they do. When a finding lands:
check it against the code yourself, then say plainly that the claim was yours and what the
correct fact is. Fix the design document too — **an error left in the document gets built
from later.**
