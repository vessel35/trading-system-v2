# 다른 PC에서 이 작업을 이어가기 위한 안내

> 작성일 2026-11-03. 기준은 main의 커밋 d7e234c(PR #59 "일곱째 Agent 회차" 병합)다. 이 문서는
> 저장소 밖에 있어 `git clone`으로 따라오지 않는 것과, 새 PC에서 첫 Claude Code 세션을 열어
> 다음 작업을 시작하기까지의 순서를 적는다. 비밀 값(비밀번호, API 키, 접속 문자열)은 이 문서에
> 없고 앞으로도 적지 않는다. 이름만 적고 값은 비밀 저장소에서 가져온다.

## 1. 지금 상태

- main은 d7e234c다. 일곱째 Agent 회차(오렌지 매매 지표, Orange Web3)는 구현 불가 보고로 끝났고
  PR #59로 2026-09-29에 병합됐다. `.claude/OBJECTIVE.md`의 완료 조건은 모두 채워졌으므로, 다음
  작업을 정한 뒤 OBJECTIVE를 새로 써야 한다(6절).
- push되지 않은 작업은 없다. 작업 트리는 깨끗하고 main은 origin/main과 같다.
- 이 PC에만 있는 옛 브랜치 둘(`feat/strategy-authoring-workflow`, `docs/harness-codex-implements`,
  둘 다 2026-08-11)과 stash 둘은 내용이 폐기됐거나 다른 경로(PR #47)로 main에 들어갔으므로 옮기지
  않는다.
- 회차 기록은 `docs/fullspec/stage_3_1_acceptance_three_strategies.md` 5.9절, Agent의 막힘 보고는
  `docs/samples_for_strategy_agent/07.Orange_Web3_Band_Retest.md` 6절과 7절에 있다.

## 2. clone으로 따라오는 것

코드와 시험 전부, Claude Code 하네스(`.claude/HARNESS.md`, `.claude/OBJECTIVE.md`,
`.claude/settings.json`의 권한과 훅 등록, `.claude/hooks/`의 훅 셋, `.claude/skills/`의 skill 열일곱,
`.claude/agents/`의 미사용 정의 여섯), 프로젝트 MCP 설정 `.mcp.json`, 설계 문서 `docs/`, 데이터베이스
초기화 SQL `init-scripts/`, v2 데이터베이스용 `docker-compose.yml`, 파이썬 설치 목록
`services/requirements-dev.txt`, 웹 잠금 파일 `apps/web/package-lock.json`이다. 이것들은 아무것도
옮길 필요가 없다.

## 3. 저장소 밖에 있어 직접 옮겨야 하는 것

| 항목 | 이 PC의 위치 | 새 PC에서 할 일 |
|---|---|---|
| 환경 파일 `.env` | 저장소 루트(gitignore) | `.env.example`을 참고해 새로 쓴다. 이 PC의 파일이 가진 키는 `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `COLLECTOR_CONFIG_DB_URL`, `COLLECTOR_DATA_DB_URL` 여섯이다. 이 PC는 `PGHOST=localhost`, `PGPORT=5432`다. 값은 비밀 저장소에서 가져오고 파일은 커밋하지 않는다 |
| 개발용 PostgreSQL과 그 안의 자료 | `localhost:5432`(`.env` 주석은 "docker에 설치된 개발용 PostgreSQL 관리자 계정"이라고 적음) | 3.1절의 두 방법 가운데 하나로 옮긴다 |
| 과거 실행의 Evidence | `var/evidence/`(gitignore, 약 60 MB, SQLite 파일) | `backtest_db.backtest_run` 행이 이 파일들을 가리킨다. 데이터베이스를 복사(3.1절의 첫째 방법)하면 함께 복사해야 화면이 과거 실행을 연다. 과거 실행이 필요 없으면 생략한다 |
| 전역 지침 | `~/.claude/CLAUDE.md` | 그대로 복사한다(출력 양식 규칙) |
| 세션 메모리 | `~/.claude/projects/-Users-vincent-workspaces-CoinTrading-trading-system-v2/memory/`(`MEMORY.md`와 파일 50개) | 그대로 복사한다. 디렉터리 이름이 저장소 경로에서 만들어지므로, 새 PC에서도 `/Users/vincent/workspaces/CoinTrading/trading-system-v2`에 clone하거나, 다른 경로에 두면 그 경로에 맞게 디렉터리 이름을 바꾼다 |
| 서브에이전트 메모리 | `.claude/agent-memory/strategy-architect/`(gitignore, 파일 2개) | 하네스가 서브에이전트를 쓰지 않으므로 선택이다 |
| 로컬 설정 | `.claude/settings.local.json`(전역 git ignore) | 이 PC는 `disabledMcpjsonServers`로 `.mcp.json`의 서버 여섯을 모두 꺼 두었다. 새 PC에서 어떤 MCP를 켤지 정한 뒤 만들거나 생략한다 |
| 사용자 범위 MCP | `~/.claude.json` | `clickup`(HTTP, `https://mcp.clickup.com/mcp`, 브라우저 인증), `codex-cli`(`npx codex-mcp-server`), `perplexity`(`npx`) 셋을 `claude mcp add`로 다시 등록한다. `.mcp.json`의 서버가 요구하는 환경 변수는 `OPENAI_API_KEY`, `PERPLEXITY_API_KEY`, `WALLET_DB_RO_URL`, `SIGNAL_DB_RO_URL`, `CRYPTO_DATA_RO_URL`(읽기 전용 계정)이다 |
| Codex CLI | `~/.codex/`(`auth.json`, `config.toml`) | 설치한 뒤 `codex login`(ChatGPT 계정)으로 로그인한다. 리뷰 호출은 `~/.codex/config.toml`의 `model` 값을 그대로 넘기고 `reasoningEffort`를 `low` 이상으로 준다. 이 PC의 값은 2026-11-03 기준 `gpt-6.1-sol`이다(2026-09-24에는 `gpt-5.6-terra`였다). 자세한 것은 `.claude/HARNESS.md`의 "Reaching Codex" |
| Orca | 별도 앱 | Codex 호출의 대체 경로일 뿐이다. MCP가 동작하면 필요 없다 |

필요한 도구는 Python 3.12(이 PC는 3.12.10), Node 20과 npm(이 PC는 20.19.4와 11.8.0), `jq`(훅이 쓴다,
없으면 `python3`로 대신한다), `psql` 클라이언트, `gh`(GitHub 로그인, PR 생성에 쓴다), `git`이다.
3.1절의 둘째 방법을 쓰면 Docker도 필요하다. `gtimeout`(coreutils)은 있으면 test-gate 훅이 시간
제한에 쓰고 없어도 된다.

### 3.1 데이터베이스와 자료를 옮기는 두 방법

작성 시점에 이 PC의 PostgreSQL이 꺼져 있어 보유 자료의 범위(종목, 기간)는 확인하지 못했다. 옮기기
전에 서버를 켜고 아래 질의로 범위를 적어 둔다.

```sql
-- crypto_data
select exchange, symbol, timeframe, min(open_time), max(open_time), count(*)
from ohlcv_futures group by 1, 2, 3 order by 1, 2, 3;
select count(*), min(funding_time), max(funding_time) from funding_rates;
-- signal_db
select strategy_id from strategy_registry order by 1;
-- backtest_db
select count(*), max(created_at) from backtest_run;
```

**첫째 방법, 복사.** 이 PC에서 데이터베이스 다섯(`crypto_data`, `signal_db`, `backtest_db`,
`config_db`, `wallet_db`)을 `pg_dump`로 내려받아 새 PC의 PostgreSQL에 `pg_restore`로 올린다. 역할과
비밀번호는 덤프에 들어가지 않으므로 새 PC에서 다시 만든다. `var/evidence/`를 함께 복사한다. 과거
실행과 등록 행이 그대로 따라오므로 가장 빠르다.

**둘째 방법, 새로 만들기.** 저장소의 `docker-compose.yml`로 v2 TimescaleDB를 띄운다(루프백 55432
포트, 절차는 `init-scripts/README.md`). 새 볼륨이면 `init-scripts/`가 데이터베이스 다섯과 역할, 그리고
`06-init-signal-registry.sql`이 가리키는 전략 일곱과 정책의 등록 행을 자동으로 만든다. 1분봉 자료는
`services/collector`의 `backfill` 모드로 채운다(`services/collector/README.md`, 종목과 기간을 지정하며
`services/collector/.env.example`의 변수가 필요하다). 그런 다음 `.env`의 `PGPORT`를 55432로 맞춘다.
과거 실행은 따라오지 않는다.

이미 있는 데이터베이스에 등록 행만 다시 적용할 때는 `\ir` 경로가 파일 기준이므로 `init-scripts`
디렉터리 안에서 실행한다.

```bash
cd init-scripts && psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d signal_db -f 06-init-signal-registry.sql
```

## 4. 설치 순서

```bash
git clone git@github.com:vessel35/trading-system-v2.git /Users/vincent/workspaces/CoinTrading/trading-system-v2
cd /Users/vincent/workspaces/CoinTrading/trading-system-v2
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r services/requirements-dev.txt   # 저장소 루트에서 실행해야 editable 경로가 맞는다
(cd apps/web && npm ci)
```

그다음 `.env`를 쓰고(3절) 데이터베이스를 준비한다(3.1절). 아래 확인이 모두 통과하면 설치가 끝난 것이다.

```bash
# 저장소 루트 pytest. 2026-09-29의 main에서는 2,539 passed, 64 skipped였다.
# 개발 PostgreSQL이 꺼져 있으면 web-api 시험 13개가 503으로 실패한다(2026-09-27 관측).
.venv/bin/python -m pytest services -q
.venv/bin/ruff check services && .venv/bin/ruff format --check services
(cd services/core-lib && ../../.venv/bin/mypy)        # mypy는 서비스 디렉터리 안에서 돌린다
(cd services/backtest-service && ../../.venv/bin/mypy)
(cd services/trading-plugins && ../../.venv/bin/mypy)
(cd apps/web && npm test && npm run typecheck)
# 능력 목록에 일곱째 회차가 더한 항목이 보여야 한다.
(cd services/trading-plugins && ../../.venv/bin/python -m trading_plugins.facts capabilities | grep -c candles.resampled_timeframes)
# 배포 전 검사. exit 0에 판정 passed. signal_db에 연결하는 단계가 있어 데이터베이스가 없으면 판정이 incomplete로 남는다.
.venv/bin/python -m backtest_service.author_check bollinger-band-bounce
```

개발 서버 둘은 다음과 같이 띄운다. uvicorn의 `--reload-dir`에 core-lib와 backtest-service를 넣지
않으면 그 코드를 고쳐도 서버가 옛 코드를 들고 있으므로 반드시 넣는다.

```bash
.venv/bin/python -m uvicorn web_api.main:app --host 127.0.0.1 --port 8000 --reload \
  --reload-dir services/web-api/web_api \
  --reload-dir services/backtest-service/backtest_service \
  --reload-dir services/core-lib/core_lib --log-level info
(cd apps/web && npm run dev)   # 화면은 http://localhost:5173/ (vite가 IPv6 localhost에 붙으므로 127.0.0.1로는 열리지 않는다)
```

## 5. Claude Code 세션을 여는 순서

1. 저장소 루트에서 `claude`를 연다(이 PC는 2.1.317). SessionStart 훅 `guardrails.sh`가 하네스 규칙과
   OBJECTIVE를 주입한다.
2. 다음 작업을 정하고 `.claude/OBJECTIVE.md`를 새로 쓴다(6절). 그다음 문서 하단의 "Register with
   /goal" 블록을 `/goal`로 등록한다. 등록은 사람이 한다. 등록 없이는 진행하지 않는 것이 하네스 규칙이다.
3. 모델과 effort. 이 PC의 마지막 설정은 `/model`로 Opus 5.5 기본, `/effort`로 high였다.
   `.claude/settings.json`은 `"model": "opus"`를 고정한다.
4. 작업 규칙은 `.claude/HARNESS.md`가 전부다. 요약하면 설계를 쓰고 Codex 설계 검토를 받고, 이 세션이
   구현하고, QA(pytest, ruff, format, 서비스별 mypy, 웹은 npm test와 typecheck)를 녹색으로 만들고,
   Codex 코드 리뷰를 받아 Blocking 0을 확인한 뒤, 일부러 깨뜨리는 인수 시험을 하고, 새 브랜치에서
   커밋한다. push는 그 뒤에만 하고 권한 프롬프트가 사람의 확인이며 거부는 최종이다. 데이터베이스는
   읽기 전용이고, dev signal_db에 등록 SQL을 적용하는 쓰기만 사용자 승인 아래 한다.
5. 훅 셋이 자동으로 돈다. `secret-scan.sh`는 쓰기와 Bash에서 리터럴 비밀을 막는다(`${ENV_VAR}` 참조는
   허용). `test-gate.sh`는 Stop 때 `.py` 변경이 있으면 `.venv/bin/pytest`를 돌려 실패하면 멈춤을 막는다
   (180초를 넘기면 막지 않는다). `risk-guard.sh`와 `write-scope.sh`는 파일만 있고 등록되지 않았으며 다시
   등록하지 않는다.
6. Codex 호출은 `mcp__codex-cli__codex`(sandbox read-only, resetSession true) 또는
   `mcp__codex-cli__review`에 `~/.codex/config.toml`의 model을 명시한다. `review`는 `base`나 `commit`과
   `prompt`를 함께 받지 않으므로, 커밋된 diff에 지시문을 붙여 검토하려면 `codex`에 "`git diff <base>..HEAD`만
   검토하라"고 적어 보낸다. 120초가 지나면 호출이 배경으로 넘어가고 결과는 알림으로 온다.

## 6. 이어서 할 작업

**사용자가 정할 것 둘**([z8nrz7e6ha](https://app.clickup.com/t/z8nrz7e6ha)). 오렌지 지표 셋(중앙
추세선, 두 단계 편차 밴드, 연동형 RSI 게이지)의 정의를 어디서 얻어 등록할지, 그리고 그때까지 승인
필요 근사안(등록된 Bollinger Bands 20/2.0과 RSI 14로 중앙선과 색상과 문턱을 사람이 정하고, 리테스트를
빼거나 근사하고, 분할 청산 대신 전량 청산)을 별도 전략 작업으로 진행할지다.

**구현 항목**([z8nrz7e7zd](https://app.clickup.com/t/z8nrz7e7zd) 아래 하위 다섯).

1. 지표 셋의 정의 확보와 registry 등록([z8nrz7e7ze](https://app.clickup.com/t/z8nrz7e7ze)). 위 결정을
   기다린다.
2. 돌파 뒤 리테스트를 표현하는 능력, series의 앞 봉 값 또는 전략 상태
   ([z8nrz7e7zf](https://app.clickup.com/t/z8nrz7e7zf)). 결정과 무관하게 바로 설계를 시작할 수 있고,
   기존 전략 일곱의 교차 조건도 원문대로 되돌리므로 먼저 하는 것을 권한다.
3. 분할 청산 `exit.partial`([z8nrz7e7zg](https://app.clickup.com/t/z8nrz7e7zg)).
4. 가격 수준(중앙 추세선)에 두는 손절 정책([z8nrz7e7zh](https://app.clickup.com/t/z8nrz7e7zh)).
5. 여덟째 Agent 회차, 문서 07 재실행([z8nrz7e7zj](https://app.clickup.com/t/z8nrz7e7zj)). 앞의 넷이
   끝난 뒤.

**그 밖의 열린 항목.** `facts series`의 개념·계열 검색([z8nrz7e6hb](https://app.clickup.com/t/z8nrz7e6hb)),
시장·종목 범위 선언 구현([z8nrz7e41h](https://app.clickup.com/t/z8nrz7e41h)), Turtle 일봉 원천의
Evidence 기록([z8nrz7e4y0](https://app.clickup.com/t/z8nrz7e4y0)), 화면의 mode별 선언 값
([z8nrz7e40t](https://app.clickup.com/t/z8nrz7e40t)), 체결 뒤 청산 안전성 재검사
([z8nrz7e3k8](https://app.clickup.com/t/z8nrz7e3k8)), 기존 전략 일곱을 `StrategyBase` 보조 다섯으로 다시
맞추는 changeset, Agent가 쓴 05·06 모듈의 docstring 기록표 복사.

**먼저 읽을 문서.** `.claude/OBJECTIVE.md`(끝난 목표의 형식), `docs/roadmap-stage-3-1-plan.md`,
`docs/fullspec/stage_3_1_acceptance_three_strategies.md`(5.8절과 5.9절),
`docs/fullspec/author_check_and_scaffold_design.md`, `docs/strategy-authoring-contract.md`(4장, 6.6절),
`.claude/skills/author-strategy/SKILL.md`와 `.claude/skills/verify-strategy/SKILL.md`.

## 7. 새 PC 준비 확인 목록

- [ ] 저장소가 `/Users/vincent/workspaces/CoinTrading/trading-system-v2`에 있고 main이 d7e234c 이상이다.
- [ ] `.venv/bin/python --version`이 3.12이고 `services/requirements-dev.txt`가 설치됐다.
- [ ] `.env`에 키 여섯이 있고 PostgreSQL이 그 값으로 열린다(`signal_db`의 `strategy_registry`에 전략 일곱이 있다).
- [ ] 저장소 루트 pytest, ruff, format, 서비스별 mypy, 웹 test와 typecheck가 exit 0이다.
- [ ] `facts capabilities`에 `candles.resampled_timeframes`가 보인다.
- [ ] `author_check bollinger-band-bounce`가 exit 0에 판정 passed다.
- [ ] uvicorn과 vite가 뜨고 `http://localhost:5173/`에서 과거 실행 또는 새 실행이 보인다.
- [ ] `~/.claude/CLAUDE.md`와 메모리 디렉터리가 복사됐고 Claude Code 세션 시작 때 메모리 색인이 보인다.
- [ ] `claude mcp list`에 clickup, codex-cli, perplexity가 있고 Codex 호출이 `config.toml`의 model로 답한다.
- [ ] `gh auth status`가 로그인 상태다.
- [ ] OBJECTIVE를 새로 쓰고 `/goal`을 등록했다.
