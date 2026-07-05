---
name: clean-architecture
description: "아키텍처 설계, 레이어 구조 정의, 의존성 관리 시 이 원칙을 적용합니다."
---
# Clean Architecture Principles

이 skill은 클린 아키텍처 원칙을 프로젝트에 적용합니다.

## 핵심 개념

### 의존성 규칙 (Dependency Rule)
- 의존성은 항상 바깥에서 안쪽으로 향함
- 내부 원은 외부 원에 대해 알지 못함

```
┌─────────────────────────────────────────────┐
│              Frameworks & Drivers           │
│  ┌───────────────────────────────────────┐  │
│  │          Interface Adapters           │  │
│  │  ┌─────────────────────────────────┐  │  │
│  │  │       Application Business      │  │  │
│  │  │  ┌───────────────────────────┐  │  │  │
│  │  │  │   Enterprise Business     │  │  │  │
│  │  │  │       (Entities)          │  │  │  │
│  │  │  └───────────────────────────┘  │  │  │
│  │  │         (Use Cases)             │  │  │
│  │  └─────────────────────────────────┘  │  │
│  │    (Controllers, Gateways, Presenters)│  │
│  └───────────────────────────────────────┘  │
│        (DB, Web, Devices, External APIs)    │
└─────────────────────────────────────────────┘
```

## 계층별 역할

### 1. Entities (Enterprise Business Rules)
- 핵심 비즈니스 규칙
- 가장 변경 가능성이 낮은 코드
- 외부 의존성 없음

### 2. Use Cases (Application Business Rules)
- 애플리케이션 특화 비즈니스 규칙
- Entities를 조합하여 비즈니스 로직 수행
- 입출력 포트(인터페이스) 정의

### 3. Interface Adapters
- 데이터 형식 변환
- Controllers, Presenters, Gateways
- 외부 형식 ↔ 내부 형식 변환

### 4. Frameworks & Drivers
- 프레임워크, 도구, DB, 외부 시스템
- 가장 바깥 계층, 상세 구현

## SOLID 원칙

### S - Single Responsibility Principle
클래스는 변경의 이유가 하나여야 함

### O - Open/Closed Principle
확장에는 열려있고, 수정에는 닫혀있어야 함

### L - Liskov Substitution Principle
하위 타입은 상위 타입을 대체할 수 있어야 함

### I - Interface Segregation Principle
클라이언트별 인터페이스 분리

### D - Dependency Inversion Principle
추상화에 의존, 구체화에 의존하지 않음

## 디렉토리 구조 예시

```
src/
├── domain/                 # Entities
│   ├── entities/
│   └── value-objects/
├── application/            # Use Cases
│   ├── use-cases/
│   ├── ports/
│   │   ├── input/
│   │   └── output/
│   └── services/
├── infrastructure/         # Frameworks & Drivers
│   ├── database/
│   ├── external-apis/
│   └── messaging/
└── presentation/           # Interface Adapters
    ├── controllers/
    ├── presenters/
    └── dto/
```

## 테스트 전략

- **Unit Tests**: Entities, Use Cases
- **Integration Tests**: Interface Adapters
- **E2E Tests**: 전체 시스템

## 체크리스트

- [ ] 의존성이 안쪽으로만 향하는가?
- [ ] Use Case가 프레임워크에 의존하지 않는가?
- [ ] 인터페이스를 통해 의존성 역전이 적용되었는가?
- [ ] 각 계층의 역할이 명확한가?
