# v2 데이터베이스 프로비저닝

루트 `docker-compose.yml`은 v2가 소유하는 PostgreSQL 16 + TimescaleDB
인스턴스만 시작한다. 초기화 스크립트는 새 볼륨에서 데이터베이스 5개,
애플리케이션 역할 8개, `crypto_data` 하이퍼테이블 2개와 2000일
retention 정책 2개, 7일 후 압축 정책 2개, 연속 집계 5개, 그리고 v2
서비스 카탈로그를 만든다. v1 또는 crypto-data-hub의 데이터 행은 읽거나
복사하지 않는다.

## 최초 기동

실제 비밀을 출력하거나 추적 파일에 기록하지 말고 현재 셸의 비밀
주입 수단으로 `POSTGRES_PASSWORD`를 설정한다. v1이 사용할 수 있는 기본
5432 대신 loopback의 55432에만 게시한다.

```bash
export POSTGRES_PASSWORD='<v2 disposable admin secret>'
export V2_POSTGRES_PORT=55432
docker-compose --env-file /dev/null \
  --project-name trading-system-v2-db up --detach --wait
```

init SQL은 애플리케이션 역할에 비밀번호를 넣지 않는다. 실제 서비스를
시작하기 전에 같은 일회용 컨테이너의 관리자 세션에서 미추적 비밀을
사용해 필요한 LOGIN 역할(`data_writer`, `config_reader`,
`backtest_writer` 등)에 비밀번호를 설정한다.

## 스키마 검증

검증 테스트는 DSN이나 저장소 `.env`를 읽지 않는다. Compose가 이
저장소에서 시작한 `timescaledb` 컨테이너인지 Docker label로 확인한 뒤
그 컨테이너 내부의 로컬 소켓만 사용한다.

```bash
V2_DB_PROVISIONING_TEST=1 \
V2_COMPOSE_PROJECT_NAME=trading-system-v2-db \
.venv/bin/pytest -q tests/test_db_provisioning.py
```

검증 후 일회용 볼륨까지 삭제한다.

```bash
docker-compose --env-file /dev/null \
  --project-name trading-system-v2-db down --volumes
```

Docker 엔진을 사용할 수 없는 환경에서는 최소한 Compose 렌더링과 검증
코드의 정적 컴파일을 수행한다. 실제 TimescaleDB SQL 구문과 정책
카탈로그 검증을 대체할 수 없으므로, Docker가 있는 인수 환경에서 위
opt-in 테스트를 반드시 다시 실행한다.

```bash
POSTGRES_PASSWORD='<non-production placeholder>' \
  docker-compose --env-file /dev/null config --quiet
.venv/bin/python -m compileall -q tests/test_db_provisioning.py
```

`signal_db`에는 읽기 전용 Adaptee 레지스트리와 signal-service가 쓰는
`trading_signals` 운영 테이블만 만든다. `wallet_db`는 빈 데이터베이스와
`wallet_writer` 역할만 준비한다. wallet 테이블, 현물 OHLCV, backfill,
지표, macro, news 스키마는 이 프로비저닝 범위에 포함하지 않는다.
