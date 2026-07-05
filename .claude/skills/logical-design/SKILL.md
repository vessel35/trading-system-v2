---
name: logical-design
description: "데이터베이스 설계, ERD 작성, 엔티티/관계 정의 시 이 원칙을 적용합니다."
---
# Database Logical Design

이 skill은 데이터베이스 논리 설계 원칙을 정의합니다.

## 설계 프로세스

```
요구사항 분석 → 개념적 설계 → 논리적 설계 → 물리적 설계
                  (ERD)        (스키마)       (구현)
```

## 개념적 설계

### 엔티티 식별

```
1. 명사 추출법
   - 요구사항에서 명사 식별
   - 핵심 비즈니스 개념 선별

2. 엔티티 분류
   - 강한 엔티티: 독립적으로 존재 (User, Product, Order)
   - 약한 엔티티: 다른 엔티티에 종속 (OrderItem, Address)
```

### 속성 정의

```
속성 유형:
├── 단순 속성: name, age
├── 복합 속성: address → (street, city, zipcode)
├── 단일값 속성: email (1개)
├── 다중값 속성: phone_numbers (여러 개)
├── 유도 속성: age (birth_date에서 계산)
└── 키 속성: id, email (고유 식별)
```

### 관계 정의

#### 관계 차수 (Cardinality)

```
1:1 (One-to-One)
┌─────────┐         ┌─────────┐
│  User   │────────│ Profile │
└─────────┘         └─────────┘
예: 사용자 - 프로필 (1명의 사용자는 1개의 프로필)

1:N (One-to-Many)
┌─────────┐         ┌─────────┐
│  User   │───────<│  Order  │
└─────────┘         └─────────┘
예: 사용자 - 주문 (1명의 사용자는 N개의 주문)

M:N (Many-to-Many)
┌─────────┐         ┌─────────┐
│ Student │>───────<│ Course  │
└─────────┘         └─────────┘
예: 학생 - 수강과목 (M명의 학생이 N개의 과목 수강)
→ 연결 테이블로 분해: Enrollment(student_id, course_id)
```

#### 참여 제약조건

```
전체 참여 (Total): 모든 엔티티가 관계에 참여해야 함
부분 참여 (Partial): 일부 엔티티만 관계에 참여

┌─────────┐         ┌─────────┐
│Department│========│Employee │
└─────────┘         └─────────┘
= 전체 참여: 모든 직원은 반드시 부서에 소속
─ 부분 참여: 부서에 직원이 없을 수 있음
```

### ERD 표기법

#### Chen 표기법
```
┌─────────┐      ◇        ┌─────────┐
│ Entity1 │─────works─────│ Entity2 │
└─────────┘               └─────────┘
     │
     ○ attribute
```

#### Crow's Foot 표기법 (권장)
```
┌─────────┐                    ┌─────────┐
│  User   │──────────────────<│  Order  │
│─────────│ 1              M  │─────────│
│ id (PK) │                   │ id (PK) │
│ name    │                   │ user_id │
│ email   │                   │ total   │
└─────────┘                    └─────────┘

기호:
──||── 1 (one)
──○── 0 or 1 (optional)
──<── many
──○<─ 0 or many
──|<─ 1 or many
```

## 논리적 설계

### 정규화 (Normalization)

#### 제1정규형 (1NF)
- 모든 속성은 원자값 (atomic value)
- 반복 그룹 제거

```
# Before (1NF 위반)
┌─────────────────────────────────────┐
│ Order                               │
│─────────────────────────────────────│
│ id │ customer │ items               │
│ 1  │ John     │ Apple, Banana, Milk │  ← 다중값
└─────────────────────────────────────┘

# After (1NF)
┌─────────────────────────┐  ┌────────────────────────┐
│ Order                   │  │ OrderItem              │
│─────────────────────────│  │────────────────────────│
│ id │ customer           │  │ order_id │ item        │
│ 1  │ John               │  │ 1        │ Apple       │
└─────────────────────────┘  │ 1        │ Banana      │
                             │ 1        │ Milk        │
                             └────────────────────────┘
```

#### 제2정규형 (2NF)
- 1NF 만족
- 부분 함수 종속 제거 (복합키의 일부에만 종속되는 속성 분리)

```
# Before (2NF 위반)
┌─────────────────────────────────────────────┐
│ OrderItem                                   │
│─────────────────────────────────────────────│
│ order_id │ product_id │ quantity │ product_name │
│          PK           │          │ ← product_id에만 종속
└─────────────────────────────────────────────┘

# After (2NF)
┌────────────────────────────────┐  ┌─────────────────────┐
│ OrderItem                      │  │ Product             │
│────────────────────────────────│  │─────────────────────│
│ order_id │ product_id │ qty    │  │ id │ name           │
└────────────────────────────────┘  └─────────────────────┘
```

#### 제3정규형 (3NF)
- 2NF 만족
- 이행적 함수 종속 제거 (A→B, B→C일 때 C를 분리)

