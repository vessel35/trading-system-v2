# WebUI 개발 전 설계 — 통합·정합·착수 계획

이 문서는 WebUI의 개발(스캐폴딩 코드) 직전까지의 사전 설계를 하나로 묶는다. 방향은
`docs/webui-direction.md`, 백엔드 API 설계는 `docs/webui-api-design.md`, 정보구조·UI/UX 설계는
`docs/webui-ux-design.md`에 있다. 이 문서는 그 둘의 교차 정합(모든 화면의 데이터 요구가 API로
충족되는지), 정합에서 드러난 보완 사항, 사람이 정할 열린 결정의 통합 목록, 그리고 개발 착수용 0단계
계획을 담는다.

## 1. 교차 정합 결과

UI/UX 설계의 각 화면이 명시한 "필요한 데이터" 체크리스트를 백엔드 API 설계의 엔드포인트와 대조했다.
두 설계가 같은 데이터 모델(카탈로그 `backtest_db`, 21개 엔티티 Evidence, `RunConfig`, `strategy_registry`)에
근거해 나왔기 때문에 대부분 정합한다. 화면 대 엔드포인트 대응은 다음과 같다.

- 카탈로그 실행 목록은 `GET /api/v1/runs`(요약 조인·필터·정렬·페이지)로 충족된다.
- 실행 요약·개요는 `GET /api/v1/runs/{id}`와 `GET /api/v1/runs/{id}/summary`로 충족된다.
- 자본곡선·드로다운 탭은 `/equity`·`/chart-summaries`·`/drawdown-episodes`·`/executions`로 충족된다.
- 거래 탭과 거래 상세 드로어는 `/trades`·`/outcome-buckets`·`/executions`·`/funding-settlements`·
  `/trade-features`·`/candidate-events`·`/positions`로 충족된다.
- 신호·의사결정 탭은 `/signals`·`/decisions`·`/candidate-events`·`/missed-opportunities`·
  `/indicator-snapshots`로 충족된다.
- 무결성·비용 탭은 `/integrity-checks`와 요약으로, 조건부 기대값·연구 노트 탭은
  `/conditional-expectancy`·`/findings`·`/prereg`로 충족된다.
- 실행 비교는 `/runs:compare`와 각 실행의 `/equity`(또는 `/chart-summaries`)로 충족된다.
- 실행 관리(트리거·큐·스윕·사전등록)는 `/run-config:validate`·`POST /runs`·`/runs/{id}/events`(SSE)·
  `/status`·`/sweeps`·`/sweeps/{id}`·`/runs/{id}/prereg`·`/runs/{id}/tags`로 충족된다.
- 전략 참조는 `/strategies`·`/strategies/{id}`와 `/runs?strategy_id=`로 충족된다.

## 2. 정합에서 드러난 보완(API 설계에 추가할 엔드포인트 세 개)

교차 정합에서 UI/UX가 요구하나 API 설계가 명시하지 않은 엔드포인트 세 개를 찾았다. 이를 API 설계의
보완으로 확정한다.

첫째는 **원천 캔들(OHLCV) 조회**다. 차트 탭(UI/UX 설계 5.4)은 캔들스틱 위에 지표와 매매 마커를
겹치므로 원천 OHLCV가 필요한데, API 설계의 엔드포인트 목록에는 캔들을 서비스하는 경로가 없었다.
보완: `GET /api/v1/runs/{run_id}/candles`를 두어 해당 run의 심볼·시간대·구간(그리고
`SOURCE_DATA_SNAPSHOT`의 range)에 맞는 OHLCV를 `crypto_data` 읽기 전용 역할로 제공한다. 표시 범위
창(window) 파라미터(`from`·`to`·`limit`)를 받는다. 이 엔드포인트는 시장 원자료를 읽어 낼 뿐 지표를
재계산하지 않는다.

둘째는 **데이터 원천 가용 범위 조회**다. 트리거 폼(6.1)은 기간이 원천 데이터 범위 밖이면 경고해야
하는데 그 범위를 줄 경로가 없었다. 보완: `GET /api/v1/data-sources/{data_source}/coverage`(또는
심볼·시간대 질의 파라미터)로 `crypto_data`의 가용 시작·끝을 읽어 낸다. 읽기 전용이다.

셋째는 **태그 패싯 조회**다. 카탈로그 목록(4.1)의 태그 필터는 존재하는 `tag_type`·`tag_value`
집합을 알아야 하는데 그 목록을 줄 경로가 없었다. 보완: `GET /api/v1/tags/facets`로 `backtest_tag`의
distinct `(tag_type, tag_value)`와 개수를 낸다.

이 셋을 제외하면 모든 화면의 데이터 요구가 API 설계의 기존 엔드포인트로 충족된다. 세 보완 모두
읽기 전용(캔들·범위·패싯)이라 단일 표준·안전 도메인 원칙과 충돌하지 않는다.

## 3. 열린 결정 통합 목록 (사람 확정)

두 설계가 각각 남긴 열린 결정을 통합하고 중복을 정리했다. 각 항목에 **언제 결정이 필요한지**(어느
단계 착수를 막는지)를 붙여, 0단계 개발은 대부분의 결정 없이 시작할 수 있음을 분명히 한다.

**0단계(P0) 착수를 막지 않는 것 — 나중에 정해도 됨:**
- 컴포넌트 라이브러리 확정(shadcn/ui 대 Mantine). 설계는 shadcn/ui 전제. 착수 후에도 교체 가능하나
  초기에 정하면 좋다.
