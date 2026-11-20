# Quant Backend Harness — Working Policy

> Imported into the project's CLAUDE.md via `@.claude/HARNESS.md`.
> Read every session. This is the **working brain** for this repository.

You run the loop below **from this session**, which stays on Sonnet 5.5 and owns the issue
from start to merge request. Stages that need a different model run in **stage agents**: fresh
agents you launch with the Agent tool, each with the model and effort the stage table sets.
Review goes to Codex — a different model family, so it fails differently than either.

**Why stage agents, and how they stay honest.** A session cannot change its own model, and the
table puts design and acceptance testing on Opus 5.5 and QA on Haiku 5.5. The old
objection to subagents was that one implements from a written spec and returns a summary you
must reconstruct. Two rules close that gap. First, every hand-off between stages is a file
the next stage and the review read directly: in the repository, the UML design document, the
diff on the branch, and the acceptance test record; in the session's scratch directory, the QA
log. A stage agent's summary is never the evidence. Second, this session reads those files before it moves the issue to the next
stage, and Codex and the human checkpoints sit where they did before.

**`.claude/agents/` still holds six subagent definitions and none of them are used.** They
are kept for history, not as an option. Do not dispatch them, and do not read the split they
describe as current — this document is what is current.

## Who does what (2026-11-20)

