# A4 — 타입·config·DB 생성 인벤토리 (trading-system, 읽기 전용 분석)

> Phase A 분석 산출물. 목적: 세 실행 모드가 공유할 도메인 타입의 **이식 원천**을 목록화하고, 신규
> 프로젝트의 `backtest_db` 생성 방식을 현행 `init-scripts/`·인프라에서 도출하며, git에 평문 커밋된
> 비밀번호를 목록화하고 저장 방식 변경을 정한다. 이 노트는 인벤토리다 — 타입 필드 확정(core-lib 클래스 설계)이나
> `backtest_db` 스키마 확정(DB 설계)은 여기서 하지 않는다. 모든 코드 사실은 `파일:줄`로 인용한다.

원천 리포(읽기 전용): `trading-system` = signal-service·wallet-service. 제거 대상인 `services/backtest/`·
`services/replay/`는 **읽지 않았다**. `crypto_data`·`config_db`는 이 리포가 아니라 crypto-data-hub가
생성하며(현행 `init-scripts/01-init-databases.sql` 머리말 전제), 여기서는 이름·역할만 기록한다.

---

## 1. 제약사항·방향

**AS-IS/TO-BE 구분 규약.** 이 노트는 【기존 코드 분석(AS-IS)】(2절)과 【새 시스템 방향(TO-BE)】(3절)을 **물리적으로
나눈다.** 2절은 기존 코드의 **사실·`파일:줄` 인용만** 담고(무엇이 이미 있는가), 3절은 새 시스템의 **결정·방향만**
담는다(무엇을 만들 것인가). 기존 코드는 **가능하면 가져오되(값·구조·패턴), 재활용은 필수가 아니다** — 3절의 각
항목이 `재활용`(기존에서 가져옴) 또는 `신규`(새로 만듦)를 명시한다.

**방향(요약, 상세는 3절).** 검증된 현행 도메인 타입·금액 정밀도 상수는 신규 공유 코어 단일 타입 정의처의 **출발점**
이다(강제 이식이 아니라 선택 재활용). 통합 캔들 타입은 현행에 없어 **신규로 만든다**. 여러 서비스가 같은 최상위
패키지명을 써서 생기는 네임스페이스 충돌은 신규 공유 패키지를 충돌 없는 이름으로 두어 해소한다. `backtest_db`는
이름을 계승하되 스키마는 신규, read-only 역할은 신설, 평문 비밀은 저장 방식을 변경한다(값 유지).

**보존 불변식(신 타입 계층이 강제).**
- **Decimal 단일 변환 관문.** 지표→전략→신호 경로는 float64로 흐르고, 체결 진입점(`Broker.submit()`)에서
  `Decimal(str(x))` + quantize를 **딱 한 번** 수행한 뒤 이후는 Decimal 전용이다. `Decimal(float)` 직접 변환은
  금지(이진 잡음이 스탑 끝자리를 뒤집어 캔들 내 트리거·해시가 흔들린다).
- **캔들 타입 계층 검증.** 시각 단조 증가(중복·역순 없음), `close_time = open_time + timeframe`,
  `high ≥ max(open, close)`, `low ≤ min(open, close)`, `price > 0`, `volume ≥ 0`. 갭은 채우지 않고 표시한다.
- **연구 데이터·운영 DB 분리.** run meta는 wallet/signal 운영 DB와 분리된 전용 `backtest_db`에 두고, 대시보드
  조회용 **read-only 역할**을 writer와 별도로 둔다.

---

## 2. 기존 코드 분석 (AS-IS) — 사실·인용만

> 여기서는 **기존 코드에 무엇이 있는지**만 기록한다. 무엇을 만들지·무엇을 재활용할지는 3절(TO-BE)에서 정한다.
> 현행 wallet 엔티티는 전부 평범한 `@dataclass`이며 **frozen이 아니다**(가변); 모든 금액·수량·가격·수수료·손익
> 필드는 `Decimal`이다.

### 2.1 통합 캔들 타입 — 현행 없음

현행 signal·wallet 어디에도 `Candle`/`OHLCV`/`Kline`/`Bar` 값 타입이 **없다**. OHLCV는 pandas `DataFrame`으로만
존재한다(컬럼 `time, open, high, low, close, volume`; 로더 `OHLCVDataLoader`
`signal-service/domain/data/ohlcv_loader.py:184`, 전략 규약 `signal-service/domain/strategies/base.py:243`).
적재원 `crypto_data.ohlcv_futures`의 컬럼은 `time·symbol·exchange·timeframe·open·high·low·close·volume·
quote_volume·trade_count·ingest_time`다(수집기 인벤토리 참조).