- 정보 밀도 기본값(조밀 대 편안). 토글로 둘 수 있어 P0에서 임의 기본값으로 시작 가능.
- 타임존·로케일 표시(UTC 대 로컬, 통화 표기). 금액은 방향 문서대로 문자열로 받아 표시만 한다.
- `run_name` 규칙 divergence: `RunConfig`는 128자·혼용 허용, 카탈로그 `backtest_run`은 24자·소문자
  kebab으로 더 좁다. 트리거 폼(P2)은 더 엄격한 카탈로그 규칙을 적용하도록 설계됨. 두 스키마를
  일치시킬지는 P2 착수 전 확정.

**1단계(P1, Evidence 분석) 착수 전 확정 필요:**
- **Evidence SQLite 파일 물리 접근 배치.** `web-api`가 `backtest_run.evidence_path`의 파일에 닿는
  방식(실행 호스트 동일 대 공유 볼륨). P1의 모든 상세 탭이 이 접근을 전제로 설계됨. P0(카탈로그
  두 테이블만)은 이 결정 없이 출시 가능하므로, 이 결정은 P1 착수 전까지 미룰 수 있다.
- 드로다운 차트 렌더 방식(자본곡선과 시간축 정렬을 위해 Lightweight Charts 동기화 페인 대 방향
  문서의 Recharts 배정). 시간축 정렬 품질 대 라이브러리 분담의 절충.
- 실행 비교 대상 개수(2개 A/B 대 N개 다중 겹침).

**2단계(P2, 실행 관리) 착수 전 확정 필요:**
- **연구 API의 카탈로그 쓰기 범위.** 사전등록·태그 부여·연구 노트는 `backtest_db`(카탈로그)에 쓰기를
  요구한다. 이 콘솔이 이 셋에 한정된 쓰기 권한을 갖는지 확정. 라이브 DB 읽기 전용 정책과는 별개의,
  카탈로그에 대한 제한적 쓰기 문제다. dry-run 트리거 자체가 이미 `backtest_writer`를 쓰므로 범위를
  명확히 하면 된다.
- `run-config:validate`가 `config_hash` 미리보기까지 낼지(중복 실행 탐지 가치 대 지표 해석 부분
  실행 복잡도).
- dry-run 진행률 세밀도(카탈로그 상태 전이 수준의 굵은 통지 대 실행 진입점에 진행률 콜백 추가 —
  후자는 `backtest-service` 변경 수반, 이 사전 설계 범위 밖).

**3·4단계(라이브) 착수 전 — 별도 프리셋 결정 선행:**
- 라이브 모니터링(읽기)조차 `wallet_db` 접근을 요구한다. 현재의 백테스트 전용·읽기 전용·dry-run
  프리셋 밖의 별도 하네스 프리셋과 자격증명·역할 결정이 선행되어야 착수 가능하다. 지갑 스키마 컬럼과
  라이브 엔드포인트 정책, 인증 강도(제어의 2차 확인 수준)는 그 프리셋이 정해진 뒤 별도 설계한다.
  이 문서는 라이브를 개념·안전 게이트·프리셋 의존까지만 확정했다.

## 4. 개발 착수용 0단계(P0) 계획

0단계는 가장 빨리·가장 싸게 쓸모를 내는 최소 종단이며, 카탈로그 두 테이블만으로 성립해 위 열린
결정 대부분(특히 Evidence 파일 접근·라이브 프리셋)을 필요로 하지 않는다.

**백엔드 최소 엔드포인트(다섯):** `GET /api/v1/runs`(요약 왼쪽 조인·필터·정렬·페이지),
`GET /api/v1/runs/{run_id}`(헤더 상세), `GET /api/v1/runs/{run_id}/summary`(요약 0..1),
`GET /api/v1/health`, 그리고 FastAPI가 자동으로 내는 `GET /openapi.json`(TypeScript 클라이언트
생성원). 전략 목록(`GET /api/v1/strategies`)은 유용하나 첫 골격에는 선택.

**프런트엔드 최소 화면(둘):** 카탈로그 실행 목록(UI/UX 설계 4.1)과 실행 요약(4.2, 상세의 개요 탭).
목록에서 필터로 좁히고 행 클릭으로 요약을 열어, 정체성·핵심 지표·판정·데이터 건강도·비용 분해를 한
화면에서 본다. 두 실행을 골라 비교 바스켓에 담는 동작까지 P0에 포함하되 비교 화면 자체는 P1에서 붙인다.

**착수 순서(권장):** 정보 구조·내비게이션 셸(사이드바·상단 바·명령 팔레트·비교 바스켓·전역 필터)을
먼저 세우고, 위 다섯 엔드포인트로 FastAPI 골격과 OpenAPI→TypeScript 생성 파이프라인을 걸고, 카탈로그
목록과 실행 요약 두 화면을 생성된 타입으로 붙인다. 이 종단이 통과하면 이후 P1(Evidence 분석) 탭들을
같은 배관 위에 덧붙인다.

**단일 표준·안전 불변식(개발 전반에 유지):** API는 지표·판정을 재유도하지 않고 저장값을 읽거나
`core_lib`을 호출한다. Decimal 금액은 JSON 문자열로 오가고 프런트는 표시만 한다. 연구 평면은 라이브
제어 순환으로 들어가는 엣지를 코드 구조상 갖지 않으며, 실주문·지갑 쓰기는 별도 hardened
`services/live-control`에만 둔다.

## 5. 이 사전 설계의 산출물과 다음

이 스프린트는 세 문서로 개발 이전 설계를 완결한다 — 방향(`webui-direction.md`), 백엔드 API 설계
(`webui-api-design.md`), 정보구조·UI/UX 설계(`webui-ux-design.md`), 그리고 이 통합·정합·착수 계획.
다음 단계는 개발(스캐폴딩)이며, 위 0단계 계획이 그 착수점이다. 착수 전에 필요한 결정은 3절의 단계별
목록을 따르되, P0는 결정 없이 시작할 수 있다.