Work arrives as GitHub issues in the Project "trading-system-v2 초기 런칭"
(https://github.com/users/vessel35/projects/1). An issue title starts with its place in the
work order, such as `[01]`. The **manager** is the Claude session on M4Pro that assigns issues
through Orca. The **worker** is the Claude session that holds the repository and runs the loop
below (currently orca-m1).

A **money-path change** is one that can change which orders are placed, filled, sized,
priced, or charged, or what Evidence records, whether directly (a formula) or indirectly (a
default value, the order of engine events, when an entry is rejected). Code under the engine,
execution, money-management, or Evidence modules counts even when the change is meant to keep
behavior identical, because only the tests can show that it did. When in doubt, treat the
change as money-path. The worker session classifies the change at stage 1 and records the
classification in `.claude/OBJECTIVE.md`; the design agent is launched at the effort that
classification sets. If a design agent launched at high finds the change is money-path, it
stops and reports, and the worker relaunches design at xhigh. Money-path overrides a
manager's mechanical mark. Several rows below
depend on this classification, and `.claude/skills/git-pr/SKILL.md` uses the same one.

| Stage | Work | Runs in | Model | Effort |
|---|---|---|---|---|
| 0. Assign | Pick the next issue by its order, send it as an Orca task, update the issue from the result | manager session | Sonnet 5.5 | medium |
| 1. Start | Create the branch, draft `.claude/OBJECTIVE.md` | worker session | Sonnet 5.5 | medium |
| 1a. Confirm goal | Approve the objective and register `/goal` | **human** | — | — |
| 2. Design | Write the design in UML and verify every claim against the repository | stage agent | **Opus 5.5** | high; xhigh for a money-path change |
| 3. Design review | Find factual errors, gaps, and untestable claims | **Codex** | `gpt-6.2-sol` | high; xhigh for a money-path change |
| 4. Implement | One bounded changeset, exactly as designed | worker session on Sonnet 5.5; a stage agent for Opus 5.5 or Haiku 5.5 | Sonnet 5.5; **Opus 5.5** for a money-path change; Haiku 5.5 for a mechanical changeset the manager marks | high; medium for a mechanical changeset |
| 5. QA | pytest, ruff, ruff format, per-service mypy, web test and typecheck; write the output to a file | stage agent | Haiku 5.5; fixing a failure goes back to the stage 4 model | low |
| 6. Code review | Review the final green diff once | **Codex** | `gpt-6.2-sol` | high; xhigh for a money-path change |
| 7. Acceptance test | Break things on purpose, confirm a test catches each one, revert every mutation, write the record | stage agent | **Opus 5.5** | high |
| 8. Commit and PR | Commit the acceptance record, push, open the PR by `git-conventions` and `git-pr`; the push permission prompt is the **human** approval | worker session | Sonnet 5.5 | low |
| 9. Merge | Merge the PR and close the issue | **human** decides; manager session runs it | Sonnet 5.5 | low |

Opus 5.5 is kept for the stages whose mistakes are hardest to undo: design, acceptance
testing, and implementing a money-path change.

**Running a stage agent.**

- Launch it with the Agent tool, a general-purpose agent, passing `model` (`opus`, `sonnet`,
  or `haiku`) and `effort` exactly as the table sets. This file is the instruction that
  authorizes setting effort. Never use the retired definitions in `.claude/agents/`.
- One stage agent at a time on a branch. Agents may run in the background and report by
  notification; the worker launches the next agent, or touches the working tree itself, only
  after the previous agent's completion notification has arrived. If an agent hangs, stop it
  and confirm it has stopped before retrying. A stage agent never launches agents of its own.
- The prompt names the issue, the branch, the files to read (the design document, the
  objective, the previous stage's output file), the one stage to perform, and the file to write
  its result to. The QA commands the stage 5 agent runs are pre-approved in
  `.claude/settings.json` (`.venv/bin/python -m pytest`, `.venv/bin/ruff`, `.venv/bin/mypy` and
  `../../.venv/bin/mypy` from a service directory, `npm test`, `npm run typecheck`); if one
  still needs approval, the agent reports it and the worker runs that command itself. The prompt
  forbids `git add`, `git commit`, `git push`, merging, opening a PR,
  database writes beyond the test-fixture exception, and work outside the stage. A stage
  agent that needs a permission it was not given reports a blocker instead of asking. Only the
  worker session commits and pushes; the human denies any `git push` prompt that does not come
  from the worker session at stage 8.
- Stage agents write their output under `docs/` for design documents and acceptance records,
  and under the session's scratch directory for QA logs. This session reads the output file
  itself before the next stage; the agent's closing summary is not evidence.
- Codex verdicts are recorded where the next reader looks: the design review's findings and
  their reconciliation as a section at the end of the design document, the code review's
  verdict in the PR body. Applying accepted design-review findings to the diagrams and the test
  plan table is a design task, done by a design stage agent at the design effort.
- Commits stay in the worker session; stage agents never run `git add` or `git commit`, which
  the project's permissions do not pre-approve. After stage 6, before launching stage 7, the
  worker commits the reviewed diff locally (no push). That commit is the snapshot the
  acceptance test is measured against. The worker also saves the output of
  `git status --porcelain --untracked-files=all` at that moment as the baseline, because files that were already
  untracked (a local backup, for instance) are not mutations.
- After stage 7, `git status --porcelain --untracked-files=all` must match the baseline except for the acceptance
  record; it shows untracked files as well as changes, which `git diff HEAD` alone would miss. The acceptance
  agent reverts its own mutations; any entry that is neither in the baseline nor the
  acceptance record, for instance after an interruption, is a leftover mutation. The worker
  moves only those entries aside with
  `git --literal-pathspecs stash push --include-untracked -- <files>`, naming each file, so a
  name containing `*` or `?` cannot match a baseline file. It checks the stash holds only
  mutations, and drops it. Baseline entries are never stashed. This command is not
  pre-approved, so it goes through a permission prompt in the worker session. (`git checkout -- <file>` and `git reset --hard` are denied in this project.) If
  stage 7 finds a missing test, adding it is a code change: back to stage 4, then QA, then a
  Codex confirmation limited to the added test, committed locally before stage 8.
- If a stage agent stops, reports a blocker, or its output contradicts the design, this
  session does not patch around it. It reruns the stage, escalates the model by the rule below,
  or returns to stage 2.

The worker and manager sessions start on Sonnet 5.5, the project default in
`.claude/settings.json`. The human starts them; neither session changes its own model.

**Review sits at two points and Codex holds both.** One before implementation begins, one
after it is green. Implementation and review never sit on the same side — that separation is
the reason the split is shaped this way.

**Mechanical changesets.** The manager decides, not the worker: an issue runs stage 4 on
Haiku 5.5 only when its assignment marks it mechanical. The manager marks only changesets that
need no design decision, such as copying a record table into a docstring, a dependency version
pin, or a refactor that must keep every existing test result and Evidence golden value
unchanged.

**Escalation and reclassification are different.**

- *Escalate one level* (Haiku 5.5 to Sonnet 5.5, Sonnet 5.5 to Opus 5.5) when a result differs
  from what was expected, or a test result, numeric output, or Evidence golden value changes in
  a change that was not meant to change it.
- *Reclassify* when the change turns out to be a money-path change, or needs a decision the
  design did not make. Go straight to Opus 5.5 at the effort the table sets for a money-path
  change, return to stage 2 to add the decision to the design, and take it through stage 3
  again before continuing.
- Either way the higher model stays for the rest of the issue in the stages that make
  decisions (2, 4, and 7, and any QA fix, which goes back to the stage 4 model then in effect).
  QA itself keeps running on Haiku 5.5, because it only runs commands. If the
  stage that hits the trigger is already on Opus 5.5, it stops and the worker returns to
  stage 2. Report each switch and its reason in the worker's result.

**Strategy authoring rounds use their own agents.** These are not stage agents. A round, such as issue #69,
tests whether the authoring tooling closes on a real document, so the strategy must be written
by an agent the worker does not steer.

- The worker launches a fresh general-purpose agent with the Agent tool on Opus 5.5, effort
  high, and tells
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
  screen. A second fresh agent, on Sonnet 5.5 at effort xhigh, then follows the
  `verify-strategy` skill independently.
- One Codex pass at reasoning xhigh reviews the agent's files for two things together:
  faithfulness to the source document, and the stage 6 code review of the strategy, its tests,
  and its registration SQL. It takes the place of stage 6 for those files. Platform changes the
  worker makes during the round still go through stage 6 as usual.

## The loop

1. **Design.** Write the design document. State what is wrong now, what you verified, what
   changes, what you will not do, and what has to be true to call it closed. Verify every
   factual claim against the repository before you write it down.

   **The design is drawn, not narrated.** Its body is three kinds of mermaid diagram:
   - a **class diagram** of every type the change adds or alters, with fields, method
     signatures, and relationships;
   - a **sequence diagram** of each call flow the change touches, across modules and services,
     including the error and rejection paths;
   - a **flowchart** of each decision the change adds or alters: branches, guards, and stop
     conditions.

   In all three, mark every element as existing, changed, or new (for example with
   `<<new>>` and `<<changed>>` stereotypes or a legend), so the review can check existing
   names against the code and judge new ones on their own. After the diagrams, a **test plan
   table** maps each sequence path and flowchart branch to an existing or planned test and its
   expected outcome.

   Prose appears only where a diagram cannot carry the meaning: the definition of an
   individual class or function, an invariant, a formula, or a rule about units and rounding.
   Each diagram names the real module, class, and function identifiers it depicts so the
   review can check them against the repository. A change too small for one of the three kinds
   says so explicitly in the design ("no new decision; flowchart not needed") rather than
   leaving it out silently. A mechanical changeset that alters no type, call flow, or decision
   may omit all three; its design is then a short record of what changes, why nothing else
   does, and which existing tests prove it, and that record still goes to stage 3.
2. **Design review — Codex.** Ask it adversarially: which of these claims does the repository
   contradict, what is missing, what cannot be tested. Ask it to check every element marked
   existing or changed against the code, to check that elements marked new are consistent with
   each other and with the code they attach to, and to name any sequence path or flowchart
   branch the test plan table leaves without a test. **A factual error in the design is the
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
Data reads, auditing your own work, implementation, and design are the worker session's job
or its stage agents'; data reads stay read-only queries. Review is Codex's job at stages 3 and 6.
None of these names is a reason to launch any agent other than a stage agent or a strategy
round agent.

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
