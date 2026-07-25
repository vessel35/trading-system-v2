# WebUI 정보구조·UI/UX 설계

이 문서는 WebUI의 정보 구조와 화면·상호작용을 개발 착수 전에 설계한다. 방향은 `docs/webui-direction.md`,
API 계약은 `docs/webui-api-design.md`, 교차 정합은 `docs/webui-predev-plan.md`에 있다. 화면마다
"필요한 데이터"를 카탈로그 컬럼·Evidence 엔티티에 직접 묶어, API가 그 화면을 채울 수 있는지 대조 가능한
체크리스트로 남긴다.

## 0. 관점

이 콘솔의 존재 이유는 "전략 개선을 위한 연구"이며 나머지는 보조축이다. 매일 반복될 작업은 "하나의
백테스트 실행이 왜 이런 성적을 냈는지 증거로 파고들고, 직전 실행과 나란히 놓고 무엇이 나아졌는지
판정하는 것"이다. 그래서 이 설계는 화면을 균등히 나누지 않고 Evidence 분석과 실행 간 비교를 물리적·
시각적 중심에 둔다. 성공 기준은 화면 수가 아니라, 가설 등록에서 실행·Evidence 조사·비교·판정·다음
가설로 이어지는 연구 루프를 화면 위에서 끊김 없이 도는지다.

## 1. 정보구조와 내비게이션 셸

앱은 두 도메인으로 갈린다. 위쪽은 읽기 중심의 "연구", 아래쪽은 시각적으로 분리된 "라이브"이며 색·
아이콘·경고 배너로 한눈에 구분한다. 연구 도메인 상위 구획은 넷이다. "카탈로그"(P0, 실행 목록·요약
브라우즈), "분석(Evidence)"(P1, 상세 증거·실행 비교 — 이 콘솔의 심장), "실행 관리"(P2, 트리거·상태·
스윕·사전등록), "전략"(단계 무관 참조, `strategy_registry`). 라이브 도메인 상위 구획은 둘이다.
"모니터"(P3, 읽기 전용), "제어"(P4, 게이트). 둘은 별도 프리셋 확정 전까지 자리만 잡고 비활성으로 둔다.

