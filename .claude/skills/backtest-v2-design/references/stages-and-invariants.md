# Backtest v2 Design — stages, deferred items, invariants (reference)

Long checklists for the `backtest-v2-design` skill. Section numbers (§N.M, §4.1#K) refer to
`backtest_v2_architecture.md` in `DESIGN_DOC_DIR`, which is canonical. `_diagrams.md` is supporting.
Exception: in the indicator context (A1/B3 and the glossary), the shorthand `§7 breadth`,
`§8 Ehlers`, `§12 pinned` refers to sections of the indicator spec `technical_indicators_calc_spec.md`
(as the arch doc itself uses that shorthand), NOT to this doc — where §7=체결, §8=비용, §12=테스트.

---

## §invariants — the 16 hard invariants (preserve, never re-decide)

Every contract the design produces must keep all of these. If a design appears to require weakening
one, STOP and escalate to the human — do not quietly relax it.

1. **Look-ahead prevention (core-enforced)** — §1-3, §3.3, §6.2, §11.1. Signals evaluated only after
   candle close; `DataFeed` structurally returns nothing after `up_to`; `resample` drops the
   unfinalized last bucket. The §6.2 loop order is itself the guard.
2. **Timestamp ordering** — §1-4, §7, §11.1. `feature_ts ≤ decision_ts < execution_ts`. Fill is
   strictly after decision = no fill at the decision candle's close; default next-bar-open. Integrity
   Check verifies post-hoc.
3. **Recursive indicators on finalized candles only** — §1-3, §3.3, §4.1#2, §11.1. EMA/RMA/SAR/cumsum
   update on closed candles only, `close_time ≤ judgment time`; `indicators/contracts.py
   assert_finalized` verifies at runtime.
4. **Deterministic normalized Evidence hash** — §9.3, §11.2. The determinism hash is over sorted rows'
   normalized serialization (wall-clock excluded), NOT the SQLite file bytes. Same input + same seed →
   same Evidence, tested. Determinism holds on same platform + pinned deps (numpy/pandas).
5. **Hard Gate thresholds** — §3.5, §10.2, diagram 5. Canonical numbers in `eval/thresholds.py` ↔
   `20_thresholds.md` (some UI-tunable). PF≥3.0 is an over-fit alarm, not auto-accept. Diagram numbers
   are examples — cite the canonical file, do not hardcode a diagram value as truth.
6. **Decimal single-cast gate** — §4.1#1/#2/#6, §11.2. float64 through indicator→strategy→signal; a
   SINGLE `Decimal(str(x))` + quantize at `Broker.submit()`; Decimal-only afterward. `Decimal(float)`
   direct is forbidden (binary noise flips a stop's last digit → intrabar trigger → parity/hash
   flakiness).
7. **Immutability** — §4.1#3 (Adaptee stateless), §4.1#10 (StrategyConfig → immutable config), diagram
   3 (ResolvedConfig immutable).
8. **Research data never in production DBs** — §1-7, §3.6, §9. Detail Evidence in per-run SQLite; meta
   in a dedicated `backtest_db` separate from wallet/signal; `backtest_reader` is a read-only role;
   `CatalogStore` is backtest-only (unused in live/paper).
9. **Accounting identity** — §3.6, §4.1#6, §6.2 (step 2 / diagram 2 ③), §12. `cash + position = equity`; each cost charged
   once; reduce_only returns margin correctly.
10. **All P&L net-of-cost** — §1-5, §3.4, §8. `x_net = x_gross − fee_entry − fee_exit − slippage −
    funding − liquidation_penalty`. "Zero-cost assumption" forbidden.
11. **Sizing survival rule** — §1-8, §3.2, §4.1#4, §8. Edge comes from the entry signal (stop/TP
    placement cannot create expectancy); volatility-based sizing, `1R ≤ 1%` of account. A pct-sizing
    run that cannot guarantee 1R≤1% is flagged "framework 비준수 (compat mode)" in meta.
12. **Candle type-layer validation** — §4.1#1, §5.1. Time strictly increasing (no dup/reorder),
    `close_time = open_time + timeframe`, `high ≥ max(open,close)`, `low ≤ min(open,close)`, price>0,
    volume≥0. Gaps are marked, not filled.
