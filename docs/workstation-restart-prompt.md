# 새 PC의 첫 Claude Code 세션에 붙여 넣을 프롬프트

> 외장 디스크 백업 `/Volumes/BackupDisk/Orca/trading-system-v2/`의 `RESTART_PROMPT.md`와 같은 내용이다. 백업의 `README-먼저읽기.md`가 복원 순서를, `docs/workstation-handover.md`가 옮길 것과 확인 목록을 적는다.

사용 조건: `restore.sh --with-secrets`를 돌렸고, 저장소 루트
(`/Users/vincent/workspaces/CoinTrading/trading-system-v2`)에서 `claude`를 열었다. 아래 프롬프트를 그대로
붙여 넣는다. 저장소를 다른 경로에 두었으면 경로 두 곳을 바꾼다.

---

이 PC는 포맷 후 새로 설치했고, 외장 디스크 `/Volumes/BackupDisk/Orca/trading-system-v2/`의 백업을
`restore.sh --with-secrets`로 복원한 직후다. 저장소는 `/Users/vincent/workspaces/CoinTrading/trading-system-v2`에
있다. 아래 순서로 진행하고, 각 단계의 결과를 실제 출력으로 보고해라. 추측으로 "됐다"고 하지 마라.

1. 백업 폴더의 `README-먼저읽기.md`와 `handover/workstation-handover.md`를 읽어라. 저장소의
   `.claude/HARNESS.md`, `.claude/OBJECTIVE.md`, 그리고 메모리 색인(`MEMORY.md`)이 보이는지 확인해라.
   메모리가 안 보이면 `~/.claude/projects/` 아래 디렉터리 이름이 저장소 경로와 맞는지 확인하고 고쳐라.
2. 저장소 상태를 확인해라. `git status`, `git log --oneline -5`, `git fetch origin` 뒤 main이 origin/main과
   같은지, 그리고 PR #60(`docs/workstation-handover`)이 병합됐는지 `gh pr view 60`으로 봐라. 병합됐으면
   로컬 main을 당겨라.
3. 설치 상태를 확인해라. `.venv/bin/python --version`이 3.12인지, 아니면 `python3.12 -m venv .venv` 뒤
   `.venv/bin/python -m pip install -r services/requirements-dev.txt`와 `apps/web`의 `npm ci`를 실행해라.
   `.env`가 저장소 루트에 있는지 확인하되 내용은 출력하지 마라.
4. 데이터베이스를 확인해라. `.env`의 PGHOST와 PGPORT로 `signal_db`에 접속해 `strategy_registry`의 전략
   일곱이 있는지 읽기 전용으로 조회해라. 접속이 안 되면 백업의 `db/README.md`를 읽고 두 방법 가운데
   어느 쪽을 쓸지 나에게 물어라. 데이터베이스에 쓰는 명령은 내가 승인하기 전에 실행하지 마라.
5. `handover/workstation-handover.md` 7절의 확인 목록을 위에서부터 하나씩 실행하고, 항목마다 통과·실패와
   실제 출력 요약을 적어라. 루트 pytest 기준치는 2,539 passed다. 실패한 항목은 원인을 적고 고치지 말고
   보고해라.
6. Codex 호출이 되는지 확인해라. `~/.codex/config.toml`의 model 값을 읽어 `mcp__codex-cli__codex`에
   `model`로 넘기고 `reasoningEffort`는 `low`로, 프롬프트는 "저장소 루트의 README.md 유무만 답하라"로
   짧게 호출해 답이 오는지 봐라. 안 되면 `codex login`이 필요한지 알려 줘라.
7. 모두 끝나면 다음 작업을 제안해라. `.claude/OBJECTIVE.md`는 끝난 목표(일곱째 Agent 회차)이므로 새로
   써야 한다. ClickUp의 결정 항목 z8nrz7e6ha(오렌지 지표 정의의 출처, 승인 필요 근사안 진행 여부)와
   구현 항목 z8nrz7e7zd의 하위 다섯을 읽고, 리테스트 능력(z8nrz7e7zf)부터 시작하는 OBJECTIVE 초안을
   제시해라. 초안을 쓰기만 하고 `/goal` 등록은 내가 한다. 새 브랜치는 main에서 만든다.

규칙은 `.claude/HARNESS.md`를 따른다. 구현은 이 세션이 하고 설계 검토와 코드 리뷰는 Codex가 한다.
push는 QA가 녹색이고 Codex 리뷰가 Blocking 0일 때만, 그리고 권한 프롬프트를 거쳐서 한다. 거부한
프롬프트는 최종이다. 데이터베이스는 읽기 전용이다. 파이썬은 `.venv/bin/python`만 쓴다. 보고는
완결된 문장으로 쓰고 화살표나 내부 약칭을 쓰지 않는다.

---

## 복원 전에 쓸 짧은 프롬프트 (restore.sh를 돌리기 전, 홈 디렉터리에서 열었을 때)

외장 디스크 `/Volumes/BackupDisk/Orca/trading-system-v2/`에 trading-system-v2 작업의 백업이 있다.
`README-먼저읽기.md`를 읽고, `restore.sh`가 무엇을 어디에 놓는지 설명한 뒤, 내가 승인하면
`bash restore.sh --with-secrets`를 실행하고 출력 전체를 보여 줘라. 비밀 파일의 내용은 출력하지 마라.
끝나면 `RESTART_PROMPT.md`의 본 프롬프트로 넘어간다.