### 2.2 금액 정밀도·enums — `wallet-service/domain/value_objects.py`

모두 `str, Enum`(문자열 값). Decimal 상수·quantize 헬퍼가 같은 파일에 있다.

| 기존 요소 | 현행 위치 | 값·비고 |
|---|---|---|
| `money` 정밀도 상수 | `value_objects.py:11-19` | `ZERO`·`ONE_HUNDRED`; quantize 스케일 `Q_PRICE`=8dp·`Q_AMOUNT`=8dp·`Q_PERCENT`=2dp·`Q_RATIO`=4dp·`Q_FEE_RATE`=4dp |
| `quantize_*` 헬퍼 | `value_objects.py:23-85` | `quantize_price/amount/percent/ratio/fee_rate`, 전부 `ROUND_HALF_EVEN` |
| `OrderType` | `value_objects.py:102` | `MARKET`·`LIMIT`·`STOP_MARKET`·`TAKE_PROFIT_MARKET`·`TRAILING_STOP_MARKET` |
| `OrderSide` | `value_objects.py:113` | `BUY`·`SELL` |
| `OrderStatus` | `value_objects.py:119` | 활성 `NEW`·`PARTIALLY_FILLED`·`PENDING_CANCEL`; 종료 `FILLED`·`CANCELLED`·`EXPIRED`·`REJECTED`·`FAILED`; `is_terminal()`(:142)·`is_active()`(:153) |
| `PositionSide` | `value_objects.py:280` | `LONG`·`SHORT`·`BOTH` |
| `MarginType` | `value_objects.py:287` | `CROSS`·`ISOLATED` |
| `MarketType` | `value_objects.py:293` | `SPOT`·`FUTURES` |
| `Exchange`·`QuoteCurrency`·`TradingMode`·`WalletStatus` | `value_objects.py:168·175·88·94` | `UPBIT/BINANCE`·`KRW/USDT`·`LIVE/PAPER`·`ACTIVE/…` |

같은 파일에 `convert_symbol()`(`value_objects.py:196`)·상태 매핑(`UPBIT_STATUS_MAP:159`·`BINANCE_STATUS_MAP:183`)도
있다(거래소 어댑터 관심사). `ExitReason` enum은 현행에 **없다**.

### 2.3 엔티티 — `wallet-service/domain/entities/` (Decimal, 가변 `@dataclass`)

| 기존 엔티티 | 현행 위치 | 핵심 필드·불변식 |
|---|---|---|
| `Order` | `entities/order.py:53` | `id·wallet_id·signal_id·order_type·side·symbol·quantity:Decimal·price:Optional[Decimal]·filled_quantity·average_filled_price·status·fee:Decimal·client_order_id:UUID·market_type·position_side·reduce_only·close_position·stop_price·time_in_force`. `__post_init__`: str→Enum 강제·`quantity>0`·reduce_only/close_position 상호배타. 상태기계 `VALID_TRANSITIONS`(:22), 체결 메서드 `mark_as_filled`(:144)·`mark_as_partially_filled`(:184)·`mark_as_cancelled`(:223), `remaining_quantity`(:327) |
| `Position` | `entities/position.py:14` | `wallet_id·symbol·quantity·average_price·total_cost·current_price/unrealized_pnl·side·market_type·leverage·margin_type·margin·entry_price·mark_price·liquidation_price·funding_fee_total`(전부 Decimal). `__post_init__`: `total_cost ≈ quantity×average_price`(허용 `0.01`). `calculate_liquidation_price`(:100) 기본 유지증거금률 `Decimal("0.004")`; `update_price`(:58)·`add_quantity`(:124)·`reduce_quantity`(:154) |
| `ClosedTrade` | `entities/closed_trade.py:12` | `source_type`(`live/paper/backtest`)·`symbol·side·market_type`·진입 `entry_price/entry_quantity/entry_time`·청산 `exit_price/exit_quantity/exit_time/exit_reason`·손익 `gross_pnl/total_fee/slippage/net_pnl/return_pct`·`leverage·funding_cost·liquidated`·문맥 `wallet_id·backtest_run_id·strategy_id/name·hold_duration_seconds·signal_confidence/reason`. `net_pnl`은 수수료·슬리피지 반영. **`r0`(최초 위험) 필드는 없다** |
| `Fill` | 현행 없음 | 별도 Fill 엔티티가 **없다** — 체결은 `Order` 상태 전이로만 표현 |
| `EquitySnapshot` | `entities/equity_snapshot.py:28` | `time·source_type·cash_balance/position_value/total_equity·wallet_id/backtest_run_id·drawdown_pct·peak_equity·open_positions`. 회계 항등식(`cash+position=equity`) 근거 |
| `FundingPayment` | `entities/funding_payment.py:27` | `wallet_id·symbol·position_side·funding_rate·position_amount·payment_amount`(부호: +수취/−지불)·`funding_time`. 이산 펀딩 정산 기록 |
| `TrailingState` | `entities/trailing_state.py:8` | `initial_risk(R0)·trailing_stage(0-3)·trailing_high/low·current_stop_price·entry_price·last_ema9/21·last_atr` |
| `Wallet` | `entities/wallet.py:15` | 계정 상태·리스크 설정(`position_size_pct`·`stop_loss_pct`·`take_profit_pct`·`default_leverage`) |

