---
name: backend-principles
description: "백엔드 아키텍처 설계, API 설계, 서버 사이드 개발 시 이 원칙을 적용합니다."
---
# Backend Development Principles

이 skill은 백엔드 개발의 핵심 원칙을 정의합니다.

## 핵심 원칙

### 1. API 설계

#### RESTful API
```
GET    /users          # 목록 조회
GET    /users/{id}     # 단일 조회
POST   /users          # 생성
PUT    /users/{id}     # 전체 수정
PATCH  /users/{id}     # 부분 수정
DELETE /users/{id}     # 삭제
```

#### 응답 형식
```json
{
  "success": true,
  "data": { },
  "meta": {
    "page": 1,
    "total": 100
  }
}
```

#### 에러 응답
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid email format",
    "details": [
      { "field": "email", "message": "Must be valid email" }
    ]
  }
}
```

#### HTTP 상태 코드
| 코드 | 의미 | 사용 |
|------|------|------|
| 200 | OK | 성공 |
| 201 | Created | 생성 성공 |
| 204 | No Content | 삭제 성공 |
| 400 | Bad Request | 잘못된 요청 |
| 401 | Unauthorized | 인증 필요 |
| 403 | Forbidden | 권한 없음 |
| 404 | Not Found | 리소스 없음 |
| 409 | Conflict | 충돌 |
| 422 | Unprocessable Entity | 유효성 검증 실패 |
| 500 | Internal Server Error | 서버 오류 |

### 2. 보안

#### 인증 (Authentication)
- JWT (Access Token + Refresh Token)
- OAuth 2.0 / OpenID Connect
- 세션 기반 인증

#### 인가 (Authorization)
- RBAC (Role-Based Access Control)
- ABAC (Attribute-Based Access Control)
- 리소스 소유권 검증

#### 보안 체크리스트
- [ ] SQL Injection 방지 (파라미터화된 쿼리)
- [ ] XSS 방지 (출력 이스케이프)
- [ ] CSRF 방지 (토큰 검증)
- [ ] Rate Limiting 적용
- [ ] 민감 데이터 암호화
- [ ] HTTPS 강제
- [ ] 보안 헤더 설정

### 3. 데이터베이스

#### 설계 원칙
- 정규화 (최소 3NF)
- 적절한 인덱스 설계
- 외래 키 제약 조건

#### 쿼리 최적화
- N+1 문제 방지 (Eager Loading)
- 페이지네이션 (Cursor-based 권장)
- 필요한 컬럼만 SELECT

#### 트랜잭션
```python
# 원자성 보장
async with db.transaction():
    await create_order(order)
    await update_inventory(items)
    await create_payment(payment)
```

### 4. 에러 처리

#### 예외 계층 구조
```
ApplicationException
├── ValidationException (400)
├── AuthenticationException (401)
├── AuthorizationException (403)
├── NotFoundException (404)
├── ConflictException (409)
└── InternalException (500)
```

#### 로깅
- 요청/응답 로깅
- 에러 스택 트레이스
- 구조화된 로그 (JSON)

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "ERROR",
  "message": "User not found",
  "request_id": "abc-123",
  "user_id": "user-456",
  "error": { "code": "NOT_FOUND", "stack": "..." }
}
```

### 5. 성능

#### 캐싱 전략
| 레벨 | 도구 | 용도 |
|------|------|------|
| Application | Local Cache | 설정, 메타데이터 |
| Distributed | Redis | 세션, 자주 조회되는 데이터 |
| HTTP | Cache-Control | 정적 리소스 |

#### 비동기 처리
- 메시지 큐 (RabbitMQ, Kafka)
- 배경 작업 (Celery, Bull)
- 이벤트 기반 아키텍처

### 6. 테스트

#### 테스트 종류
```
tests/
├── unit/              # 비즈니스 로직
├── integration/       # DB, 외부 서비스
└── e2e/              # API 엔드포인트
```

#### 테스트 원칙
- 테스트 격리 (독립적 실행)
- 테스트 데이터 관리 (Fixtures, Factories)
- Mocking 최소화

### 7. 폴더 구조

```
src/
├── api/
│   ├── routes/
│   ├── controllers/
│   └── middlewares/
├── domain/
│   ├── entities/
│   ├── repositories/
│   └── services/
├── infrastructure/
│   ├── database/
│   ├── cache/
│   └── external/
├── config/
└── utils/
```

## 운영

### Health Check
```
GET /health
{
  "status": "healthy",
  "version": "1.0.0",
  "dependencies": {
    "database": "healthy",
    "cache": "healthy"
  }
}
```

### 모니터링
- 메트릭: 요청 수, 응답 시간, 에러율
- 알림: 임계치 초과 시 알림
- 분산 추적: 요청 흐름 추적

## 체크리스트

- [ ] API가 RESTful 원칙을 따르는가?
- [ ] 적절한 인증/인가가 구현되었는가?
- [ ] SQL Injection 등 보안 취약점이 없는가?
- [ ] 에러 처리가 일관적인가?
- [ ] 로깅이 적절히 구현되었는가?
- [ ] 테스트 커버리지가 충분한가?
