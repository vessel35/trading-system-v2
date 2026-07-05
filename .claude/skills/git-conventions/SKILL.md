---
name: git-conventions
description: "Git 커밋, 브랜치 생성, PR 작성 시 이 규칙을 적용합니다."
---
# Git Conventions

이 skill은 일관된 Git 사용 규칙을 정의합니다.

## Commit Message Convention

### 형식 (Conventional Commits)

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type 종류

| Type | 설명 |
|------|------|
| `feat` | 새로운 기능 추가 |
| `fix` | 버그 수정 |
| `docs` | 문서 변경 |
| `style` | 코드 포맷팅 (기능 변경 없음) |
| `refactor` | 리팩토링 (기능 변경 없음) |
| `perf` | 성능 개선 |
| `test` | 테스트 추가/수정 |
| `chore` | 빌드, 설정 파일 변경 |
| `ci` | CI 설정 변경 |
| `revert` | 이전 커밋 되돌리기 |

### 예시

```
feat(auth): add JWT authentication

- Implement JWT token generation
- Add token validation middleware
- Create refresh token mechanism

Closes #123
```

```
fix(api): resolve race condition in user update

The concurrent update issue was caused by missing
transaction locks. Added pessimistic locking to
prevent data corruption.

Fixes #456
```

### Subject 규칙
- 50자 이내
- 첫 글자 소문자
- 마침표 없음
- 명령형 사용 (add, fix, change)

### Body 규칙
- 72자에서 줄바꿈
- "무엇을"과 "왜"를 설명
- "어떻게"는 코드가 설명

## Branch Strategy

### Git Flow

```
main (production)
  └── develop
        ├── feature/feature-name
        ├── bugfix/bug-description
        └── release/v1.0.0
              └── hotfix/critical-fix
```

### Branch 네이밍

| Branch | 패턴 | 예시 |
|--------|------|------|
| Feature | `feature/<issue-id>-<description>` | `feature/123-user-auth` |
| Bugfix | `bugfix/<issue-id>-<description>` | `bugfix/456-login-error` |
| Hotfix | `hotfix/<issue-id>-<description>` | `hotfix/789-security-patch` |
| Release | `release/v<version>` | `release/v1.2.0` |

### Trunk-Based Development (대안)

```
main
  ├── short-lived feature branches
  └── release branches (optional)
```

- 짧은 수명의 feature branch (1-2일)
- 자주 main에 merge
- Feature flag 활용

## Pull Request

### PR 제목
```
[TYPE] 간단한 설명 (#이슈번호)
```

### PR 템플릿

```markdown
## 변경 사항
- 변경 내용 1
- 변경 내용 2

## 변경 이유
왜 이 변경이 필요한지 설명

## 테스트
- [ ] 단위 테스트 추가/수정
- [ ] 통합 테스트 통과
- [ ] 수동 테스트 완료

## 스크린샷 (UI 변경 시)

## 체크리스트
- [ ] 코드 셀프 리뷰 완료
- [ ] 문서 업데이트 완료
- [ ] Breaking change 없음
```

## 기타 규칙

### .gitignore 필수 항목
```
# Dependencies
node_modules/
venv/
vendor/

# Build
dist/
build/
*.pyc

# Environment
.env
.env.local
*.local

# IDE
.idea/
.vscode/
*.swp

# OS
.DS_Store
Thumbs.db

# Logs
*.log
logs/
```

### Git Hooks (권장)
- `pre-commit`: 린터, 포맷터 실행
- `commit-msg`: 커밋 메시지 검증
- `pre-push`: 테스트 실행

## 체크리스트

- [ ] 커밋 메시지가 Conventional Commits 형식인가?
- [ ] Branch 이름이 규칙을 따르는가?
- [ ] PR에 충분한 설명이 있는가?
- [ ] .gitignore가 적절히 설정되었는가?