좌측 사이드바가 상위 구획을, 상단 바가 전역 요소를 담는다. 라이브 구획은 연구 구획과 구분선·색으로 분리한다.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ▣ Backtest Console        [ RESEARCH · DRY-RUN ]   ⌘K 검색  ⚖ 비교(2) ◐         │  ← 상단 바(청록 배지)
├────────────┬─────────────────────────────────────────────────────────────────┤
│ 연구        │                                                                  │
│  ▤ 카탈로그   │                    (라우트별 본문 영역)                            │
│  ◎ 분석      │                                                                  │
│  ⏵ 실행 관리  │                                                                  │
│  ⌗ 전략      │                                                                  │
│ ─────────── │                                                                  │
│ 라이브 🔒    │   (모니터·제어는 붉은 계열 구분선 아래, 별도 프리셋 전엔 비활성)         │
│  ◔ 모니터    │                                                                  │
│  ⛔ 제어      │                                                                  │
└────────────┴─────────────────────────────────────────────────────────────────┘
```

라이브 라우트로 진입하면 배지가 청록에서 호박색(모니터, 읽기 전용)·적색(제어)으로 바뀌고 상단에 경고
띠가 깔린다. 이 색 전환이 "연구인지 라이브인지"를 매 순간 알려주는 1차 안전 신호다.

전역 요소는 다섯이다. 명령 팔레트(Command+K로 run/전략/심볼 검색·이동·동작 실행), 비교 바스켓(어디서든
실행을 담아 비교로 넘기는 전역 상태), 전역 필터 컨텍스트(strategy·symbol·timeframe·기간·status·
decision_route·gate_verdict를 목록형 화면이 공유), 테마 토글(다크 기본), 환경·안전 배지("RESEARCH ·
DRY-RUN" 상시 노출).

연구 평면은 방향성 비순환이라 데이터 누수·은닉 상태 위험이 없다. 유일한 순환은 사람이 낀 라이브 제어
루프이며, `apps/web`과 `web-api`는 `live-control`로 향하는 엣지를 하나도 갖지 않는다(연구 API는 주문
코드를 import·호출 불가, 거래소 키·지갑 쓰기 자격증명은 `live-control`만 보유, P3 모니터는 `wallet_db`
읽기 전용만). 바이브코딩으로 만든 연구 화면이 라이브 제어 순환으로 들어가는 경로가 코드 구조상 없다.

## 2. 화면 목록

P0(카탈로그): 실행 목록, 실행 요약(P1 상세의 개요 탭과 동일 화면 — P0에서 최소로 출시 후 P1에서 탭
성장). P1(분석): 실행 상세 7탭(개요, 자본곡선·드로다운, 거래, 차트, 신호·의사결정, 무결성·비용,
조건부 기대값·연구 노트), 거래 상세 드로어, 실행 비교. P2(실행 관리): 트리거 폼, 실행 큐·상태 모니터,
스윕 빌더·결과 그리드, 사전등록 폼. P3: 라이브 모니터(개념). P4: 라이브 제어(개념). 전략 참조: 목록·상세.

## 3. 공통 UX 원칙

정보 밀도는 연구 도구에 맞춰 "조밀"을 기본으로 하고 "편안"을 토글로 둔다. 숫자는 tabular-nums로 자릿수를
세로 정렬하고, 금액은 문자열로 받아 표시만 하며 프런트에서 산술하지 않는다. 비교를 1급 시민으로 둔다 —
모든 행을 비교 바스켓에 담고, 바스켓은 페이지를 옮겨도 유지되며, 비교 화면에서 기준선을 고정하면 나머지
지표가 델타로 강조된다. 결정성 키(config_hash·source_data_hash)로 "같은 설정 재실행"과 "설정 변경"을
구분한다. 키보드 친화성(명령 팔레트·행 이동·비교 담기·필터 포커스·구획 점프)을 전면에 둔다. dry-run 안전
신호를 곳곳에 둔다. 라이브를 건드리는 것에는 강한 확인 게이트와 오해 불가능한 시각 분리(모니터 호박색·
제어 적색·심볼 재입력·idempotency 키·상시 kill switch·잠금 배너)를 둔다. 전역 상태는 로딩=스켈레톤,
빈 상태="왜 비었는지+다음 행동", 에러=표준 code·message+재시도로 통일한다.

## 4. P0 화면 상세

### 4.1 카탈로그 — 실행 목록

목적: 모든 백테스트 실행을 요약 지표와 함께 훑어보며 필터·정렬하고 관심 실행을 골라 상세로 들어가거나
비교에 담는다.

```
┌─ 카탈로그 · 실행 ────────────────────────────────────────────── ⚖ 비교(2) ─┐
│ [/필터] strategy▾ symbol▾ tf▾ 기간▾ status▾ gate_verdict▾ route▾   ↺ 초기화 │
│ 열 선택 ⚙  밀도 ▤/▦  내보내기 ⭳                          142개 실행 · 1/6 │
├──┬───────────────────────┬────────┬─────┬────┬─────┬──────┬────┬─────┬───────┤
│☐ │ run_name / run_id      │strategy│ sym │ tf │ pf  │sortino│mdd │ psr │verdict│
├──┼───────────────────────┼────────┼─────┼────┼─────┼──────┼────┼─────┼───────┤
│☑ │ ema-cross-oos-b        │Vessel  │BTC  │ 1h │1.84 │ 2.11 │12.3│0.71 │pass   │
│☐ │ atr-stop-tighten       │Vessel  │ETH  │ 4h │0.94 │ 0.71 │28.1│0.22 │not_pro│
├──┴───────────────────────┴────────┴─────┴────┴─────┴──────┴────┴─────┴───────┤
│ 선택 2개 → [비교에 담기] [태그]                      ◀ 이전  1 2 3 … 6  다음 ▶ │
└──────────────────────────────────────────────────────────────────────────────┘
```

컴포넌트: TanStack Table 위 shadcn Table(정렬·열 표시/숨김·행 선택), 필터 바는 Select·Popover·
DateRangePicker·Command 다중선택, 열/밀도는 DropdownMenu, 상태는 Badge, 선택 동작은 하단 고정 액션 바.
차트: 표 중심이라 큰 차트 없음. pf·sortino·mdd 열에 Recharts 마이크로 바 선택지.
상호작용: 필터 좁히기, 열 정렬, 다중 선택 후 비교 담기, 행 클릭 상세 이동, 태그 부여, 슬래시/방향키
키보드 흐름. status RUNNING은 회전, FAILED·ORPHANED는 회색·경고.

필요한 데이터: `backtest_run`(run_id·run_name·strategy_id·strategy_name·symbol·timeframe·period·
status·created_at·config_hash·source_data_hash·sweep_id), `backtest_summary`(pf·sortino·calmar_or_mar·
sqn·mdd·ror·sharpe·psr·win_rate·payoff·expectancy_r·ulcer·kelly·trade_count·net_pnl_total·gate_verdict·
decision_route·integrity_status·data_coverage_ratio), 서버측 페이지네이션 계약, `backtest_tag` 필터 패싯.

### 4.2 실행 요약 (상세의 개요 탭)

목적: 한 실행의 정체성·성적·판정·데이터 건강도를 한 화면에서 파악하고 상세 탭·비교로 갈라져 들어가는 관문.

```
┌─ BT_20260722_000141_ema-cross-oos-b ──────── ⚖ 비교  ⏵ 재실행  ⌗ 태그 ─┐
│ Vessel Reference v1.0.0 · BTCUSDT · 1h · FUTURES · 2025-01→06 · seed 0  │
│ 초기자본 10,000 · risk_based 1.00% · config_hash 9f3c… · source a1b2…    │
│ [ 개요 ] 자본곡선·DD 거래 차트 신호·의사결정 무결성·비용 조건부·노트     │
│ ┌ 판정 ────────────────────────────────────────────────────────────┐ │
│ │ GATE pass(B)  ROUTE promote  ENVELOPE in_range  OOS 열화 -6.2%      │ │
│ │ 근거: "sortino 성공 임계 위, OOS 허용 범위" (decision_rationale)    │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│ ┌ 핵심 지표 ────────────────────────────────────────────────────────┐ │
│ │ PF 1.84 Sortino 2.11 Calmar 1.32 SQN 3.1 Sharpe 1.55 PSR 0.71       │ │
│ │ MDD 12.3% RoR 4.1% Ulcer 5.2 Kelly .18 승률 54% 기대 0.34R 거래 141 │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│ ┌ 데이터 건강도 ───────────┐ ┌ 비용 분해(Recharts 워터폴) ──────────┐ │
│ │ 커버리지 99.7%           │ │ gross +2310 fee -281 slip -142        │ │
│ │ 최대연속갭 3 · 갭이탈 1   │ │ funding -45 penalty 0 = net +1842      │ │
│ │ integrity passed ✓        │ └────────────────────────────────────────┘ │
│ └──────────────────────────┘                                            │
└──────────────────────────────────────────────────────────────────────────┘
```

컴포넌트: Card·정의목록·격자, gate_failed_json·envelope_deviated_json 배열은 HoverCard/Accordion,
상단 동작은 Button·DropdownMenu, 탭은 Tabs, 긴 해시는 클릭 복사.
차트: 비용 분해 Recharts 워터폴, 상단에 자본곡선 sparkline(Recharts 라인).
상호작용: 탭 전환, 비교 담기, "같은 설정 재실행"(config_hash 프리셋으로 트리거 폼), 태그, 해시 복사,
판정 배열 펼치기. gate_verdict가 pass가 아니면 배너 경고색+실패 항목 펼침.
상태: RUNNING이면 "실행 중" 안내+스트림 링크, FAILED면 error_message 강조, Evidence 미접근이면
"요약만 표시"로 우아하게 저하.

필요한 데이터: `backtest_run` 전 구성 컬럼, `backtest_summary` 지표·판정·커버리지·비용 컬럼 전부,
status·error_message·started_at·finished_at.

## 5. P1 화면 상세 — Evidence 분석(심장)

실행 상세는 개요(4.2) 포함 7탭. 이하 여섯 탭·드로어·비교.

### 5.1 자본곡선·드로다운

목적: 자본 성장·손실을 시간축으로 보고 드로다운의 깊이·기간·회복을 사건 단위로 파고든다.

```
┌─ 자본곡선·드로다운 ──────────────── [로그축] [매매마커 겹치기] ─┐
│ 자본 ╭──╮   ╭────╮   ╭──── (Lightweight Charts 자본 라인)        │
│  ────╯  ╰─╮╭╯    ╰─╮╭╯                                          │
│ DD 0%┐ ┌─┘└┐  ┌───┘└┐   (Recharts area, 자본과 시간축 동기화)    │
│  -12%└─┘   └──┘     └──                                         │
├────────────────────────────────────────────────────────────────┤
│ 드로다운 사건(깊이순): 시작·저점·회복·깊이·기간·기여거래(→상세)   │
│  03-14→03-19→04-02  -12.3%  19일  #83 #84 #85                    │
└──────────────────────────────────────────────────────────────────┘
```

컴포넌트: ToggleGroup, 사건 표 TanStack Table, 기여 거래 Badge(→드로어). 차트: 자본곡선 Lightweight
Charts 라인/영역, 드로다운 Recharts 영역(시간축 동기), 월별 수익 Recharts 히트맵. 상호작용: 로그축,
매매 마커 겹치기, 사건 행 클릭으로 구간 확대·기여 거래 강조, 브러시.
필요한 데이터: `PORTFOLIO_PNL`(ts·total_equity·peak_equity·drawdown_pct·intrabar_low_equity 등),
`CHART_SUMMARY`(equity·drawdown·monthly_return), `DRAWDOWN_RUNUP_EPISODE`(start/end/recovery_ts·
depth_pct·duration·contributing_trades_json), 마커용 `EXECUTION`.

### 5.2 거래

목적: 개별 거래를 표로 훑고 R-multiple 분포·결과 버킷으로 거래 품질 구조를 보며 단건 상세로 파고든다.

```
┌─ 거래 141건 ──── [exit_reason▾][승/패▾][outcome_class▾]  R 분포 ▾ ─┐
│ ┌ R 분포(Recharts 히스토그램) ──┐ ┌ 결과 버킷(Recharts 막대) ─────┐ │
│ │   ▁▃█▆▃▂  -2R -1R 0 +1R +2R    │ │ top_winner ██12 normal █████64│ │
│ │  (0 기준 색 분리, 꼬리 강조)    │ │ small ████49 tail ▉12 churn ▏4│ │
│ └─────────────────────────────────┘ └──────────────────────────────┘ │
│ #83 LONG STOP_LOSS net -142 R -1.00 17h │ #85 LONG LIQUID. -410 -2.90⚠ │
└─────────────────────────────────────────────────────────────────────────┘
```

컴포넌트: TanStack Table(가상 스크롤), 분포·버킷 카드, 다중선택 Command 필터, 청산은 경고 Badge.
차트: R-multiple 분포 Recharts 히스토그램(0 기준 좌우 색), 결과 버킷 Recharts 가로 막대. 상호작용:
exit_reason·승패·outcome_class로 표·분포 동시 필터, 분포 막대 클릭으로 해당 R 구간만(차트·표 양방향
브러싱), 행 클릭 드로어. 상태: 거래 0건이면 신호·의사결정 탭으로 유도, r_multiple null(r0 미정의)은
R제외 표기하고 `backtest_summary.r_excluded_count`와 대조.
필요한 데이터: `TRADE` 전 컬럼, `OUTCOME_BUCKET`(trade·outcome_class 집계), 요약 win/loss/r_excluded_count.

### 5.3 거래 상세 드로어

목적: 한 거래의 진입~청산 체결·비용·펀딩·특징·최대역행/순행을 한 패널에서 재구성.

```
┌─ 거래 #85 · LONG · BTCUSDT ────────────────────────────── ✕ ┐
│ 진입 03-18 03:00 @41,250 수량0.184 3x 청산됨⚠ net-410 R-2.90 │
│ 체결(EXECUTION): 진입 MARKET ref41250→41268 fee3.8 slip3.3   │
│               청산 LIQUIDATION ref39900→39840 penalty gap    │
│ 펀딩(FUNDING_SETTLEMENT): 08:00 +0.012% measured pay-6.1      │
│ 특징(TRADE_FEATURE_SNAPSHOT): entry trend_up · mae -2.9R      │
│ 후보 연결(CANDIDATE_EVENT): trigger "ema_cross_up" filters ▾  │
└──────────────────────────────────────────────────────────────┘
```

컴포넌트: Sheet(우측 드로어), Accordion, features_json은 Collapsible→키-값 표, 금액 tabular-nums.
차트: mae·mfe excursion_r 소형 수평 막대(Recharts), "차트에서 이 거래 보기" 링크(5.4 연동). 상호작용:
다음/이전 거래 순회, 차트 탭 연동, 청산이면 청산가·마진 강조.
필요한 데이터: `EXECUTION`(entry·exit), `FUNDING_SETTLEMENT`(trade_id), `TRADE_FEATURE_SNAPSHOT`(phase·
features_json·regime_tag·excursion_r), `CANDIDATE_EVENT`(linked_trade_id), 선택 `POSITION`(청산 맥락).

### 5.4 차트

목적: 캔들 위에 지표·매매 마커를 겹쳐 진입·청산이 시장 구조 위 어디서 일어났는지 눈으로 검증.

```
┌─ 차트·BTCUSDT 1h ── [지표: EMA9 EMA21 ATR▾][마커: 진입/청산/신호/후보][기간◧] ─┐
│ 42k┤      ▲84청산   EMA21────╲   (Lightweight: 캔들 + 라인 오버레이)             │
│ 41k┤ ┃┃┃┃┃┃▲85진입  EMA9╲╲                                                     │
│ 40k┤   ▼85청산(LIQ)⚠     ╲                                                       │
│ ATR┤▁▂▃▅▆▇█▇▆▅▃ (하단 동기 페인)                                                │
│ 범례: ▲진입(색=side) ▼청산(색=exit_reason) ◇신호(warmup 반투명) ·후보(blocked)  │
└────────────────────────────────────────────────────────────────────────────────┘
```

컴포넌트: ToggleGroup·DropdownMenu(지표·마커 토글), Popover(마커 요약), Button(→드로어). 차트:
Lightweight Charts 캔들스틱+라인 오버레이+마커 API, ATR은 하단 동기 페인. 상호작용: 지표 on/off,
마커 종류 토글, 마커 클릭→거래 상세, 확대·이동, 후보 마커(blocked_by)로 "진입할 뻔했으나 막힌 지점" 확인.
필요한 데이터: 원천 OHLCV(제공 범위는 `SOURCE_DATA_SNAPSHOT`), `INDICATOR_DEFINITION`·
`INDICATOR_SNAPSHOT`(feature_ts·value·is_warmup), `EXECUTION`, `SIGNAL`, `CANDIDATE_EVENT`.
(OHLCV는 API 정합 보완 `/runs/{id}/candles`로 서비스 — `webui-predev-plan.md` 2절.)

### 5.5 신호·의사결정 (왜 진입했고 왜 안 했나)

목적: 신호가 진입·청산·건너뜀 중 무엇으로 이어졌는지, 진입할 뻔한 후보가 무엇에 막혔는지, 놓친 기회는
무엇인지 조사해 전략 로직의 게이트를 검증. 진단 원칙: 성적이 기대와 어긋나면 전략 로직을 의심하기 전에
지표 신선도(`INDICATOR_SNAPSHOT.feature_ts`·is_warmup, `SIGNAL`의 feature_ts·decision_ts 정렬)와 재진입/
쿨다운 게이트(`CANDIDATE_EVENT.blocked_by`)를 먼저 확인한다. 그래서 blocked_by 분포를 1급 시각화로 둔다.

```
┌─ 신호·의사결정 ────── [action▾][skip_reason▾][blocked_by▾] ─┐
│ 건너뜀(DECISION.skip_reason)     후보차단(CANDIDATE.blocked_by)│
│ cooldown ████41 position ███27   reentry_gate ████33 cooldown██22│
│ 03-18 03:00 LONG conf0.55 enter SL40100 TP43200 → #85          │
│ 03-18 05:00 LONG conf0.60 skip cooldown_active                 │
│ 03-18 09:00 exit skip position_open (feat 지연?⚠)              │
└────────────────────────────────────────────────────────────────┘
```

컴포넌트: TanStack Table, 분포 카드, 다중선택 Command, is_warmup·feat_ts 지연은 Tooltip 아이콘. 후보·
놓친 기회는 하위 Tabs. 차트: skip_reason·blocked_by Recharts 가로 막대(재진입·쿨다운 상단 정렬).
상호작용: 필터, 분포 막대 클릭으로 해당 사유만, 신호 행→차트 탭 시점 점프, realized 후보→거래 상세.
feature_ts가 decision_ts보다 뒤처지거나 is_warmup이면 강조.
필요한 데이터: `SIGNAL`·`DECISION`(결합), `CANDIDATE_EVENT`, `MISSED_OPPORTUNITY`, 신선도 대조용
`INDICATOR_SNAPSHOT`.

### 5.6 무결성·비용

목적: 이 실행의 숫자를 믿어도 되는지 무결성 검사·커버리지로 확인하고 비용이 성적을 얼마나 깎았는지 분해.

```
┌─ 무결성·비용 ──────────────────────────────────────────────┐
│ 무결성(INTEGRITY_CHECK)        데이터 커버리지               │
│ accounting_identity ✓ ...      커버리지 99.7%(4362/4374)     │
│ deterministic ✓ evidence ✓     최대연속갭 3bars 갭이탈1       │
│ trailing_parity ―해당없음       funding 미관측2 coverage_passed✓│
│ 비용(Recharts 워터폴): gross+2310 -fee281 -slip142 -fund45 =net+1842│
└──────────────────────────────────────────────────────────────┘
```

컴포넌트: Badge·Collapsible(실패면 detail_json 펼침), Card·Progress, diagnostic_only면 상단 Alert.
차트: 비용 Recharts 워터폴, 커버리지 Progress/게이지. 상호작용: 실패 검사 detail_json·sample_ref 펼침,
커버리지 gap을 차트 탭 시간축과 연동, funding 미관측·갭 이탈→관련 거래. 상태: diagnostic_only면
"판정 근거로 승격 불가" 경고.
필요한 데이터: `INTEGRITY_CHECK`, `backtest_summary` 커버리지·무결성·비용 컬럼, 회계 항등식 검증용
gross/fee/slippage/funding/penalty/net.

### 5.7 조건부 기대값·연구 노트 (개선 루프의 종착이자 시작)

목적: "어떤 조건에서 실제로 우위를 갖는가"를 조건 서명별 기대값·신뢰구간으로 읽고, 이 실행의 주장
(finding)을 근거와 함께 기록해 다음 가설로 잇는다.

```
┌─ 조건부 기대값·연구 노트 ─── [유의미만][표본≥N][정렬:기대값▾] ─┐
│ 조건 서명별(CONDITION_SIGNATURE × CONDITIONAL_EXPECTANCY)      │
│ regime=trend_up·conf≥0.6  38  63% 2.1 +0.52 [+.18,+.86] ✓CI>0 │
│ regime=range·conf<0.6     44  41% 0.9 -0.21 [-.55,+.13] ✗     │
│ 연구 노트(FINDING_CLAIM)          사전등록 대조(backtest_prereg)│
│ "range 저신뢰 진입이 손실 대부분"  가설: ATR 손절 축소로 tail 감소│
│  제안: range+저conf 차단 →PR-114    관측 sortino 2.11 → 성공 ✓  │
└────────────────────────────────────────────────────────────────┘
```

컴포넌트: TanStack Table, Card 목록+confidence Badge, 정의목록, Collapsible(definition_json·evidence_ref).
노트 작성 기능은 쓰기 범위 열린 결정이라 기본 읽기 표시. 차트: 조건별 기대값·CI는 Recharts 점·오차막대
(0선 통과 여부). 상호작용: 유의미만·최소 표본 필터·정렬, 조건 클릭으로 거래 탭 필터, evidence_ref 클릭으로
근거 엔티티 점프, next_prereg_ref로 사전등록 연결.
필요한 데이터: `CONDITION_SIGNATURE`, `CONDITIONAL_EXPECTANCY`, `FINDING_CLAIM`, `backtest_prereg`,
`backtest_summary.harness_json`.

### 5.8 실행 비교 (비교-우선의 심장)

목적: 바스켓의 여러 실행을 나란히 놓고 설정 차이와 지표 델타를 대조해 "무엇을 바꿨더니 무엇이 나아졌나"를
판정.

```
┌─ 실행 비교(3) ──── 기준선:[ema-cross-oos-a▾] [설정diff만][지표만] ─┐
│                    │●baseline-a(기준)│○oos-b        │○atr-tighten   │
│ config_hash        │4c1a…           │9f3c…(변경)   │7b22…(변경)     │
│ params.reward_risk │2.0             │2.5 ▲변경     │2.0            │
│ PF                 │1.52            │1.84(+0.32)▲  │0.94(-0.58)▼   │
│ Sortino            │1.78            │2.11(+0.33)▲  │0.71(-1.07)▼   │
│ MDD                │15.8%           │12.3%(-3.5)▲좋│28.1%(+12.3)▼나 │
│ gate/route         │pass/retest     │pass/promote  │not_pro/abandon│
│ 자본곡선 겹침(Lightweight): a(회) oos-b(청) atr(적,아래로)          │
└────────────────────────────────────────────────────────────────────┘
```

컴포넌트: TanStack Table(실행을 열로 전치), Select(기준선), ToggleGroup, Badge(변경 셀). 차트: 자본곡선
겹침 Lightweight Charts 색 구분 라인, 지표 델타 Recharts 그룹 막대 토글. MDD·RoR·Ulcer는 델타 색 방향 반전.
상호작용: 기준선 고정·델타 재계산, 설정 diff만/지표만, 변경 파라미터만 필터, 결정성 키로 "같은 설정
재실행" 경고(같은데 다르면 비결정성 의심), 성공/실패 기준 대조. 대상 개수(2 대 N)는 열린 결정. 상태:
1개면 "하나 더 담기", 다른 축(symbol/tf)이면 경고.
필요한 데이터: 각 실행 `backtest_run` 설정 컬럼, `backtest_summary` 지표·판정, 겹침용 `CHART_SUMMARY`/
`PORTFOLIO_PNL`, params_json 안정 키 순서.

## 6. P2 화면 상세 — 실행 관리(전부 dry-run)

### 6.1 트리거 폼(RunConfig 구성)

목적: `RunConfig`를 폼으로 구성해 서버측 pydantic 검증을 통과시키고 백테스트를 트리거(모의).

```
┌─ 새 백테스트 트리거 ──────────────── [ DRY-RUN · 실주문 아님 ] ─┐
│ 전략[Vessel Reference▾] 지원tf:1h 필수지표:EMA9,EMA21,ATR       │
│ run_name[ema-cross-oos-c] (소문자·숫자·하이픈,24자)             │
│ 심볼[BTCUSDT] 거래소[binance] market(○spot ●futures)           │
│ tf(●1h) data_source[ohlcv_futures] 기간[07-01]→[12-31] seed[0]  │
│ 초기자본[10000] 사이징(●risk_based 1.00% ○pct[―]) 지표(●auto)   │
│ 파라미터 atr_stop[2.0] reward_risk[2.5] leverage[1]             │
│ trigger_feed[tf_candle 고정] fill_timing[next_bar 고정]         │
│ □스윕 □사전등록      [설정 미리보기·config_hash] [트리거(모의)]  │
└──────────────────────────────────────────────────────────────────┘
```

폼 제약(스키마 직접): risk_based면 risk_per_trade만(0<x≤0.01)·pct는 비움, pct면 position_size_pct만
(0<x≤1.0)·framework_compliant 꺼짐, trigger_feed는 tf_candle만·m1_subcandle 비활성, fill_timing은
next_bar 고정, run_name은 카탈로그 더 엄격 규칙(24자·소문자 kebab) 적용. 컴포넌트: shadcn Form(react-
hook-form+zod, OpenAPI 생성 타입 정렬), Command 콤보박스, DateRangePicker, RadioGroup, 확인 Dialog
(config_hash 되비추기). 상호작용: 전략 선택 시 tf·파라미터·지표 자동 제약, "설정 미리보기"로 config_hash
사전 계산(같은 해시 기존 run 있으면 중복 경고), 상세의 "같은 설정 재실행"에서 프리셋 열기.
필요한 데이터: `strategy_registry`, `RunConfig` 스키마(OpenAPI 생성), config_hash 미리보기(열린 결정),
데이터 원천 가용 범위(정합 보완 `/data-sources/{ds}/coverage`).

### 6.2 실행 큐·상태 모니터

```
┌─ 실행 큐 ─────────────────────────── (SSE 스트림) ─┐
│ ●ema-cross-oos-c RUNNING 00:42 [████████░░] 4362/4374│
│ ✓atr-tighten COMPLETED PF0.94 Sortino0.71 [상세]     │
│ ✗range-block FAILED "data_source range 부족"         │
│ ⚠old-run-x ORPHANED [진단]                           │
└──────────────────────────────────────────────────────┘
```

컴포넌트: Card 행·Progress·Badge·Button, SSE를 TanStack Query 캐시에 반영. 상호작용: 스트림 진행 갱신,
완료→상세, 실패→트리거 폼 수정 재시도, ORPHANED 진단.
필요한 데이터: `backtest_run`(status·started/finished_at·error_message), 진행 스트림, 완료 시 요약 일부.

### 6.3 스윕 빌더·결과 그리드

```
┌─ 스윕 결과 · S-...-a ── 지표[Sortino▾] [히트맵|목록] n=25 ─┐
│         reward_risk→ 1.5 2.0 2.5 3.0 3.5                    │
│  atr 1.5│ 0.8 1.1 1.4 1.2 0.9  (Recharts 히트맵)           │
│      2.0│ 1.2 1.6 2.1▲1.9 1.5  ←최적(클릭→상세)            │
│ 선택셀→[비교담기][상세]  경고: 과적합 위험·OOS 재검증 권장  │
└────────────────────────────────────────────────────────────┘
```

컴포넌트: Select·ToggleGroup·액션 바. 차트: 2축은 Recharts 히트맵, 1D는 라인/막대. 상호작용: 지표 전환,
셀 클릭→상세, 다중 셀 비교 담기, 최적 강조+과적합 경고, 사전등록 묶기. 상태: RUNNING 셀 진행·FAILED 회색·
3축 이상은 두 축+슬라이서.
필요한 데이터: sweep_id 묶음 `backtest_run`+params_json·status, 각 `backtest_summary` 지표·gate_verdict·
oos_degradation, 스윕 축 정의.

### 6.4 사전등록 폼

목적: 실행 전 가설·성공/실패 기준을 잠가 사후 합리화를 막고 판정을 검증 가능하게.

```
┌─ 사전등록 ─────────────── 잠그면 수정 불가(immutable) ─┐
│ 가설[range 저신뢰 진입 차단으로 tail_loser 감소]        │
│ 약점[tail_loser 과다] 주지표[sortino▾] 방향(●높을수록)  │
│ 성공 {"sortino":">=1.8","tail_loser_ratio":"<=0.08"}    │
│ 실패 {"sortino":"<1.4"} 연계[FINDING-102] by[vincent]   │
│                            [초안 저장] [잠금(확인)]      │
└─────────────────────────────────────────────────────────┘
```

컴포넌트: shadcn Form, 구조화 입력/JSON 편집기, 잠금 재확인 Dialog. 카탈로그 쓰기를 하므로 연구 API 쓰기
범위 전제(열린 결정). 상호작용: 초안 저장·잠금 확인·실행 연결·완료 후 5.7에서 관측 대 기준 자동 대조.
필요한 데이터: `backtest_prereg` 전 컬럼·locked_at, primary_metric 선택지 검증, 연계 finding.

## 7. 전략 참조

전략 목록은 `strategy_registry`(display_name·strategy_id·version·supported_timeframes·required_
indicators_json·min_history·is_active·is_deprecated), 단건은 description·default_params_json·module_
path·class_name과 이 전략 실행 목록(`backtest_run` strategy_id 필터). 지표 개수는 계약이 아니라 "현재
등록분"임을 표현으로 밝힌다.

## 8. P3·P4 개념 — 라이브(안전 프레이밍)

별도 하네스 프리셋·자격증명 결정 선행. P3 라이브 모니터는 `wallet_db` 읽기 전용으로 포지션·주문·잔고·
손익만 보이고 제어 요소가 없다(호박색 도메인·"읽기 전용·인증 필요" 배너·읽기에도 인증 강제). P4 라이브
제어는 실주문·지갑 쓰기가 가능한 유일 코드인 별도 hardened `live-control`이며 UI는 신뢰되지 않는 쪽(적색
도메인·잠금 배너). 심층 방어: 최소 실제 인증·내용 되비추기·심볼 재입력·서버측 idempotency·상시 kill
switch, 최대 주문 크기·심볼 허용 목록·rate limit은 UI가 아니라 서비스가 강제, append-only 감사 로그.
가장 마지막에 만들며 골격까지만 고정.

## 9. P0 최초 사용 경험(착수 지점)

최소 화면 둘: 카탈로그 실행 목록(4.1)과 실행 요약(4.2, 개요 탭). 콘솔을 열면 목록이 created_at 내림차순
으로 뜨고 필터로 좁혀 행 클릭→요약(정체성·핵심 지표·판정·건강도·비용 분해)을 한 화면에서 본다. 두 실행을
골라 비교 바스켓에 담는 동작까지 P0(비교 화면 자체는 P1). 이 최소 경험은 카탈로그 두 테이블만 요구하므로
Evidence 파일 접근 결정 없이 가장 먼저·가장 싸게 출시할 수 있다.

## 10. 열린 결정

컴포넌트 라이브러리(shadcn 대 Mantine), 정보 밀도 기본값, 드로다운 차트 렌더(Lightweight 동기 페인 대
Recharts), 실행 비교 대상 개수(2 대 N), 연구 API 카탈로그 쓰기 범위(사전등록·태그·노트), run_name 규칙
divergence(`RunConfig` 128자 대 카탈로그 24자 kebab), 타임존·로케일 표시, Evidence 파일 물리 접근 배치.
통합 목록과 단계별 gating은 `docs/webui-predev-plan.md` 3절에 있다.