### 2.4 신호 타입 — signal-service (Decimal/float 경계)

| 기존 타입 | 현행 위치 | 필드·비고 |
|---|---|---|
| `TradingSignal`(전략 출력) | `signal-service/domain/strategies/base.py:36` | `signal_type:SignalType·symbol·price:float·confidence:float(0~1)·timestamp·metadata·reason·market_type·leverage·stop_loss:Optional[float]=None·take_profit:Optional[float]=None`. 전략 `analyze` 반환형. **float**. 방향 필드 `signal_type`을 가진다 |
| `SignalType` | `base.py:24` | `BUY·SELL·HOLD`(방향: BUY=long, SELL=short) |
| `Signal`(영속 엔티티) | `signal-service/domain/entities/signal.py:13` | `wallet_id·strategy_id·assignment_id·signal_type(BUY/SELL/HOLD)·symbol·price:Decimal·confidence:Decimal·status·created_at/sent_at/processed_at`. `__post_init__`: signal_type·`price>0`·status 7종·confidence[0,1] 검증. **Decimal** |

**관측: float/Decimal 경계.** 전략 계층 `TradingSignal`은 float, 실행/지갑 계층은 Decimal이다. 즉 현행 코드에 이미
"순수 계산은 float64, 체결 진입에서 한 번 Decimal로 캐스팅"하는 경계가 실재한다(신 시스템의 Decimal 단일 변환
관문 위치와 일치).

### 2.5 DB 생성 현황 — `init-scripts/` (라이브)

라이브 `init-scripts/01-init-databases.sql`이 세 DB와 writer 유저를 생성한다. `backtest_db`·`backtest_writer`가
**이미 존재**한다.

```sql
-- init-scripts/01-init-databases.sql (검증)
CREATE DATABASE wallet_db;            -- 19행 부근
CREATE DATABASE signal_db;
CREATE DATABASE backtest_db;          -- 이미 존재
CREATE USER wallet_writer   WITH PASSWORD '<평문-커밋>';   -- 26행
CREATE USER signal_writer   WITH PASSWORD '<평문-커밋>';   -- 27행
CREATE USER backtest_writer WITH PASSWORD '<평문-커밋>';   -- 28행 (writer 전용)
-- backtest_db 권한 (57~64행): backtest_writer 에 전권
\c backtest_db
GRANT ALL PRIVILEGES ON DATABASE backtest_db TO backtest_writer;
GRANT USAGE, CREATE ON SCHEMA public TO backtest_writer;
```

- **read-only `backtest_reader` 역할은 어디에도 없다**(`init-scripts/` 전역 grep 0건). 현재 `backtest_db`에는
  writer(`backtest_writer`)만 있다. wallet_db에는 read-only `report_reader`가 있으나
  (`init-scripts/02-init-wallet-db.sql` 597행) 다른 DB다.
- 아카이브된 legacy 초기화 `init-scripts/archive/07-init-backtest-db.sql`이 같은 DB·유저를 만들며 평문
  비밀번호를 담는다(같은 파일 16행, `CREATE USER backtest_writer WITH PASSWORD '…'` — 값은 마스킹). 이는 현행
  `init-scripts/01-init-databases.sql`로 대체된 구 스킴이다.
