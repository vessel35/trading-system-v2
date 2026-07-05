---
name: python
description: "Python 코드 작성, .py 파일 수정, Python 프로젝트 개발 시 이 규칙을 적용합니다."
---

# Python Conventions

> **Target Version: Python 3.12** (Stable, October 2024)
> **Minimum Supported: Python 3.10**

이 skill은 Python 코딩 규칙을 정의합니다.

<!-- context7-strip-begin -->
## 버전별 주요 변경사항

### Python 3.12 (현재 권장)
- **추가**: 타입 파라미터 문법 (`type` 문, 제네릭 클래스 간소화)
- **추가**: f-string 개선 (중첩, 멀티라인, 백슬래시 허용)
- **추가**: `@override` 데코레이터 (`typing` 모듈)
- **개선**: 에러 메시지 개선, 15% 성능 향상

### Python 3.11
- **추가**: `ExceptionGroup`, `except*` 문법
- **추가**: `tomllib` 표준 라이브러리
- **추가**: `Self` 타입 (`typing` 모듈)
- **개선**: 25% 성능 향상

### Python 3.10
- **추가**: `match`/`case` 패턴 매칭
- **추가**: `|` Union 타입 문법 (`str | None`)
- **추가**: `ParamSpec`, `TypeAlias`

### Deprecated/Removed
- `typing.List`, `typing.Dict` → `list`, `dict` (3.9+, 3.12에서 권장)
- `asyncio.get_event_loop()` → `asyncio.get_running_loop()` 또는 `asyncio.run()`
- `distutils` 모듈 제거 (3.12)
<!-- context7-strip-end -->

## 스타일 가이드

### PEP 8 기본 규칙

```python
# 들여쓰기: 4 spaces
def function():
    if condition:
        do_something()

# 줄 길이: 88자 (Black 기준) 또는 79자 (PEP 8)

# 빈 줄
# - 최상위 함수/클래스 사이: 2줄
# - 클래스 내 메서드 사이: 1줄


class MyClass:
    def method_one(self):
        pass

    def method_two(self):
        pass


def top_level_function():
    pass
```

### 네이밍

| 종류 | 규칙 | 예시 |
|------|------|------|
| 변수/함수 | snake_case | `user_name`, `get_user_by_id` |
| 상수 | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT` |
| 클래스 | PascalCase | `UserService` |
| 모듈 | snake_case | `user_service.py` |
| Private | _prefix | `_internal_method` |
| Dunder | __name__ | `__init__`, `__str__` |

### Import 순서

```python
# 1. 표준 라이브러리
import os
import sys
from datetime import datetime

# 2. 서드파티 라이브러리
import requests
from fastapi import FastAPI

# 3. 로컬 모듈
from app.models import User
from app.services import UserService
```

## 타입 힌트

### 기본 타입 (Python 3.12)

```python
# Python 3.12+: typing 모듈 import 최소화
from typing import Callable  # 필요한 것만

# 기본 타입
name: str = "John"
age: int = 30
active: bool = True

# 컬렉션 - 내장 타입 사용 (3.9+, 권장)
names: list[str] = ["Alice", "Bob"]
scores: dict[str, int] = {"math": 90}
coordinates: tuple[int, int] = (10, 20)
unique_ids: set[str] = {"a", "b"}

# Optional - Union 문법 사용 (3.10+, 권장)
email: str | None = None
result: int | str = 42

# ❌ Deprecated (3.9 이전 문법)
# from typing import List, Dict, Optional
# names: List[str]  → list[str]
# data: Optional[str]  → str | None
```

### 함수 타입

```python
def greet(name: str) -> str:
    return f"Hello, {name}"

def process(
    items: list[str],
    *,
    limit: int = 10,
    callback: Callable[[str], None] | None = None,
) -> list[str]:
    pass
```

### 제네릭 (Python 3.12 신규 문법)

```python
# Python 3.12+: 새로운 타입 파라미터 문법 (권장)
class Repository[T]:
    def get(self, id: str) -> T | None:
        pass

    def save(self, entity: T) -> T:
        pass

# 제네릭 함수 (3.12+)
def first[T](items: list[T]) -> T | None:
    return items[0] if items else None

# 타입 별칭 (3.12+)
type Vector[T] = list[tuple[T, T]]
type UserID = int

# ❌ 이전 문법 (3.11 이하에서만 사용)
# from typing import TypeVar, Generic
# T = TypeVar("T")
# class Repository(Generic[T]): ...
```

### Pydantic 모델 (Pydantic v2.6+)

```python
from pydantic import BaseModel, Field, EmailStr, ConfigDict

# Pydantic v2 문법 (권장)
class User(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)

    id: str
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    age: int = Field(..., ge=0, le=150)

# 검증 데코레이터 (v2)
from pydantic import field_validator

