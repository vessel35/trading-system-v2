---
name: physical-design
description: "테이블 생성, 인덱스 설계, SQL DDL 작성 시 이 원칙을 적용합니다."
---
# Database Physical Design

이 skill은 데이터베이스 물리 설계 원칙을 정의합니다.

## 물리적 설계 개요

```
논리적 스키마 → 물리적 스키마
              │
              ├── 테이블 구조 최적화
              ├── 인덱스 설계
              ├── 파티셔닝
              ├── 스토리지 설계
              └── 성능 최적화
```

## 테이블 설계

### DDL 기본 구조

```sql
CREATE TABLE users (
    -- 기본키
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- 필수 필드
    email VARCHAR(255) NOT NULL,
    name VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,

    -- 선택 필드
    phone VARCHAR(20),
    avatar_url TEXT,

    -- 상태/플래그
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,

    -- 메타데이터
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE,  -- Soft delete

    -- 제약조건
    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT ck_users_email CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

-- 코멘트
COMMENT ON TABLE users IS '사용자 정보';
COMMENT ON COLUMN users.password_hash IS 'bcrypt 해시된 비밀번호';
```

### 데이터 타입 선택 (DBMS별)

#### PostgreSQL

```sql
-- 문자열
VARCHAR(n)          -- 가변 길이 (n 바이트 제한)
TEXT                -- 무제한 가변 길이
CHAR(n)             -- 고정 길이

-- 숫자
SMALLINT            -- -32,768 ~ 32,767
INTEGER             -- -2B ~ 2B
BIGINT              -- -9E18 ~ 9E18
NUMERIC(p,s)        -- 정밀 소수 (금액)
REAL / DOUBLE       -- 부동소수점

-- 날짜/시간
TIMESTAMP WITH TIME ZONE  -- 권장 (타임존 포함)
TIMESTAMP           -- 타임존 없음
DATE                -- 날짜만
TIME                -- 시간만
INTERVAL            -- 시간 간격

-- 특수 타입
UUID                -- 고유 식별자
JSONB               -- JSON (바이너리, 인덱싱 가능)
ARRAY               -- 배열
BYTEA               -- 바이너리 데이터

-- 열거형
CREATE TYPE order_status AS ENUM ('pending', 'processing', 'completed', 'cancelled');
```

#### MySQL

```sql
-- 문자열
VARCHAR(n)          -- 최대 65,535 바이트
TEXT                -- 최대 65,535 바이트
MEDIUMTEXT          -- 최대 16MB
LONGTEXT            -- 최대 4GB

-- 숫자
TINYINT             -- -128 ~ 127
SMALLINT            -- -32,768 ~ 32,767
INT                 -- -2B ~ 2B
BIGINT              -- -9E18 ~ 9E18
DECIMAL(p,s)        -- 정밀 소수

-- 날짜/시간
DATETIME            -- 날짜+시간 (타임존 없음)
TIMESTAMP           -- UTC 저장, 조회시 변환
DATE                -- 날짜만

-- 특수 타입
JSON                -- JSON 데이터
BINARY / VARBINARY  -- 바이너리
ENUM('a','b','c')   -- 열거형
```

### NULL 처리 전략

```sql
-- NULL 허용 여부 결정 기준
-- 1. 비즈니스적으로 "값이 없음"이 의미 있는가?
-- 2. 쿼리 성능에 영향을 주는가?

-- 권장: 가능하면 NOT NULL + DEFAULT
status VARCHAR(20) NOT NULL DEFAULT 'pending'

-- NULL이 의미 있는 경우
deleted_at TIMESTAMP  -- NULL = 삭제되지 않음
parent_id BIGINT      -- NULL = 최상위 항목
```

## 인덱스 설계

### 인덱스 유형

```sql
-- B-Tree 인덱스 (기본, 대부분의 경우)
CREATE INDEX idx_users_email ON users(email);

-- 복합 인덱스 (다중 컬럼)
CREATE INDEX idx_orders_user_status ON orders(user_id, status);

-- 유니크 인덱스
CREATE UNIQUE INDEX idx_users_email_unique ON users(email);

-- 부분 인덱스 (조건부)
CREATE INDEX idx_users_active ON users(email) WHERE is_active = TRUE;

-- 커버링 인덱스 (INCLUDE)
CREATE INDEX idx_orders_user ON orders(user_id) INCLUDE (status, total);

-- Hash 인덱스 (동등 비교만)
CREATE INDEX idx_users_email_hash ON users USING HASH (email);

-- GIN 인덱스 (배열, JSONB, 전문검색)
CREATE INDEX idx_posts_tags ON posts USING GIN (tags);
CREATE INDEX idx_products_data ON products USING GIN (data jsonb_path_ops);

-- GiST 인덱스 (지리/기하 데이터)
CREATE INDEX idx_locations_point ON locations USING GIST (coordinates);
```

