# Python Ruff Rules Reference

Ruff는 Rust로 작성된 빠른 Python 린터입니다.

## 기본 설정

### pyproject.toml

```toml
[tool.ruff]
target-version = "py311"
line-length = 88
fix = true

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # Pyflakes
    "I",      # isort
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "UP",     # pyupgrade
    "ARG",    # flake8-unused-arguments
    "SIM",    # flake8-simplify
    "TCH",    # flake8-type-checking
    "PTH",    # flake8-use-pathlib
    "RUF",    # Ruff-specific rules
]

ignore = [
    "E501",   # line too long (handled by formatter)
    "B008",   # function call in default argument (for FastAPI)
]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = [
    "ARG",    # unused arguments in tests
    "S101",   # assert usage
]

[tool.ruff.lint.isort]
known-first-party = ["app"]
force-single-line = true

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

## 주요 규칙 설명

### E (pycodestyle)
```python
# E711: comparison to None
# Bad
if x == None:

# Good
if x is None:
```

### F (Pyflakes)
```python
# F401: imported but unused
# F841: local variable assigned but never used
from os import path  # 사용하지 않으면 에러

unused_var = 1  # 사용하지 않으면 에러
```

### B (flake8-bugbear)
```python
# B006: mutable default argument
# Bad
def func(items: list = []):
    pass

# Good
def func(items: list | None = None):
    items = items or []
```

### C4 (flake8-comprehensions)
```python
# C400: unnecessary generator
# Bad
list(x for x in range(10))

# Good
[x for x in range(10)]
```

### UP (pyupgrade)
```python
# UP006: use builtin types for type hints
# Bad (Python 3.9+)
from typing import List
def func(items: List[str]):
    pass

# Good
def func(items: list[str]):
    pass
```

### SIM (flake8-simplify)
```python
# SIM102: nested if statements
# Bad
if a:
    if b:
        do_something()

# Good
if a and b:
    do_something()

# SIM108: ternary operator
# Bad
if condition:
    x = a
else:
    x = b

# Good
x = a if condition else b
```

### TCH (flake8-type-checking)
```python
# TCH001: move import into TYPE_CHECKING block
# 런타임에 필요 없는 타입만 사용하는 import

# Bad
from mymodule import SomeClass
def func(x: SomeClass): ...

# Good
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from mymodule import SomeClass
def func(x: "SomeClass"): ...
```

### PTH (flake8-use-pathlib)
```python
# PTH123: use Path.open()
# Bad
import os
with open(os.path.join(dir, file)) as f:
    pass

# Good
from pathlib import Path
with Path(dir, file).open() as f:
    pass
```

### RUF (Ruff-specific)
```python
# RUF001: ambiguous unicode character
# RUF002: docstring with ambiguous unicode
# RUF003: comment with ambiguous unicode
```

## 추가 권장 규칙

```toml
[tool.ruff.lint]
select = [
    # ... 기본 규칙 ...
    "ANN",    # flake8-annotations
    "ASYNC",  # flake8-async
    "S",      # flake8-bandit (security)
    "BLE",    # flake8-blind-except
    "A",      # flake8-builtins
    "COM",    # flake8-commas
    "DTZ",    # flake8-datetimez
    "T10",    # flake8-debugger
    "EM",     # flake8-errmsg
    "ISC",    # flake8-implicit-str-concat
    "ICN",    # flake8-import-conventions
    "LOG",    # flake8-logging
    "G",      # flake8-logging-format
    "PIE",    # flake8-pie
    "PYI",    # flake8-pyi
    "Q",      # flake8-quotes
    "RSE",    # flake8-raise
    "RET",    # flake8-return
    "SLF",    # flake8-self
    "SLOT",   # flake8-slots
    "TID",    # flake8-tidy-imports
    "INT",    # flake8-gettext
    "ERA",    # eradicate (commented code)
    "PGH",    # pygrep-hooks
    "PL",     # Pylint
    "TRY",    # tryceratops
    "FLY",    # flynt
    "PERF",   # Perflint
    "FURB",   # refurb
]
```

## CI 통합

```yaml
# .github/workflows/lint.yml
name: Lint
on: [push, pull_request]
jobs:
  ruff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/ruff-action@v1
        with:
          args: "check --output-format=github"
      - uses: astral-sh/ruff-action@v1
        with:
          args: "format --check"
```

## 로컬 사용

```bash
# 린트 체크
ruff check .

# 자동 수정
ruff check --fix .

# 포맷팅 체크
ruff format --check .

# 포맷팅 적용
ruff format .
```
