# 전략 작성 Agent 사용법

이 문서는 **사람이 쓴 전략 기술 문서를 이 플랫폼에서 도는 전략으로 옮기는 방법**을 적는다.

규칙 자체는 `docs/strategy-authoring-contract.md`가 소유한다. 이 문서는 그 규칙을 어떻게
쓰는지만 다루며, 둘이 어긋나면 규범이 이긴다. 왜 이렇게 만들었는지는
`docs/fullspec/strategy_authoring_workflow_design.md`와
`docs/fullspec/strategy_registration_mcp_design.md`에 있다.

## 1. 전체 흐름

전략 기술 문서를 건네면 절차가 그것을 구조로 옮기고, 필요한 재료와 능력이 있는지 확인한 뒤
둘 중 하나를 돌려준다. 하나는 등록되어 백테스트가 도는 전략이고, 다른 하나는 **무엇 때문에
막혔고 무엇이 있으면 풀리는지를 적은 보고**다.

막히지 않으면 구현과 등록 문장 생성과 사전 점검을 거쳐 화면에서 실행하는 데까지 간다. 그
뒤에 검산 절차가 계산이 문서와 맞는지 독립적으로 되짚는다.

**등록 행을 데이터베이스에 넣는 마지막 한 걸음만은 사람이 한다.** 도구는 문장을 만들어 주고
점검까지 해 주지만 운영 데이터베이스에 쓰지 않는다. 이유는 6절에 있다.

## 2. 무엇을 준비하는가

**전략 기술 문서 하나면 된다.** 형식은 자유롭다. 유튜브 강의를 정리한 글도 되고 가설과 검증
순서를 갖춘 연구 설계서도 된다. `docs/samples_for_strategy_agent/`에 두 종류가 예시로 있다.

문서가 완전할 필요는 없다. **비어 있는 값은 지어내지 않고 물어보므로**, 모르는 것은 모르는
채로 두는 편이 낫다. 값을 채워 넣으면 그 값으로 재고 만다.

## 3. 부르는 법

```
/author-strategy docs/samples_for_strategy_agent/00.TCT_MultiTF.md
```

슬래시로 부르지 않고 "이 문서로 전략 만들어 줘"라고 해도 같은 절차가 실린다. 전략 기술
문서나 매매 아이디어 정리본을 건네는 상황이면 자동으로 붙는다.

구현이 끝나고 백테스트를 한 번 돌린 뒤에는 검산을 따로 부른다.

```
/verify-strategy
```

**검산은 구현 코드를 읽고 확인하는 것이 아니다.** 원본 문서와 계산 표준에서 값을 다시 끌어와
직접 계산해 대조한다. 구현할 때 한 오해를 확인할 때 되풀이하지 않으려는 것이다.

## 4. 돌아오는 답을 읽는 법

막혔다면 사유가 **세 갈래로 갈려서** 온다. 이 구분이 절차의 핵심이다.

| 갈래 | 무슨 뜻인가 | 당신이 할 일 |
|---|---|---|
| 문서가 비워 둔 값 | 문서에 숫자가 없거나 `TODO`다 | 값을 정해 준다 |
| 계산 재료의 부재 | 필요한 지표나 패턴이 등록되어 있지 않다 | 그 재료를 먼저 만들지 결정한다. 전략 작업이 아니라 플랫폼 작업이다 |
| 실행 능력의 부재 | 플랫폼이 그 요구를 표현할 수 없다 | 요구를 바꾸거나 플랫폼을 넓히는 별도 작업을 연다 |

**셋 다 걸리는 문서가 보통이다.** 그래서 가장 앞선 하나만 보고하지 않고 걸린 것을 전부 적는다.
하이킨아시를 만든 뒤에야 "하루 5회 제한도 안 됩니다"를 듣는 일이 없게 하려는 것이다.

**전부 막혀도 되는 부분이 있으면 함께 온다.** 문서가 실험 순서를 정해 두었다면 지금 능력으로
어디까지 잴 수 있는지 밝힌다. 이때 **문서와 달라지는 점을 빠짐없이 적고 당신의 승인을
받는다.** 조용히 바꿔 구현하면 문서가 물은 것과 다른 것을 잰 뒤 답을 얻었다고 믿게 된다.

## 5. 직접 물어보기

전략을 만들기 전에 "이런 게 되나"를 확인하고 싶으면 직접 물어도 된다. 저장소 뿌리에서 돈다.

