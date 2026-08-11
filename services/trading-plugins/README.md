# Trading plugin facts

`trading_plugins.facts`가 전략·자금관리 정책의 배포 사실과 등록 산출물을 소유한다.
명령줄 인터페이스는 저장소 루트에서 다음처럼 실행한다.

```text
.venv/bin/python -m trading_plugins.facts <lookup> [args]
```

각 호출은 새 프로세스에서 파일을 import하므로 파일 변경 뒤에 별도 재시작이 필요하지 않다.

같은 여섯 lookup은 `trading_plugins.mcp_server`가 MCP tool로도 제공한다. 서버는 시작할 때
import한 모듈로 계속 답하므로 전략, 정책 또는 fact 파일을 바꾼 뒤에는 반드시 MCP 서버를
재시작해야 한다. 저장소의 `.mcp.json`은 이 서버를 `.venv/bin/python`으로 실행한다.

서버 의존성은 `pyproject.toml`의 `mcp>=1.29,<2`이다. 현재 저장소 가상환경에 직접
설치하려면 저장소 루트에서 다음을 실행한다.

```text
.venv/bin/python -m pip install 'mcp>=1.29,<2'
```

서버는 데이터베이스 연결 문자열이나 비밀을 받지 않으며 데이터베이스에 쓰지 않는다.