```
# Before (3NF 위반)
┌───────────────────────────────────────────────┐
│ Employee                                      │
│───────────────────────────────────────────────│
│ id │ name │ dept_id │ dept_name │ dept_location│
│    │      │         │ ← dept_id에 종속 (이행적) │
└───────────────────────────────────────────────┘

# After (3NF)
┌───────────────────────┐  ┌─────────────────────────────┐
│ Employee              │  │ Department                  │
│───────────────────────│  │─────────────────────────────│
│ id │ name │ dept_id   │  │ id │ name │ location        │
└───────────────────────┘  └─────────────────────────────┘
```

#### BCNF (Boyce-Codd Normal Form)
- 3NF 만족
- 모든 결정자가 후보키

```
# 3NF는 만족하지만 BCNF 위반 예시
학생-과목-교수 관계에서:
- 한 과목은 여러 교수가 가르칠 수 있음
- 한 교수는 한 과목만 가르침

{학생, 과목} → 교수
{교수} → 과목  (교수가 결정자이지만 후보키 아님)

해결: 테이블 분리
```

### 반정규화 고려

정규화 vs 성능 트레이드오프:

```
정규화 장점:
- 데이터 무결성
- 저장 공간 효율
- 갱신 이상 방지

반정규화가 필요한 경우:
- 조인 비용이 높을 때
- 읽기가 쓰기보다 훨씬 많을 때
- 계산된 값이 자주 필요할 때

예: 주문 총액을 Order 테이블에 저장 (매번 계산 대신)
```

## 키 설계

### 기본키 (Primary Key)

```
자연키 vs 대리키:

자연키 (Natural Key):
- 비즈니스 의미가 있는 값
- 예: email, ISBN, 주민번호
- 장점: 의미 있음, 별도 조회 없이 식별
- 단점: 변경 가능성, 복잡한 형태

대리키 (Surrogate Key) - 권장:
- 시스템이 생성한 식별자
- 예: auto_increment, UUID
- 장점: 불변, 단순, 성능
- 단점: 비즈니스 의미 없음
```

### 복합키 vs 단일키

```
복합키:
- 연결 테이블에 적합
- 예: enrollment(student_id, course_id)

단일키:
- 대부분의 엔티티에 권장
- 복합키보다 조인 성능 우수
```

### 외래키 (Foreign Key)

```sql
-- 명시적 외래키 정의
CREATE TABLE orders (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    CONSTRAINT fk_orders_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);
```

#### 참조 무결성 옵션

| 옵션 | DELETE 시 | UPDATE 시 |
|------|-----------|-----------|
| RESTRICT | 거부 | 거부 |
| CASCADE | 함께 삭제 | 함께 변경 |
| SET NULL | NULL로 설정 | NULL로 설정 |
| SET DEFAULT | 기본값 설정 | 기본값 설정 |
| NO ACTION | 거부 (지연 검사) | 거부 (지연 검사) |

## 데이터 타입 가이드

### 문자열

| 용도 | 권장 타입 | 설명 |
|------|-----------|------|
| 식별자 | CHAR(n) / VARCHAR(n) | 고정/가변 길이 |
| 짧은 텍스트 | VARCHAR(255) | 이름, 제목 |
| 긴 텍스트 | TEXT | 본문, 설명 |
| 코드/열거형 | VARCHAR(50) | status, type |

### 숫자

| 용도 | 권장 타입 | 설명 |
|------|-----------|------|
| 식별자 | BIGINT | auto_increment |
| 개수/수량 | INT / SMALLINT | 범위에 따라 |
| 금액 | DECIMAL(19,4) | 정밀도 보장 |
| 비율 | DECIMAL(5,4) | 0.0000~1.0000 |

### 날짜/시간

| 용도 | 권장 타입 | 설명 |
|------|-----------|------|
| 타임스탬프 | TIMESTAMP WITH TIME ZONE | 이벤트 시각 |
| 날짜만 | DATE | 생년월일 |
| 시간만 | TIME | 영업시간 |

### Boolean

```sql
-- 권장: BOOLEAN 타입
is_active BOOLEAN DEFAULT TRUE

-- 대안: TINYINT (MySQL 호환)
is_active TINYINT(1) DEFAULT 1
```

## 명명 규칙

### 테이블

```
- 복수형 사용: users, orders, products
- snake_case: order_items, user_profiles
- 연결 테이블: {table1}_{table2} (알파벳순)
  예: course_students, product_tags
```

### 컬럼

```
- snake_case: first_name, created_at
- 외래키: {referenced_table}_id (단수형)
  예: user_id, order_id
- Boolean: is_, has_, can_ 접두사
  예: is_active, has_permission
- 날짜: _at, _on, _date 접미사
  예: created_at, deleted_at, birth_date
```

## 체크리스트

### 엔티티 설계
- [ ] 모든 핵심 비즈니스 개념이 엔티티로 정의되었는가?
- [ ] 엔티티 간 관계가 명확히 정의되었는가?
- [ ] 관계의 차수(1:1, 1:N, M:N)가 올바른가?

### 정규화
- [ ] 최소 3NF까지 정규화되었는가?
- [ ] 반정규화가 필요한 경우 문서화되었는가?

### 키 설계
- [ ] 적절한 기본키가 정의되었는가?
- [ ] 외래키와 참조 무결성이 설정되었는가?

### 명명 규칙
- [ ] 일관된 명명 규칙이 적용되었는가?
- [ ] 의미 있는 이름이 사용되었는가?