- 구 backtest 서비스가 런타임에 `backtest_db`에 만들었을 legacy **테이블**은 서비스 **미열람**이라 여기서
  확인하지 않는다(폐기 목록 인벤토리가 이름으로만 식별). 라이브 `01-init-databases.sql`이 만드는 것은 빈 DB·
  writer 유저뿐이다.
- 파일 번호 규약: 라이브 `init-scripts/` 루트는 `01-init-databases.sql`(DB·유저)·`02-init-wallet-db.sql`(wallet_db)·
  `03-init-signal-db.sql`(signal_db)이다(파일명 앞 두 자리가 실행 순서). 마이그레이션 미러 디렉터리
  `init-scripts/wallet-service/`가 날짜별 하위(2026-03-19 … 2026-04-02)로 존재한다.
- 교차 리포: `config_db`·`crypto_data`는 crypto-data-hub가 생성하고(`init-scripts/01-init-databases.sql` 머리말
  전제), signal·backtest가 읽는다. `data_reader`·`config_reader` 역할도 그 리포 소관이라 여기 정의가 없다.

### 2.6 config 스키마 — 각 서비스 `core/config.py`

두 서비스 모두 `pydantic_settings.BaseSettings`, `env_file=".env"`, `case_sensitive=False`, `extra="ignore"`.
접속 문자열은 코드에서 조립하지 않고 env-var URL(`postgresql+asyncpg://…`)로 통째 주입한다.

| 서비스 | 설정 | 위치 | DB/역할 |
|---|---|---|---|
| wallet | `database_url`(별칭 `DATABASE_URL`) | `wallet-service/core/config.py:18` | → `wallet_db` |
| wallet | `config_db_url`(별칭 `CONFIG_DB_URL`) | `wallet-service/core/config.py:19` | → `config_db` |
| wallet | `auto_create_tables:bool=True` | `wallet-service/core/config.py:46` | dev `create_all` |
| signal | `database_url` | `signal-service/core/config.py:18` | → `signal_db` |
| signal | `crypto_data_url`(별칭 `CRYPTO_DATA_URL`) | `signal-service/core/config.py:19` | → `crypto_data`(읽기) |
| signal | `config_db_url` | `signal-service/core/config.py:20` | → `config_db` |

두 서비스 config에 `backtest_db` 참조는 없다(제거 대상 backtest 서비스만 참조했다). 관측된 DB 이름:
`wallet_db·signal_db·crypto_data·config_db`. 공용/shared `core/config.py` 패키지는 없고 서비스마다 자기 것을 소유한다.

### 2.7 평문 커밋 비밀 위치

git에 평문 커밋된 것과 디스크 `.env`(gitignore로 추적 제외이나 실운영 비밀 보유). 값은 마스킹(앞 2자 + `***`).

| 파일:줄 | 키 | 마스킹 | 성격 | git 추적 |
|---|---|---|---|---|
| `init-scripts/01-init-databases.sql:26/27/28` | `wallet_writer`/`signal_writer`/`backtest_writer` PW | 실 비밀 | 라이브 생성 | 추적됨 |
| `init-scripts/02-init-wallet-db.sql:597` | `report_reader` PW | `re***` | 라이브(약함) | 추적됨 |
| `init-scripts/archive/07-init-backtest-db.sql:16` | `backtest_writer` PW | `ba***` | legacy(대체됨) | 추적됨 |
| `signal-service/.env`·`.env.live`·`.env.dev:4-6` | `DATABASE_URL`/`CRYPTO_DATA_URL`/`CONFIG_DB_URL` DSN | 실 비밀 | 운영 | 미추적(디스크) |
| `wallet-service/.env`·`.env.live`·`.env.dev:4-5` | `DATABASE_URL`/`CONFIG_DB_URL` DSN | 실 비밀 | 운영 | 미추적(디스크) |
| `wallet-service/docker-compose.e2e.yml:10,52,53` | `POSTGRES_PASSWORD` / 테스트 DSN | `te***` | 테스트 | 추적됨 |
| `wallet-service/core/config.py:37` | `secret_key` 기본값 | `yo***` | 플레이스홀더 | 추적됨 |

---

## 3. 새 시스템 방향 (TO-BE) — 결정·방향만

> 여기서는 **무엇을 만들지**만 정한다. 각 타입은 2절의 기존 요소를 `재활용`(값·구조를 가져옴)하거나 `신규`(새로
> 만듦)로 명시한다. **재활용은 필수가 아니다** — 신뢰할 수 없거나 인프라와 얽힌 기존 요소는 신규로 대체한다.