class CreateUser(BaseModel):
    name: str
    email: str

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        if '@' not in v:
            raise ValueError('Invalid email')
        return v.lower()

# ❌ Pydantic v1 문법 (Deprecated)
# class Config:  → model_config = ConfigDict(...)
# @validator  → @field_validator
# .dict()  → .model_dump()
# .parse_obj()  → .model_validate()
```

## 코딩 패턴

### Context Manager

```python
# 파일 처리
with open("file.txt", "r") as f:
    content = f.read()

# 커스텀 컨텍스트 매니저
from contextlib import contextmanager

@contextmanager
def database_transaction():
    db = connect()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

### 예외 처리

```python
# 구체적인 예외
try:
    result = process_data(data)
except ValueError as e:
    logger.error(f"Invalid data: {e}")
    raise
except ConnectionError as e:
    logger.error(f"Connection failed: {e}")
    return None

# 커스텀 예외
class UserNotFoundError(Exception):
    def __init__(self, user_id: str):
        self.user_id = user_id
        super().__init__(f"User not found: {user_id}")
```

### 데코레이터

```python
from functools import wraps
from typing import Callable, TypeVar

T = TypeVar("T")

def retry(max_attempts: int = 3) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception:
                    if attempt == max_attempts - 1:
                        raise
            raise RuntimeError("Unreachable")
        return wrapper
    return decorator
```

### Dataclass

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass(frozen=True)
class User:
    id: str
    name: str
    email: str
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if not self.name:
            raise ValueError("Name cannot be empty")
```

## 비동기 프로그래밍

```python
import asyncio
from typing import AsyncIterator

async def fetch_user(user_id: str) -> User:
    async with aiohttp.ClientSession() as session:
        async with session.get(f"/users/{user_id}") as response:
            data = await response.json()
            return User(**data)

async def fetch_all_users(user_ids: list[str]) -> list[User]:
    tasks = [fetch_user(uid) for uid in user_ids]
    return await asyncio.gather(*tasks)

async def stream_data() -> AsyncIterator[str]:
    async for item in source:
        yield item
```

## Docstring

### Google Style (권장)

```python
def fetch_user(user_id: str, include_deleted: bool = False) -> User | None:
    """사용자 정보를 조회합니다.

    Args:
        user_id: 조회할 사용자 ID.
        include_deleted: 삭제된 사용자 포함 여부.

    Returns:
        User 객체. 존재하지 않으면 None.

    Raises:
        ValueError: user_id가 빈 문자열인 경우.
        ConnectionError: DB 연결 실패 시.

    Example:
        >>> user = fetch_user("user-123")
        >>> print(user.name)
        John Doe
    """
    pass


class UserService:
    """사용자 관련 비즈니스 로직을 처리하는 서비스.

    Attributes:
        repository: 사용자 저장소.
        cache: 캐시 클라이언트.

    Example:
        >>> service = UserService(repo, cache)
        >>> user = await service.get_user("123")
    """

    def __init__(self, repository: UserRepository, cache: CacheClient):
        """UserService를 초기화합니다.

        Args:
            repository: 사용자 저장소 인스턴스.
            cache: 캐시 클라이언트 인스턴스.
        """
        self.repository = repository
        self.cache = cache
```

### 모듈 Docstring

```python
"""사용자 관리 모듈.

이 모듈은 사용자 생성, 조회, 수정, 삭제 기능을 제공합니다.

Example:
    >>> from app.services import UserService
    >>> service = UserService()
    >>> user = service.create_user(name="John")
"""
```

## Ruff 규칙 (Ruff 0.8+)

### 필수 규칙

```toml
# pyproject.toml
[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # Pyflakes
    "I",      # isort
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "UP",     # pyupgrade
    "SIM",    # flake8-simplify
    "TCH",    # flake8-type-checking
    "PTH",    # flake8-use-pathlib
    "RUF",    # Ruff-specific rules
]
ignore = [
    "E501",   # line too long (Black handles this)
]

[tool.ruff.lint.isort]
known-first-party = ["app"]
```

### 주요 규칙 설명

| 규칙 | 설명 |
|------|------|
| `F401` | 사용하지 않는 import |
| `F841` | 사용하지 않는 변수 |
| `E711` | `== None` 대신 `is None` 사용 |
| `B006` | mutable 기본 인자 금지 |
| `B008` | 함수 호출을 기본 인자로 사용 금지 |
| `SIM102` | 중첩 if문 통합 |
| `UP035` | deprecated typing import 교체 |

## 체크리스트

- [ ] 타입 힌트가 적절히 사용되었는가?
- [ ] PEP 8 스타일을 따르는가?
- [ ] 예외 처리가 구체적인가?
- [ ] docstring이 적절히 작성되었는가?
- [ ] import 순서가 올바른가?