### 인덱스 설계 원칙

```
1. 선택도(Selectivity) 고려
   - 높은 선택도 컬럼 우선 (유니크에 가까울수록)
   - 낮은 선택도: gender, status (인덱스 효과 낮음)
   - 예외: 낮은 값이 적은 비율일 때 (is_admin = TRUE)

2. 복합 인덱스 컬럼 순서
   - 동등 조건(=) 컬럼 먼저
   - 범위 조건(<, >, BETWEEN) 컬럼 나중에
   - ORDER BY 컬럼 고려

   -- 쿼리: WHERE user_id = ? AND created_at > ? ORDER BY created_at
   CREATE INDEX idx_orders_user_created ON orders(user_id, created_at);

3. 읽기 vs 쓰기 트레이드오프
   - 인덱스 많으면 INSERT/UPDATE 느려짐
   - 필요한 인덱스만 생성
```

### 인덱스 사용 확인

```sql
-- PostgreSQL
EXPLAIN ANALYZE SELECT * FROM users WHERE email = 'test@example.com';

-- MySQL
EXPLAIN SELECT * FROM users WHERE email = 'test@example.com';

-- 실행 계획 확인 포인트
-- - Index Scan vs Seq Scan (Table Scan)
-- - 예상 비용 (cost)
-- - 실제 실행 시간
```

## 파티셔닝

### 파티션 유형

```sql
-- 범위 파티셔닝 (Range)
CREATE TABLE orders (
    id BIGINT,
    user_id BIGINT,
    created_at TIMESTAMP,
    total DECIMAL(19,4)
) PARTITION BY RANGE (created_at);

CREATE TABLE orders_2024_q1 PARTITION OF orders
    FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');
CREATE TABLE orders_2024_q2 PARTITION OF orders
    FOR VALUES FROM ('2024-04-01') TO ('2024-07-01');

-- 리스트 파티셔닝 (List)
CREATE TABLE orders (
    id BIGINT,
    region VARCHAR(50),
    total DECIMAL(19,4)
) PARTITION BY LIST (region);

CREATE TABLE orders_asia PARTITION OF orders
    FOR VALUES IN ('KR', 'JP', 'CN');
CREATE TABLE orders_europe PARTITION OF orders
    FOR VALUES IN ('DE', 'FR', 'UK');

-- 해시 파티셔닝 (Hash)
CREATE TABLE orders (
    id BIGINT,
    user_id BIGINT
) PARTITION BY HASH (user_id);

CREATE TABLE orders_p0 PARTITION OF orders
    FOR VALUES WITH (MODULUS 4, REMAINDER 0);
CREATE TABLE orders_p1 PARTITION OF orders
    FOR VALUES WITH (MODULUS 4, REMAINDER 1);
```

### 파티셔닝 고려 사항

```
적용 시점:
- 테이블 크기가 수억 건 이상
- 특정 기간/조건 데이터만 자주 조회
- 오래된 데이터 아카이빙/삭제 필요

주의사항:
- 파티션 키는 대부분의 쿼리에 포함되어야 함
- 파티션 간 조인 성능 저하
- 유니크 제약조건은 파티션 키 포함 필요
```

## 성능 최적화

### 쿼리 최적화 패턴

```sql
-- 1. 커버링 인덱스 활용
-- 인덱스만으로 쿼리 완료 (테이블 접근 불필요)
CREATE INDEX idx_orders_cover ON orders(user_id, status, created_at)
    INCLUDE (total);

SELECT status, total, created_at
FROM orders
WHERE user_id = 123;

-- 2. 페이지네이션 최적화
-- Bad: OFFSET 사용 (대량 데이터 시 느림)
SELECT * FROM orders ORDER BY id LIMIT 20 OFFSET 10000;

-- Good: Keyset/Cursor 방식
SELECT * FROM orders
WHERE id > 10000  -- 마지막 조회 ID
ORDER BY id
LIMIT 20;

-- 3. EXISTS vs IN
-- 서브쿼리 결과가 클 때 EXISTS 유리
SELECT * FROM users u
WHERE EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id);

-- 4. 불필요한 컬럼 제외
-- Bad
SELECT * FROM users;

-- Good
SELECT id, name, email FROM users;

-- 5. 배치 처리
-- 대량 INSERT
INSERT INTO logs (message, created_at)
VALUES
    ('msg1', NOW()),
    ('msg2', NOW()),
    ('msg3', NOW());  -- 여러 행 한 번에
```

### 통계 관리

```sql
-- PostgreSQL: 통계 갱신
ANALYZE users;
ANALYZE orders;

-- 자동 vacuum 설정
ALTER TABLE orders SET (
    autovacuum_vacuum_scale_factor = 0.1,
    autovacuum_analyze_scale_factor = 0.05
);

-- MySQL: 통계 갱신
ANALYZE TABLE users;
ANALYZE TABLE orders;
```