### 3.1 `core_lib.types` 목표

신규 `core_lib.types`가 담을 대상. `재활용`은 2절 기존 요소에서 값·구조를 가져옴, `신규`는 새로 만듦을 뜻한다.

- **`Candle`(신규).** 현행 원천 없음(Chapter 2.1 참고). `Candle(symbol, exchange, timeframe, open_time, close_time, open, high,
  low, close, volume, quote_volume?, trade_count?)` — `crypto_data.ohlcv_futures` 컬럼과 1:1 대응 가능. 위 1의
  캔들 검증 불변식을 이 타입이 강제한다.
- **`money`(재활용).** 정밀도 상수·quantize 값을 2.2에서 가져옴: `Q_PRICE/AMOUNT`=8dp·`Q_PERCENT`=2dp·
  `Q_RATIO/FEE_RATE`=4dp·`ROUND_HALF_EVEN`·`ZERO`.
- **enums(재활용 + 신규).** `OrderType/Side/Status·PositionSide·MarginType·MarketType`는 2.2 값을 재활용.
  `ExitReason`은 **신규**(현행 없음).
- **`Order`·`Position`(재활용 가능, 필수 아님).** 2.3 필드·검증(`quantity>0`·`total_cost≈qty×avg`·Isolated MMR
  `0.004`)을 가져올 수 있으나, 라이브 인프라와 얽힌 부분은 순수 타입으로 재구성한다.
- **`Trade`(신규 성형).** 2.3 `ClosedTrade`를 계승하되 **`r0`(최초 위험) 추가**. 신규 필드라 성형이다.
- **`Fill`(신규).** 현행 원천 없음(Chapter 2.3 참고). 체결 사실을 명시 타입으로 신설.
- **`TradingSignal`(재활용 + 신규(성형)).** 2.4 signal `TradingSignal`을 공유 표준으로 승격하되 **판단 전용(수량·방향
  필드 없음)** 으로 성형한다 — 방향은 Decision·Order가 소유. 현행이 가진 방향 필드 `signal_type`을 떼는 것이
  성형의 핵심이며, 이 발산은 타입 클래스 설계가 확정한다.
- **불변: Decimal 단일 변환 관문.** float64가 지표→전략→신호를 흐르고, `Broker.submit()`에서 `Decimal(str(x))`+
  quantize 1회(현행 float/Decimal 경계 2.4와 일치). `Decimal(float)` 금지.

`convert_symbol`·상태 매핑(Chapter 2.2 참고)은 코어 타입이 아니라 포트/어댑터 관심사로 재검토한다(현 스코프 재활용 대상 아님).
`Wallet`·`TrailingState`(Chapter 2.3 참고)는 실행/리스크 설정·트레일링 소관이라 코어 값 타입에 넣지 않는다(트레일링은 현
스코프 유보).

### 3.2 `backtest_db` 생성 계획

**결정: DB 이름 `backtest_db` + writer 역할 `backtest_writer`를 유지(개명하지 않음).** 라이브
`init-scripts/01-init-databases.sql`에 이미 프로비저닝돼 있고(Chapter 2.5 참고), 생성 규약이 legacy가 쓰는 이름의 재발명을
금하기 때문이다. 제거 대상 backtest 서비스의 `backtest_db` 정의는 **계승 원천이 아니라** 이름 확인용일 뿐이며,
스키마는 이 계획이 계승하지 않는다.

신규 작업(출처 = `init-scripts/` 패턴 + 인프라, 2.5·2.6):
1. **read-only `backtest_reader` 역할 신설.** 대시보드 조회용. `report_reader`(wallet_db)·`config_reader`
   (crypto_data)와 같은 패턴으로 `GRANT SELECT`만 부여. 현재 없으므로 반드시 추가한다(Chapter 2.5 참고).
2. **신규 마이그레이션 디렉터리 `init-scripts/backtest-service/`.** 현행 `init-scripts/wallet-service/`의 날짜별
   미러 구조를 따른다. `backtest_db` meta 스키마 자체(`backtest_run`·`backtest_summary`·`backtest_prereg`·
   `backtest_tag`의 컬럼·타입·키·제약)는 DB 설계 단계에서 확정한다 — 여기서는 생성 방식만 고정한다.