```
.venv/bin/python -m trading_plugins.facts <조회> [인자]
```

결과는 언제나 JSON이고, 실패하면 종료 코드가 0이 아니면서 `error` 하나를 담은 JSON이 온다.

```
$ .venv/bin/python -m trading_plugins.facts declaration strategy nope
{"error": "unknown strategy: nope"}
```

### 5.1 `capabilities` — 플랫폼이 표현할 수 있는 것

```
.venv/bin/python -m trading_plugins.facts capabilities
.venv/bin/python -m trading_plugins.facts capabilities exit.partial
```

스물일곱 항목이 있고 이름만 보아도 무엇을 묻는지 알 수 있다. `exit.partial`은 부분 익절이
되는지, `series.multi_timeframe`은 상위 timeframe을 볼 수 있는지, `risk.between_trade_rules`는
하루 손실 한도 같은 거래 간 규칙이 있는지다.

**값만 보지 말고 문장을 읽는다.** 값은 참거짓이나 숫자일 뿐이고, 왜 그런지와 어느 경로에
해당하는지는 문장에 있다.

### 5.2 `series` — 지금 등록된 지표와 패턴

```
.venv/bin/python -m trading_plugins.facts series
.venv/bin/python -m trading_plugins.facts series EMA
```

```
{'kind': 'indicator', 'name': 'EMA', 'params': {'period': 200}, 'min_history': 200,
 'pinned_impl': 'technical_indicators_calc_spec.md §0.3 (SMA seed, recursive)'}
```

**지표는 이름과 parameter 조합 단위로 등록된다.** 위에서 보듯 `EMA`는 9와 21과 55와 200 넷만
있으므로 50봉 EMA는 선언할 수 없다.

**채택 근거는 지표에만 실린다.** 패턴은 공통 판만 있고 항목마다의 근거가 없으므로,
`docs/references/candlestick_pattern_calc_spec.md`를 읽어 정의를 확인해야 한다는 문구가 함께
온다.

### 5.3 `deployed` — 지금 배포된 전략과 정책

```
.venv/bin/python -m trading_plugins.facts deployed strategy
.venv/bin/python -m trading_plugins.facts deployed money_management
```

```
{"kind": "money_management",
 "items": [{"identifier": "manual", "class_name": "ManualMoneyManagement",
            "module_path": "trading_plugins.money_management.manual"}, ...],
 "faults": []}
```

**`faults`를 반드시 본다.** 불러오지 못한 파일이 여기 사유와 함께 남는다. 파일 하나가 잘못돼도
나머지는 그대로 배포되므로, 이 자리를 보지 않으면 빠진 것을 눈치채지 못한다.

### 5.4 `declaration` — 그 클래스가 스스로 밝힌 것

```
.venv/bin/python -m trading_plugins.facts declaration strategy <전략 id>
.venv/bin/python -m trading_plugins.facts declaration money_management <mode>
```

전략이면 선언한 series와 최소 이력과 지원 timeframe과 판단 방식, `StrategyProfile` 전부,
parameter schema가 온다. 정책이면 설정마다의 기본값 유무와 판과 두 capability와 **그 정책이
선언한 요구 전부**가 온다.

**조회는 서술하고 거부하지 않는다.** 요구를 하나도 선언하지 않은 정책이나 기본값 없는 설정을
가진 정책도 그대로 서술한다. 실행되지 않는 것을 조회했을 때 침묵하면 진단이 막히기 때문이다.

### 5.5 `registration_sql` — 등록 문장 만들기

```
.venv/bin/python -m trading_plugins.facts registration_sql \
    strategy <전략 id> "<표시 이름>" "<설명>" <true|false> [기본값 JSON]
```

선언에서 나오는 열은 클래스에서 읽고 **나머지는 인자로 받는다.** 자세한 것은 6절에 있다.

### 5.6 `catalog_precheck` — 등록 행과 클래스가 맞는지

```
.venv/bin/python -m trading_plugins.facts catalog_precheck strategy <전략 id>
```

```
{"passed": true,
 "checks_performed": ["catalog identity and declaration", "catalog lifecycle",
                      "adapter construction"],
 "not_checked": ["execution timeframe support", "series resolution", "policy input arity",
                 "live-signal capability", "return-type violation on the first decision"],
 "findings": []}
```

