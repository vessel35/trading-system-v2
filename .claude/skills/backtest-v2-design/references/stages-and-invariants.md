# Backtest v2 Design — stages, deferred items, invariants (reference)

Long checklists for the `backtest-v2-design` skill. Reference-notation follows dev_plan §0.2:
`§N`·`§N.M` = a section of `backtest_v2_architecture.md` (canonical); `#K` (e.g. §4.1#3) = component K
of §4.1; `마이그N`·`§13-N` = migration step N of §13; `다이어그램 §N` = `backtest_v2_diagrams.md`;
`AN`/`BN`/`CN` = a dev_plan part; a code path (`services/…`) = a legacy repo file. `_diagrams.md` is
supporting. **This notation is agent-facing ONLY — it tells the AGENT what to read.** The DELIVERABLES
(the design document + inventories) must NOT use any of these foreign-document labels; they refer to
everything by actual name + their own §1-§5 numbers, and the closing Traceability table names each
guideline requirement (e.g. "look-ahead prevention"), never labels it (§0.2, self-contained-design-docs).
Exception: in the indicator context (A1/B6 and the glossary), the shorthand `§7 breadth`,
`§8 Ehlers`, `§12 pinned` refers to sections of the indicator spec `technical_indicators_calc_spec.md`
(as the arch doc itself uses that shorthand), NOT to the architecture doc — where §7=체결, §8=비용, §12=테스트.

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

| Item | Section | Owning stage (설계서 절) | Rule |
|---|---|---|---|
| `backtest_db` meta table fields (backtest_run / backtest_summary / backtest_prereg / backtest_tag) | §9.3 | b-database / B12 (§5.2) | 용도만 정의됨 → mermaid erDiagram + 필드·타입·키·제약 확정, 목적 유지 |
| SQLite Evidence Entity fields (basic 13 + extended 7) | §9.6 | b-database / B13 (§5.3) | same — erDiagram + 필드 확정, 용도 불변 |
| The port list (which concerns become ports) | §4.3 / §4.1#7 | b-components / B4 (§3.2 concrete adapters) + b-corelib-classes / B8 (§4.3 port ABCs) | "미리 고정하지 않는다" → finalize the actual list + method signatures (repr. six named) |
| Trailing-parity tolerance (candle-unit vs live 1m watermark gap) | §14 / diagram 4 | b-service-classes / B9 (§4.4) | 1m execution feed adopted 2026-07-03 → finalize allowed deviation + parity criterion (§12) |

Basic 13 SQLite entities (§9.6): Backtest Run (local copy), Source Data Snapshot, Feature/Indicator
Definition, Feature/Indicator Snapshot, Signal, Decision, Execution, Trade, Position, Portfolio/PnL,
Outcome Bucket, Integrity Check, Chart Summary. Extended 7 (기능 B): Candidate Event, Trade Feature
Snapshot, Condition Signature, Conditional Expectancy, Missed Opportunity, Drawdown/Runup Episode,
Finding/Claim.

---

## §parts — per-part spine (목적 · 입력 · 작업 · 산출물 · 정합성)

Faithful to `backtest_v2_dev_plan.md`. Grouped into the eight stages.

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

> Phase B = ONE doc `backtest_v2_detailed_design.md`, built top-down. 각 파트가 설계서의 한 절을
> **전문(자기완결)** 으로 채우고, 모든 다이어그램은 mermaid. 파트 순서 = 문서 절 순서.

### Stage b-skeleton (설계서 §1-§2)
- **B1 서비스 다이어그램 + 정의서 → §1** — 입력 §0.1·§4.1·§4.2 + A 전체. 작업: 서비스 다이어그램(mermaid:
  `core-lib`·`backtest-service`·기존 `signal-service`/`wallet-service`·저장소 `crypto_data`/`backtest_db`/
  `signal_db`/Evidence SQLite, 의존 방향) → 서비스 정의서(책임·경계·소비·패키징). backtest/replay는 서비스
  아님(제거 대상). 정합성: §0.1·§4.1 의존 방향.
- **B2 프로젝트 코드 트리 → §2** — 입력 §4.2 + B1. 작업: 전체 트리(`core_lib/{types,indicators,strategy,
  sizing,costs,execution,ports,eval}` + backtest-service) + 경로별 한 줄 역할. 트리 노드 = B3 컴포넌트 1:1.
  이 파트가 설계 문서를 생성하고 §1-§5 읽기 지도를 넣는다.

### Stage b-components (설계서 §3.1-§3.3)
- **B3 core-lib 컴포넌트 → §3.1 (공유)** — 입력 §4.1 + B1·B2. mermaid 컴포넌트 다이어그램(types·indicators·
  strategy〈StrategyAdapter/Adaptee〉·sizing·costs·execution·ports·eval·StrategyConfig·Adapter Manager) +
  정의서(책임·인터페이스·의존). 공유는 여기 한 번만.
- **B4 backtest-service 컴포넌트 → §3.2** — 입력 §4.1 + B1·B3. 컴포넌트 다이어그램(Engine·ConfigLayer·
  Harness + 포트 어댑터 DataFeed·Broker·Clock·CostModel·EvidenceSink·CatalogStore) + 정의서. **§4.3 포트
  목록을 구체 어댑터로 확정(deferred).**
- **B5 채택 컴포넌트 → §3.3 (signal/wallet)** — 입력 §13 + A2·A3·B3. 채택 후 컴포넌트 다이어그램(내부 구현이
  `core_lib` import로 치환된 모습) + 정의서(치환 지점·shim·동작 불변). 설계만(C7 실행).

### Stage b-corelib-classes (설계서 §4.1-§4.3)
- **B6 클래스: types·indicators → §4.1** — 입력 §4.1#1·#2·§5.1·§5.8·§6.1 + B3. classDiagram + 정의서:
  types(Candle·Order·Position·Trade·Fill·enums·money, 필드 전문·검증 불변식·Decimal single-cast gate),
  indicators(IndicatorSpec·registry·IndicatorState·contracts, 82종 목록·seed). 지표 계산 flow는 정의서 안.
- **B7 클래스: 전략 (+config 시퀀스) → §4.2** — 입력 §4.1#3·#9·#10·§5.5 + B3·A2. classDiagram + 정의서:
  StrategyAdapter(Protocol)·Adaptee·Adapter Manager·StrategyConfig·trailing·profile(메서드 전문). **Adaptee
  생성·config resolve 시퀀스(mermaid)는 정의서 안.** 경계: 선언=Adaptee, 해석=Config, 생성=Manager.
- **B8 클래스: 실행·평가 (+판정 플로우) → §4.3** — 입력 §4.1#4-8·§7·§8·§10·다이어그램 §5 + B3·A3.
  classDiagram + 정의서: execution·costs·sizing·ports(포트 ABC)·eval(metrics 수식·integrity·hard_gate
  임계값 전문·decision·thresholds·profile). **판정 파이프라인(Integrity→Hard Gate→Decision) 플로우(mermaid)는
  eval 정의서 안.**

### Stage b-service-classes (설계서 §4.4-§4.5)
- **B9 클래스: Engine (+캔들 루프·1m 시퀀스) → §4.4** — 입력 §6.2·§7·§11.1·§14 + B4·B6·B7·B8. classDiagram +
  정의서: Engine·DataFeed/Broker/Clock/CostModel 구현·ConfigLayer·Harness. **캔들 루프(6.2)·1m 트리거 walk·
  look-ahead 순서 시퀀스(mermaid)는 Engine 정의서 안.** **트레일링 parity 허용 편차 확정(deferred).**
- **B10 클래스: 출력 (+run 저장 시퀀스) → §4.5** — 입력 §9 + B4·B9. classDiagram + 정의서: EvidenceSink·
  CatalogStore 책임·인터페이스. **run 저장·finalize 시퀀스(mermaid)는 정의서 안.** 실제 테이블·Entity 스키마는
  §5(B11~B13) ERD로, 여기선 쓰기 계약만.

### Stage b-database (설계서 §5.1-§5.3, DB by ERD — 원칙 4)
- **B11 DB 전체 + crypto_data·signal_db ERD → §5.1** — 입력 §9·다이어그램 §7 + A4·A5. DB 전체 구성 다이어그램
  (crypto_data〈공유·읽기〉·backtest_db〈신규·meta〉·signal_db〈+Adaptee 레지스트리〉·Evidence SQLite〈run별〉,
  역할·접근·경계) → crypto_data 읽기 테이블 erDiagram·정의서(ohlcv 전략TF·1m·funding) → signal_db Adaptee
  레지스트리 erDiagram·정의서.
- **B12 backtest_db ERD + 테이블 정의서 → §5.2** — 입력 §9.3·다이어그램 §7 + B10. `backtest_db` erDiagram
  (backtest_run·backtest_summary·backtest_prereg·backtest_tag, run_id 1:1/0..1/N) → 테이블 정의서(컬럼·타입·
  키·제약 전문 = **§9.3 deferred, 용도 불변**) → run_id 단독 발급·정규화 해시·FK 비강제.
- **B13 Evidence SQLite ERD + Entity 정의서 → §5.3** — 입력 §9.5·§9.6 + B10·B6·B8. Evidence SQLite erDiagram
  (기본 13 + 확장 7, 관계) → Entity 정의서(컬럼·타입·키 전문 = **§9.6 deferred, 용도 불변**) → run 자기완결·
  backtest_run_id 참조.

### Stage b-adoption (설계서 부록)
- **B14 채택·회귀 절차 → 부록** — 입력 §13 + A6. 작업: 채택 지점 + re-export shim(mermaid 시퀀스) → **구↔신
  backtest 대사는 WAIVE**(A6 — 구 backtest 제거 대상), 대신 신 backtest 자체 검증 기준선(골든/parity +
  bias-fix 이식 대상) 명시 → 회귀 범위(wallet 1175·fill_timing next_bar 전환, mermaid 플로우) → 크리덴셜
  회전. 정합성: §13 채택 시 프로덕션 동작 불변.

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