3. **legacy 잔재 정리.** 아카이브 `07-init-backtest-db.sql`(Chapter 2.5 참고)은 대체 완료 처리한다. 구 backtest 서비스가
   `backtest_db`에 런타임 생성했을 legacy 테이블(미열람 식별, 2.5)은 신규 스키마 배선 시 인벤토리 후 드롭하거나
   신규 스키마와 분리한다.
4. **인프라 계층은 두 서비스와 동일.** SQLAlchemy 2.x async + `Base.metadata`, dev용 `AUTO_CREATE_TABLES=true`
   (→ `create_all`), `pydantic-settings`의 `DATABASE_URL`(backtest_db). config 패턴은 현행과 같다(Chapter 2.6 참고).
5. **접속 규약.** Docker 컨테이너는 host PostgreSQL에 `host.docker.internal`로 접속.
6. **카탈로그 규약(동작, 필드 아님).** `run_id`는 Engine이 `backtest_db` 시퀀스로 **단독 발급**해 SQLite 파일명에
   넣는다(병렬 스윕 채번 경합·파일명 충돌 차단). 결정성 검증 해시는 SQLite **파일 바이트가 아니라** 정렬된 행의
   **정규화 직렬화**(wall-clock 제외)로 산출한다. 이 두 동작은 DB 설계·Engine 설계 단계에서 정책으로 확정한다.

새 파일 번호는 지침의 "01~06"을 문자 그대로 따르지 말고 구현 시점 라이브 루트의 실제 최고 번호 다음(현재 기준
`04-…`)으로 정한다(Chapter 4 참고).

### 3.3 비밀 저장 방식 변경

**용어.** 이하 "변경"은 비밀번호 **저장 방식을 바꾸는 것**(커밋 파일 하드코딩 → `.env` 주입)을 뜻하며, 비밀
**값 자체의 교체**는 포함하지 않는다(기존 값은 유지 — 아래 결정).

**결정(사용자 확정).**
- **기존 암호는 그대로 사용한다.** git에 평문 커밋된 기존 DB 비밀번호의 **값을 바꾸지 않고** 계속 쓴다. 로컬 전용
  dev DB(localhost/`host.docker.internal`·사설 저장소·폐기 가능 데이터)라 git 노출의 실무 위험이 낮다는 판단이다.
  이는 지침의 "커밋 값 재사용 금지·값 교체" 규약에서 벗어나는 **의도적 조정**이며, 값 교체를 강제하지 않는다.
- **저장 방식은 변경한다.** 강도·노출과 무관하게, **앞으로 새 비밀은 커밋 파일(`init-scripts/` 등)에 하드코딩하지
  않고 `.env`(gitignore) 주입으로 둔다.** `.env` 계열(signal·wallet·crypto-data-hub)은 이미 이 방식이다.

**성격 구분.** git에 **커밋된** 것(`init-scripts/`·`docker-compose.e2e.yml`, 2.7)과 `.env` 계열로 갈린다. 저장 방식
변경은 **신규 비밀부터** 적용하고(커밋 파일 대신 `.env`), 기존 커밋 값은 위 결정대로 유지한다. `.env` 계열은 이미
올바른 방식이라 손대지 않는다. 예외로 crypto-data-hub `.env`의 실 외부 API 키(`NEWS_API_KEY`)는 외부 유료 서비스
자격증명이라 유출 정황이 있으면 그때 값을 바꾼다(이 역시 커밋된 것은 아니고 git 노출과 별개다).

**실행 인계.** 기존 `backtest_writer`(Chapter 2.5 참고 — `init-scripts/01-init-databases.sql` 28행에서 생성) 값은 유지한다. 신설
`backtest_reader`는 **새 자격증명**이므로 저장 방식 변경을 적용해 비밀을 `.env`로만 주입한다. 저장 방식 변경의
실제 수행·범위는 채택·검증(부록) 단계의 크리덴셜 산출물이다.

---

## 4. 블로커·확인·드리프트

- **통합 Candle 타입 부재(예상된 gap).** 현행에 값 타입이 없어 신규로 만든다(Chapter 2.1·3.1 참고). 이식이 아니라 신설이다.
- **`backtest_reader` 역할 부재(gap).** read-only 역할 분리 요구에 비해 현행 `backtest_db`에는 writer만 있다 →
  신설이 생성 계획의 필수 항목이다(Chapter 2.5·3.2 참고).