**`not_checked`를 반드시 읽는다.** 통과는 "등록과 선언이 맞는다"는 뜻이지 "이제 실행된다"는
뜻이 아니다. 실행 timeframe 지원과 series 해석과 정책 입력 개수와 라이브 신호 capability는
실행 설정이 정해진 뒤에야 검사되고, 반환 형 위반은 첫 판단을 받아야 드러난다.

## 6. 등록까지 가는 길

등록은 네 걸음이고 **마지막 하나는 사람이 한다.**

첫째, `registration_sql`로 문장을 만든다. 둘째, `catalog_precheck`로 그 행이 클래스와 맞는지
본다. 셋째, 만들어진 문장을 `init-scripts/signal-service/<날짜>/` 아래 파일로 옮기면서 기존
파일과 같은 껍데기를 씌운다. 넷째, 운영자가 그 파일을 적용한다.

**셋째 걸음에서 껍데기가 필요한 이유가 있다.** 도구는 문장 하나만 낸다. 기존 등록 파일에 있는
`\set ON_ERROR_STOP on`과 `BEGIN`과 `COMMIT`은 psql이 읽는 파일의 모양이고 **psql 메타 명령은
psycopg로 보낼 수 없어** 도구가 낼 수 없다. 문장 하나는 그 자체로 원자적이라 동작에는 문제가
없고, 파일로 옮길 때만 감싸면 된다.

### 6.1 무엇이 사람 몫인가

선언에서 나오지 않는 값이 넷이고 전략은 다섯이다.

**표시 이름과 설명**은 사람이 정한다. 클래스 docstring으로 대신 채우지 않는다. 그것은 사실
조회가 아니라 등록 문구를 고르는 일이기 때문이다.

**`is_active`는 인자이며 기본값이 없다.** 이것이 켜고 끄는 스위치이므로 기본값을 두면 도구가
운영 결정을 대신하게 된다.

**전략의 `default_params_json`은 클래스 기본값의 사본이 아니다.** 화면과 스윕이 쓰는 **시작값
제안**이고 클래스 기본값과 일부러 다를 수 있다. 그래서 인자로만 들어가며, 주지 않으면 빈
객체가 된다.

### 6.2 폐기된 전략을 되살리지 않는다

만들어진 문장은 충돌했을 때 **선언과 표시 열만 갱신하고 `is_active`와 `is_deprecated`는 건드리지
않는다.** 그래서 폐기해 둔 전략에 같은 문장을 다시 적용해도 폐기가 유지된다. 활성화와 폐기는
등록과 다른 일이며 별도 운영 문장으로 한다.

### 6.3 문장이 실제 PostgreSQL에서 도는지 보기

표시가 붙은 시험이 있고 기본 실행에서는 건너뛴다. 돌리려면 명시적으로 고른다.

```
.venv/bin/python -m pytest services -q -m integration -k facts_integration_postgres
```

**이것은 데이터베이스에 쓰는 일이다.** 이름에 임의 문자열이 붙은 임시 schema를 만들어 그
안에서만 표를 세우고 끝나면 지운다. 기존 표와 행은 건드리지 않고 데이터베이스를 만들거나
지우지 않는다. 그래도 쓰기이므로 **돌리기 전에 승인을 받는다.**

## 7. MCP로 쓰기

같은 조회 여섯을 MCP 도구로도 쓸 수 있다. `.mcp.json`에 `trading_plugin_facts`로 등록되어
있고 저장소의 `.venv`로 뜬다.

**절차 자체는 MCP를 필요로 하지 않는다.** skill이 가리키는 것은 명령줄이므로 서버가 없어도
그대로 돈다. MCP가 유용한 것은 다른 클라이언트가 같은 사실을 도구로 부를 때다.

**서버는 뜰 때 읽은 코드로 답한다.** 전략 파일이나 사실 모듈을 고쳤으면 **서버를 다시 띄워야**
새 내용을 답한다. 명령줄은 부를 때마다 새 프로세스라 그 함정이 없다.

## 8. 자주 틀리는 자리

**이름이 같아도 정의는 다를 수 있다.** registry의 `pat_hammer`는 TA-Lib 0.7.1 정의이지
"아랫꼬리가 몸통의 두 배"가 아니다. 문서가 이름만 적고 정의를 주지 않았다면 재료가 갖춰진
것이 아니라 **무엇을 잴지 정해야 하는 상태**다.

**지표는 조합 단위로 등록된다.** 문서에 흔한 숫자가 없으면 거기서 먼저 걸린다.

