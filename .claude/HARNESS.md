# Quant Backend Harness — Working Policy

> Imported into the project's CLAUDE.md via `@.claude/HARNESS.md`.
> Read every session. This is the **working brain** for this repository.

You plan, design, implement, and verify **yourself, in this session**. You do not route
implementation to subagents. The only work that leaves this session is **review**, and it
goes to Codex — a different model family, so it fails differently than you do. The one
exception is a strategy authoring round, where writing the strategy is itself what is being
tested (see "Who does what").

**Why direct implementation.** A subagent implements from a written spec and reports back a
summary; you then have to reconstruct what it actually did before you can judge it. Doing
the work here removes that round trip and keeps the person who decided the design
accountable for the code that came out of it.

**`.claude/agents/` still holds six subagent definitions and none of them are used.** They
are kept for history, not as an option. Do not dispatch them, and do not read the split they
describe as current — this document is what is current.

## Who does what (2026-11-20)

Work arrives as GitHub issues in the Project "trading-system-v2 초기 런칭"
(https://github.com/users/vessel35/projects/1). An issue title starts with its place in the
work order, such as `[01]`. The **manager** is the Claude session on M4Pro that assigns issues
through Orca. The **worker** is the Claude session that holds the repository and runs the loop
below (currently orca-m1).

| Stage | Work | Owner | Model |
|---|---|---|---|
| 0. Assign | Pick the next issue by its order, send it as an Orca task, update the issue from the result | manager | Opus 5.5 |
| 1. Start | Create the branch, draft `.claude/OBJECTIVE.md` | worker | Opus 5.5 |
| 1a. Confirm goal | Approve the objective and register `/goal` | **human** | — |
| 2. Design | Write the design document and verify every claim against the repository | worker | Opus 5.5, effort high |
| 3. Design review | Find factual errors, gaps, and untestable claims | **Codex** | `gpt-6.2-sol`, reasoning high |
| 4. Implement | One bounded changeset, exactly as designed | worker | Opus 5.5; Sonnet 5.5 for simple mechanical changesets (see below) |
| 5. QA | pytest, ruff, ruff format, per-service mypy, web test and typecheck | worker | same model as stage 4, or Opus 5.5 once switched |
| 6. Code review | Review the final green diff once | **Codex** | `gpt-6.2-sol`; reasoning xhigh when the diff touches money, quantity, price, fees, or slippage, otherwise high |
| 7. Acceptance test | Break things on purpose and confirm a test catches each one | worker | Opus 5.5, effort high |
| 8. Commit and PR | `git-conventions` and `git-pr`; push goes through the permission prompt | worker; push approval by **human** | same model as stage 4, or Opus 5.5 once switched |
| 9. Merge | Merge the PR and close the issue | **human** decides; manager runs it | — |

**Review sits at two points and Codex holds both.** One before implementation begins, one
after it is green. Implementation and review never sit on the same side — that separation is
the reason the split is shaped this way.

**When Sonnet 5.5 is allowed.** The manager decides, not the worker: an issue may run on
Sonnet 5.5 only when its assignment says so. The manager marks only changesets that need no
design decision, such as copying a record table into a docstring, a dependency version pin,
or a refactor that must keep every existing test result and Evidence golden value unchanged.
The worker switches its own model with `/model`; it does not hand the work to a subagent.

The classification is checked by what the change does, not by which files it edits. Switch
back to Opus 5.5 at whatever stage it happens, implementation, QA, or commit, as soon as any of
these is true: a decision the design did not already make is needed; any test result, numeric
output, or Evidence golden value changes; or the change alters how money, quantity, price,
fees, slippage, or Evidence are computed. After switching, report the switch and its reason in
the worker's result. Every other changeset runs on Opus 5.5 from the start.

**Strategy authoring rounds are the one place subagents work.** A round, such as issue #69,
tests whether the authoring tooling closes on a real document, so the strategy must be written
by an agent the worker does not steer.

- The worker launches a fresh general-purpose agent with the Agent tool on Opus 5.5 and tells
  it to follow the `author-strategy` skill. These are skills, not the retired definitions in
  `.claude/agents/`. The round's rules go in that prompt: no questions, a fixed file scope, no
  git operations, no service restarts, and no screen operations. The agent runs
  `python -m backtest_service.author_check <id>` through all nine stages, including stage 9,
  whose integration tests create and drop a disposable schema, and the repository-root pytest,
  whose fixtures add and remove their own disposable rows. Those test fixtures are its only
  database access. It does not connect to a database otherwise and does not apply the
  registration SQL. Where the skill tells it to restart services or use the screen, it records
  the step as left to the worker.
- The worker never edits the agent's output: the strategy module, its tests, the registration
  SQL, and the document sections the agent writes. A finding against that output is fixed by
  running the agent again, never by the worker.
- After the agent finishes, the worker runs QA, applies the registration SQL to dev
  `signal_db` with the user's approval, restarts the dev servers, and runs the strategy on the
  screen. A second fresh Opus 5.5 agent then follows the `verify-strategy` skill independently.
- One Codex pass at reasoning xhigh reviews the agent's files for two things together:
  faithfulness to the source document, and the stage 6 code review of the strategy, its tests,
  and its registration SQL. It takes the place of stage 6 for those files. Platform changes the
  worker makes during the round still go through stage 6 as usual.

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
   only the check the fix touched. Re-review the whole diff only if a fix changed design-level
   behavior. After a mechanical fix to a Blocking finding, ask Codex only to confirm that the
   named finding is resolved on the new diff; that confirmation completes the zero-Blocking
   verdict the push gate needs. Non-Blocking findings fixed mechanically need no confirmation.
7. **Acceptance test.** **Break things on purpose and confirm a test catches each one.** This
   is not a checklist walk. If a mutation passes, either the test is missing or your mutation
   was invalid — determine which before moving on, and say which it was.
8. **Commit.** Follow `git-conventions` and `git-pr`. Work on a branch, not `main`.

## Reaching Codex

**The Codex model is `gpt-6.2-sol`** (user decision, 2026-11-20). Each machine's
`~/.codex/config.toml` sets it as the first line, `model = "gpt-6.2-sol"`; read the file before a
call and confirm the line is there. Earlier values were `gpt-5.6-terra` (2026-09-24) and
`gpt-6.1-sol` (2026-11-03).

`mcp__codex-cli__codex` and `mcp__codex-cli__review` refuse every model name the MCP
offers by default (`... is not supported when using Codex with a ChatGPT account`). **They work
when `model` is set to `gpt-6.2-sol`** with `reasoningEffort` of `low` or higher (`minimal` is
refused). Plain `codex exec --sandbox read-only "<prompt>"` from Bash also works because it
takes the configured model; this is the path to use where the `codex-cli` MCP is disabled, as
on orca-m1. An MCP response does not report which model ran, so on the MCP route the evidence
is the `model` value you passed; the `codex exec` header check below confirms only the
machine's configured default. Set the stage's reasoning level with `-c model_reasoning_effort=high` or
`-c model_reasoning_effort=xhigh`. The output header prints `model:` and `reasoning effort:`;
confirm both before trusting the review. The Orca worker terminal path (`orca orchestration`:
create a task, dispatch it with `--inject`, wait for `worker_done`) remains the fallback.

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

Some domain skills still name roles from the retired split: `data-agent`,
`validation-auditor`, `execution-realism-auditor`, `backtest-runner`, `review-agent`, an
implementation agent, a design agent. The skills keep those names because they sit inside
methodology text. Read them through the current split.
Data reads, auditing your own work, implementation, and design are the worker session's job;
data reads stay read-only queries run by the worker. Review is Codex's job at stages 3 and 6.
None of these names is a reason to launch a subagent.

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

**Waiting on Codex** depends on the route. A Bash `codex exec` call either finishes in the
foreground or, when run in the background, re-invokes you with a notification when it exits. An
MCP call that runs past 120 seconds moves to the background and its result arrives as a
notification. An Orca worker task is collected with `orca orchestration check --wait`, as above.
Do not poll any of them with sleep loops.

**Waiting on the manager.** A worker does not pick its own next issue. After `worker_done`, it
waits for the next Orca task.

**Waiting on an external condition** — a CI run, a file another process writes, a dev server
coming up — uses `Monitor`, or a backgrounded `until <check>; do sleep 2; done`. That is the
only valid sleep-polling pattern.

## Goal anchoring

- The current sprint goal lives in `.claude/OBJECTIVE.md`. `guardrails.sh` re-injects it
  at SessionStart.
- After editing OBJECTIVE.md, the **human** registers its **Done when:** block as a `/goal` so
  each turn is auto-evaluated. The session drafts the block and asks; it does not proceed
  without a registered goal.
- Done-when criteria must be **transcript-verifiable** (a failing test that passes, a
  zero-Blocking review verdict, an exit-0 lint run — all observable in this transcript), with
  a **turn cap** to prevent runaway loops.

## Hard rules

- **Single source of truth = this session.** Codex reviews; it never co-drives and never
  holds state you rely on. Never sync state two ways with it.
- **Backtest-only scope.** All DB access is READ-ONLY. Strategies run dry-run. No live
  orders / withdrawals / wallet writes in this preset (separate preset if needed). A write
  happens only when the user authorizes that specific write. One standing exception: test
  fixtures that create their own disposable rows or schemas in the development databases and
  remove them afterwards, such as the web-api `disposable_run` fixture in
  `services/web-api/tests/conftest.py` and the integration tests behind `author_check` stage 9,
  are part of QA and need no per-run approval. Anything that leaves data behind is not covered.
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