- **init-scripts 파일 번호 불일치(비블로커).** `init-scripts/`의 SQL 파일은 **이름 앞 두 자리 숫자**(`NN-…sql`)가
  실행 순서를 정한다 — 여기서 "번호"는 그 **파일명 앞 번호**다. 현재 라이브 루트에는 `01-init-databases.sql`·
  `02-init-wallet-db.sql`·`03-init-signal-db.sql` 세 개뿐이라 **최고 번호가 03**이다. 그런데 생성 규약 서술은
  "현행 01~06 다음 번호에 추가"라 해 라이브에 없는 04~06을 전제하는데, 그 번호대는 `init-scripts/archive/`에
  남은 구 스킴(`03~07`)의 흔적일 뿐이다. 따라서 신규 backtest DB·역할 생성 SQL의 **파일 번호는 "01~06"을 문자
  그대로 따르지 말고, 구현 시점 라이브 루트의 실제 최고 번호 다음**(현재 기준 `04-…`)으로 정하고, 스키마
  마이그레이션은 `init-scripts/backtest-service/` 디렉터리에 둔다.
- **`.env` 미추적이나 실비밀 보유.** signal·wallet `.env`는 gitignore로 추적 제외지만 실운영 비밀을 담는다 —
  이미 `.env` 방식이라 저장 방식 변경 대상이 아니고, 값도 유지한다(Chapter 3.3 참고).
- **wallet_db 내부 `backtest_runs` 테이블 혼동 주의.** `init-scripts/02-init-wallet-db.sql` 334행의 `backtest_runs`는
  wallet_db 안의 legacy **리포팅** 테이블(`source_type` `live/paper/backtest` 체크, `backtest_run_id` FK)로, 신규
  전용 `backtest_db` meta와 **다른 것**이다. 신규 backtest_db 스코프에 넣지 않는다.

---

## 5. Traceability (설계 표준 요구 ↔ 이 노트 절)

| 이 노트의 절 | 충족하는 표준 요구(이름) |
|---|---|
| 1, 3.1 | Decimal 단일 변환 관문(`Broker.submit`에서 1회), `Decimal(float)` 금지 — 현행 float/Decimal 경계(Chapter 2.4 참고)와 일치 |
| 1, 3.1 | 캔들 타입 계층 검증(시각 단조·`close_time=open_time+tf`·`high≥max(o,c)`·`low≤min(o,c)`·`price>0`·`volume≥0`) |
| 2, 3.1 | 도메인 타입·금액 정밀도의 단일 정의처(AS-IS 이식 원천 → TO-BE 목표, 재활용/신규 명시, 통합 Candle 신설) |
| 1, 3.2 | 연구 데이터·운영 DB 분리 — `backtest_db` 전용, read-only `backtest_reader` 신설 |
| 2.5, 3.2 | `backtest_db` 생성은 두 서비스와 동일 패턴(init-scripts 번호 SQL + 마이그레이션 디렉터리 + SQLAlchemy async), 이름 계승 |
| 3.2 | `run_id` 단독 발급·정규화 Evidence 해시(파일 바이트 아님, wall-clock 제외) — 동작 규약 확정 지점 |
| 2.7, 3.3 | 평문 커밋 비밀 목록(AS-IS) → 저장 방식 변경(TO-BE, 기존 값 유지·신규 비밀 `.env` 주입) |

**정합성 확인 대상:** 기존 코드 분석(2절, AS-IS)과 새 시스템 방향(3절, TO-BE)이 물리적으로 갈렸는지, TO-BE 각
타입이 재활용/신규를 명시하고 재활용을 강제하지 않는지, `backtest_db` 생성 계획이 제거 대상 backtest가 아니라
`init-scripts/`+인프라(Chapter 2.5·2.6 참고)에서 도출됐는지(이름 계승·스키마 신규·`backtest_reader` 신설·legacy 잔재 드롭·비밀
저장 방식 변경이 모두 명시), 공용 타입 이식 원천이 실제 `파일:줄`로 자기완결한지, 하드 불변식(Decimal 단일 변환
관문·캔들 검증·연구/운영 DB 분리)이 보존됐는지. 이 노트는 이후 타입 클래스 설계가 필드를 확정하고, DB 설계가
`backtest_db` 스키마·역할·ERD를 그리며, 채택 단계가 크리덴셜 저장 방식을 변경하도록 재인벤토리 없이 입력을 제공한다.