### 연결 풀링

```
-- 권장 설정
- 최대 연결 수: CPU 코어 * 2 + 디스크 수
- 유휴 연결 타임아웃: 5-10분
- 연결 검증 쿼리: SELECT 1

-- PgBouncer 예시
[databases]
mydb = host=localhost dbname=mydb

[pgbouncer]
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
```

## 고가용성

### 복제 구성

```
Primary-Replica 구성:

┌─────────┐     WAL     ┌─────────┐
│ Primary │────────────→│ Replica │
│  (R/W)  │             │  (R/O)  │
└─────────┘             └─────────┘
     │
     └── 쓰기 쿼리

읽기 분산:
- 읽기: Replica로 분산
- 쓰기: Primary만
- 복제 지연 고려 필요
```

### 백업 전략

```
백업 유형:
1. 전체 백업 (Full): 주 1회
2. 증분 백업 (Incremental): 일 1회
3. WAL/Binlog 아카이브: 지속적

-- PostgreSQL pg_dump
pg_dump -Fc -f backup.dump mydb

-- PostgreSQL 포인트인타임 복구
archive_mode = on
archive_command = 'cp %p /archive/%f'

-- MySQL mysqldump
mysqldump --single-transaction -u root -p mydb > backup.sql
```

## 보안

### 접근 제어

```sql
-- 역할 생성
CREATE ROLE app_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_readonly;

CREATE ROLE app_readwrite;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_readwrite;

-- 사용자 생성
CREATE USER app_user WITH PASSWORD 'secure_password';
GRANT app_readwrite TO app_user;

-- 컬럼 레벨 권한
GRANT SELECT (id, name, email) ON users TO app_readonly;
-- password_hash 컬럼 접근 불가
```

### 데이터 암호화

```sql
-- 저장 암호화 (Encryption at Rest)
-- DBMS 또는 스토리지 레벨에서 설정

-- 컬럼 암호화
-- PostgreSQL pgcrypto
CREATE EXTENSION pgcrypto;

INSERT INTO users (ssn_encrypted)
VALUES (pgp_sym_encrypt('123-45-6789', 'encryption_key'));

SELECT pgp_sym_decrypt(ssn_encrypted::bytea, 'encryption_key')
FROM users;
```

### 감사 로깅

```sql
-- 감사 테이블
CREATE TABLE audit_log (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    table_name VARCHAR(100),
    operation VARCHAR(10),
    old_data JSONB,
    new_data JSONB,
    changed_by VARCHAR(100),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 트리거 예시
CREATE OR REPLACE FUNCTION audit_trigger()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO audit_log (table_name, operation, old_data, new_data, changed_by)
    VALUES (
        TG_TABLE_NAME,
        TG_OP,
        row_to_json(OLD),
        row_to_json(NEW),
        current_user
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

## 마이그레이션

### 스키마 버전 관리

```sql
-- 마이그레이션 테이블
CREATE TABLE schema_migrations (
    version VARCHAR(255) PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 마이그레이션 파일 명명
-- V001__create_users_table.sql
-- V002__add_email_index.sql
-- V003__create_orders_table.sql
```

### 무중단 마이그레이션

```sql
-- 1. 새 컬럼 추가 (NULL 허용)
ALTER TABLE users ADD COLUMN phone VARCHAR(20);

-- 2. 데이터 마이그레이션 (배치)
UPDATE users SET phone = old_phone WHERE id BETWEEN 1 AND 10000;

-- 3. 애플리케이션 배포 (새 컬럼 사용)

-- 4. NOT NULL 제약 추가
ALTER TABLE users ALTER COLUMN phone SET NOT NULL;

-- 5. 이전 컬럼 삭제
ALTER TABLE users DROP COLUMN old_phone;
```

## 체크리스트

### 테이블 설계
- [ ] 적절한 데이터 타입이 선택되었는가?
- [ ] NOT NULL/DEFAULT가 적절히 설정되었는가?
- [ ] 제약조건이 정의되었는가?

### 인덱스
- [ ] 자주 사용되는 쿼리에 인덱스가 있는가?
- [ ] 복합 인덱스 컬럼 순서가 올바른가?
- [ ] 불필요한 인덱스가 없는가?

### 성능
- [ ] 쿼리 실행 계획이 확인되었는가?
- [ ] 대용량 테이블에 파티셔닝이 고려되었는가?
- [ ] 연결 풀링이 설정되었는가?

### 보안
- [ ] 최소 권한 원칙이 적용되었는가?
- [ ] 민감 데이터가 암호화되었는가?
- [ ] 감사 로깅이 설정되었는가?

### 운영
- [ ] 백업 전략이 수립되었는가?
- [ ] 복제/HA 구성이 되어있는가?
- [ ] 마이그레이션 전략이 있는가?