13. **Warm-up signals discarded** — §4.1#11, §5.6, §6.2. Preload `max(strategy min_history, longest
    indicator warm-up)` before `period_start`; never eat into the evaluation window; same at each
    IS/OOS·WFA fold start.
14. **No retroactive self-fill-candle check** — §6.2-2, §7, diagram 2. No position triggers a check
    before its own fill candle (`skip_first_sl_check` inherited).
15. **Conservative same-touch priority** — §7, diagram 2.1. stop+TP same candle → STOP wins (TP-first
    over-states win rate / PF). Intra-candle order is the conservative worst path (OHLC-locked).
16. **Determinism (no wall-clock, single float↔Decimal conversion, seeded)** — §11.2. Companion to #4
    and #6; the design must state where the seed enters and that no wall-clock reaches a recorded value.

---

## §deferred — the items the doc defers to detailed design (write out IN FULL; keep 용도)

> Self-containment applies to ALL of these: the deliverable must list the ACTUAL fields / port list +
> signatures / tolerance value, not a reference to the section. A `§N` citation belongs only in the
> doc's closing Traceability table.

| Item | Section | Owning stage | Rule |
|---|---|---|---|
| `backtest_db` meta table fields (backtest_run / backtest_summary / backtest_prereg / backtest_tag) | §9.3 | b-engine-eval (B6) | 용도만 정의됨 → 필드·타입·제약 확정, 용도·목록 조정 가능하나 목적은 유지 |
| SQLite Evidence Entity fields (basic 13 + extended 7) | §9.6 | b-engine-eval (B6) | same — 용도 불변, 필드만 확정 |
| The port list (which concerns become ports) | §4.3 / §4.1#7 | b-corelib (B1) | "미리 고정하지 않는다" → finalize the actual list + method signatures (repr. six named) |
| Trailing-parity tolerance (candle-unit vs live 1m watermark gap) | §14 / diagram 4 | b-engine-eval (B5) | 1m execution feed adopted 2026-07-03 → finalize allowed deviation + parity criterion (§12) |

Basic 13 SQLite entities (§9.6): Backtest Run (local copy), Source Data Snapshot, Feature/Indicator
Definition, Feature/Indicator Snapshot, Signal, Decision, Execution, Trade, Position, Portfolio/PnL,
Outcome Bucket, Integrity Check, Chart Summary. Extended 7 (기능 B): Candidate Event, Trade Feature
Snapshot, Condition Signature, Conditional Expectancy, Missed Opportunity, Drawdown/Runup Episode,
Finding/Claim.

---

## §parts — per-part spine (목적 · 입력 · 작업 · 산출물 · 정합성)

Faithful to `backtest_v2_dev_plan.md`. Grouped into the five stages.

### Stage a-domain
- **A1 지표 인벤토리** — 입력 §3.3·§5.8 + `$TRADING_SYSTEM_DIR` signal
  `domain/indicators/{technical,extended}.py`. 작업: signal-service 구현 지표 목록화 → 82종 gap 표
  (§12 pinned·§7 breadth·§8 Ehlers·Donchian·adx_14·주간 ATR) → 상용 ~10-15종 식별. (backtest 복제본은
  제거 대상이라 드리프트 대조 없음.) 산출: `A1_indicator_inventory.md`. 정합성: "구현은 전부·계산은
  설정"(§5.8).
- **A2 전략 인벤토리** — 입력 §3.2·§4.1#3 + signal `domain/strategies/`, `strategy_executor.py`,
  `strategy_service.py`. 작업: AbstractStrategy·Registry·Factory·상속체인(이식 대상 아님) 기술 → 전략별
  순수 `analyze`(입력/출력/의존 지표) 이식 범위 → `required_indicators`·TF·프로파일 후보 → wallet
  트레일링 관계. 산출: `A2_strategy_inventory.md`. 정합성: Adaptee=판단 전용.
- **A3 실행·비용·사이징** — 입력 §6·§7·§8·§4.1#4-6 + wallet `futures_calculator.py`·
  `slippage_calculator.py`·`trailing_stop_update_service.py`·`slippage_validator.py` + paper 체결.
  작업: 체결·비용·사이징·sub-candle 트레일링 이식 범위·계약 → `fill_timing`(immediate) 확인 → wallet
  회귀(1175) 범위 스캔. 산출: `A3_execution_cost_sizing_inventory.md`. 정합성: 마이그5 동작 보존.

### Stage a-infra
- **A4 타입·config·DB** — 입력 §4.1#1·§9.2 + `$TRADING_SYSTEM_DIR` wallet `entities/`·
  `value_objects.py`, signal `TradingSignal`, 각 `core/config.py`, `init-scripts/`(01~03).
  작업: 공용 타입 이식 목록 → 새 `backtest_db` 생성 방식을 `init-scripts/`+인프라에서 도출(제거 대상
  backtest 서비스의 `backtest_db` 정의는 계승 원천이 아니라 legacy-정리 대상 — DB 이름/역할 유지·개명
  결정 기록) → 평문 비밀번호 회전 대상. 산출: `A4_types_config_db_inventory.md`. 정합성: §9.2 DB-생성 규약.
- **A5 collector** — 입력 §3.3·§14 + `$CRYPTO_DATA_HUB_DIR`의 collector. 작업: collector를 OHLCV 적재
  vs 지표 사전계산 분리 → 의존성·설정·크리덴셜 목록 → 적재만 내부화, 지표 사전계산·
  `technical_indicators` 읽기 폐지 경계 → 1m·전략 TF 적재 범위(2025-03~). 산출:
  `A5_collector_internalization_scope.md`. 정합성: §14 "collector는 적재만". (필요한 파일 없으면 경로와
  함께 블로커 기록.)
- **A6 폐기 목록·대사 결정** — 입력 §2·§4.1#9. 작업: 제거 대상 목록화(구 `services/backtest/`
  engine·CLI·mock·sys.path·harness·지표 복제, 그리고 `replay` — **읽지 않음**) → **구↔신 backtest 대사
  기준선 WAIVE**(사유 기록: 구 backtest는 제거 대상이라 참조하지 않음) → bias-fix 31 테스트는
  `feat/vessel-reversion-short-only` 브랜치에 있으며 Phase C 이식 대상으로 **이름·브랜치만 기록**(여기서
  읽지 않음). 산출: `A6_baseline_and_reconciliation.md`. 정합성: 대사 waive가 명시·사유화됐는지(§2/§14).

### Stage b-corelib
- **B1 토폴로지 + core-lib 구조 + 포트** — 입력 §0.1·§4.1·§4.2·§7·§11.1 + A1~A6. 작업: 신규 repo →
  `core-lib` 설치형 패키징 → `core_lib` 트리 → 포트 시그니처(DataFeed bounded+1m·Broker·Clock·
  CostModel·EvidenceSink·CatalogStore) → `StrategyAdapter` Protocol(get_metadata/get_parameter_schema/
  analyze) → 의존 방향 단방향. **§4.3 포트 목록 확정(deferred).** 산출: `B1_topology_ports.md`.
- **B2 타입 상세** — 입력 §4.1#1·§5.1 + A4. 작업: Candle·Order·Position·Trade(+r0)·Fill·enums·
  money(quantize) 필드 확정 → 캔들 검증 불변식 → Decimal 정밀도 + single-cast gate 명시. 산출:
  `B2_types_detail.md`.
- **B3 지표 registry·contracts** — 입력 §2·§5.8·§6.1·§11.1 + A1. 작업: IndicatorSpec(버전·min_history·§12
  pinned)·compute_batch·IndicatorState.update·assert_finalized(close_time≤T) 계약 → 82종 목록·파라미터·
  pinned 확정 → 벡터화↔증분 seed·워밍업. 산출: `B3_indicator_contracts.md`.
- **B4 StrategyConfig·Manager·레지스트리** — 입력 §4.1#9·#10·§5.5 + A2. 작업: StrategyConfig(resolve/
  json_schema/serialize/version) → Adapter Manager(create/lifecycle/registry) → signal_db Adaptee
  레지스트리 스키마 → config 검증(extra=forbid·기본값·교차필드) → 레지스트리 접근 포트(core_lib DB
  비의존). 경계: 선언=Adaptee, 해석=StrategyConfig, 생성=Manager. 산출: `B4_strategyconfig_manager.md`.

### Stage b-engine-eval
- **B5 Engine·1m 피드·look-ahead** — 입력 §6.2·§7·§11.1·§14 + A3·B1. 작업: 캔들 루프 의사코드(§6.2 시가/
  종가) → bounded DataFeed 미래 비노출 강제 → 1m 집행 피드 트리거 walk(손절·트레일링·청산 시간순) →
  `decision_ts < execution_ts` 강제 지점 → 워밍업 프리로드. **트레일링 parity 허용 편차 확정(deferred).**
  산출: `B5_engine_1m_lookahead.md`.
- **B6 출력 계층(Entity 필드)** — 입력 §9(용도 표) + A4·B2·B7. 작업: Evidence SQLite 필드 확정(기본 13·
  확장 7) → `backtest_db` meta 4테이블 필드 확정 → 정규화 해시 규칙(파일 바이트 아님·wall-clock 제외) →
  EvidenceSink·CatalogStore 계약. **§9.3·§9.6 필드 확정(deferred), 용도 불변.** 산출:
  `B6_output_entities.md`.
- **B7 판정·eval** — 입력 §10·§10.1·§10.2 + diagrams §5 + B6. 작업: metrics 수식(√365 리샘플·Sortino·
  SQN·intrabar MDD·Calmar/MAR·RoR MC) → Integrity 항목 → Hard Gate (A) 임계값 정본 위치·(B) 프로파일 →
  Decision 라우팅(promote/partial_keep/retest/abandon) → envelope_status 성숙도. 산출:
  `B7_eval_judgment.md`. 정합성: Scorecard 없음·3단계·forensics 루프.

### Stage b-adoption
- **B8 채택·검증기준·회귀** — 입력 §13 + A6. 작업: 기존 서비스 내부 구현→`core_lib` import 치환 지점 +
  re-export shim 배치 → **구↔신 backtest 대사는 WAIVE**(A6 — 구 backtest 제거 대상), 대신 신 backtest의
  자체 검증 기준선(골든/parity + A6가 넘긴 bias-fix 이식 대상) 명시 → 회귀 범위(wallet 1175·fill_timing
  next_bar 전환 시점) → 크리덴셜 회전. 산출: `B8_adoption_reconciliation_regression.md`. 정합성: §13
  채택 시 프로덕션 동작 불변.

---

## §sections — architecture section cross-reference (quick map)

§0 목적/목표 (기능 A 검증 / B 개선, B가 주 목적) · §1 8 불변 원칙 · §2 폐기 vs 존치 · §3 요구사항
(3.1 공유·3.2 구조 vs 전략·3.3 지표·3.4 비용/체결·3.5 판정·3.6 데이터/출력·3.7 과최적화) · §4 아키텍처
(4.1 16 컴포넌트 명세[#K 번호]·4.2 core-lib 패키지·4.2.1 거버넌스·4.3 포트 6종) · §5 입력 (5.1 Candle+1m·
5.2 Funding·5.3 비용·5.4 거래소규칙·5.5 전략설정·5.6 실행/리스크·5.7 sweep·5.8 지표계산·5.9 프로파일) ·
§6 실행 (6.1 vectorized/incremental·6.2 캔들 루프·6.3 재현 vs stub) · §7 체결 규칙 · §8 비용·리스크 net ·
§9 출력 (9.1 2계층·9.2 backtest_db 생성·9.3 meta 스키마[deferred]·9.4 포트분리·9.5 거래로그·9.6 SQLite
Entity[deferred]·9.7 비기능) · §10 지표·판정 (10.1 metrics·10.2 3단계 판정·10.3 harness·10.4 개선 루프
기능 B) · §11 검증 (11.1 look-ahead·11.2 결정성·11.3 입력검증) · §12 테스트 계획 · §13 마이그레이션 1~8 ·
§14 확정 결정(2026-07-01 + 07-03 1m 피드) · §15 하지 않는 것. Diagrams: 1 컴포넌트·2 캔들/체결·3 config/
push·4 트레일링 갭·5 판정·6 개선·7 ER.