**체결은 언제나 다음 봉이다.** 판단한 그 봉의 종가로 들어가는 모형은 없다. 그것은 규범이
금지한 미래 참조라 플랫폼이 일부러 막고 있다. 문서가 종가 진입을 전제했다면 재는 것이 달라진다.

**백테스트를 통과해도 paper에서 거절될 수 있다.** 실거래 쪽에는 백테스트에 없는 관문이 따로
있고 백테스트 결과에는 그 거절이 반영되어 있지 않다. `capabilities risk.paper_execution_guard`가
그것을 적어 둔 자리다.

**거래 사이를 보는 규칙이 백테스트에 없다.** 하루 손실 한도도 연패 중단도 하루 거래 횟수
상한도 없고, 전략은 지난 거래의 결과를 입력으로 받지 않아 스스로 셀 수도 없다.

**상위 timeframe은 series로만 볼 수 있다.** 4시간봉 EMA를 15분봉 실행에서 읽는 것은 되지만,
4시간봉 원본 캔들을 봉마다 훑는 것은 되지 않는다. 전략에 들어오는 캔들은 실행 timeframe
하나다.

**거래당 위험은 1퍼센트가 상한이다.** 문서가 2퍼센트를 권해도 그 값으로는 실행되지 않는다.

## 9. 샘플 둘로 보는 실제 판정

`docs/fullspec/strategy_sample_verdicts.md`에 두 문서의 판정이 통째로 적혀 있다. 요지만 옮긴다.

**`00.EMA_StochasticRSI.md`는 세 갈래 모두에 걸린다.** 하이킨아시가 없어 트리거가 성립하지
않고, 하루 5회 제한과 고정 비율 보호가격을 표현할 수 없으며, 값 넷이 비어 있다. 하이킨아시를
등록하는 것만으로도 부족한데, 문서가 EMA를 하이킨아시 종가 위에서 계산하라고 하지만 **등록된
지표는 모두 실행 캔들에서 계산하기 때문이다.**

**`00.TCT_MultiTF.md`는 여러 timeframe이 막힘이 아니다.** 4시간봉 series는 지금도 된다. 막힌
것은 종목 셋 동시 운용과 부분 익절과 트레일링과 거래 간 리스크 규칙, 그리고 4시간봉 구간을
만드는 계산 재료다. **다만 문서가 정한 첫 실험 단계는 승인 둘과 빈 값 하나를 채우면 지금도
잴 수 있다.**

이 판정들이 낡지 않도록 근거를 시험이 붙들고 있다. 하이킨아시가 등록되거나 부분 청산이 생기면
그 시험이 깨지고 판정을 다시 내리게 된다.

## 10. 이 절차가 하지 않는 것

**운영 데이터베이스에 쓰지 않는다.** 등록 문장을 만들고 점검까지 하지만 적용은 사람이 한다.

**막힌 것을 우회해 구현하지 않는다.** 능력이 없으면 없다고 보고하고 멈춘다.

**등록된 지표나 패턴을 전략 안에 다시 구현하지 않는다.** 원시 캔들 비교와 전략 고유 규칙만
전략이 직접 계산한다.

**문서가 비운 값을 지어내지 않는다.** 물어보고 기다린다.

**성적이 좋다고 채택하지 않는다.** 검산을 통과하지 못하면 채택하지 않는다.

## 11. 막혔을 때 확인하는 순서

전략이 실행되지 않으면 위에서 아래로 확인한다.

첫째, `deployed`로 그 전략이 발견되었는지와 `faults`가 비어 있는지 본다. 파일을 고친 뒤
서비스를 다시 띄우지 않으면 예전 내용이 계속 돈다.

둘째, `declaration`으로 클래스가 무엇을 선언했는지 본다.

셋째, `catalog_precheck`로 등록 행과 선언이 맞는지 본다. 여기서 걸리면 등록 문장을 다시 만들어
적용한다.

넷째, 여기까지 통과했는데 실행이 거부되면 `not_checked`의 다섯을 의심한다. 실행 timeframe이
지원 목록에 있는지, 선언한 series 조합이 등록되어 있는지, 정책이 변동성 입력을 정확히 하나
선언했는지, 라이브 신호라면 정책이 계좌 상태와 무관하다고 선언했는지, 그리고 선언한 반환
방식과 실제로 돌려주는 값이 같은지다.
