"""Keep the candlestick pattern standard's tables aligned with the TA-Lib ports."""

from __future__ import annotations

import ast
import inspect
import textwrap
from collections.abc import Mapping, Sequence
from pathlib import Path

from core_lib.patterns import TALIB_FUNCTIONS, TALIB_RAW_ALLOWED_VALUES
from core_lib.patterns.talib_candles import CANDLE_SETTING_ORDER, DEFAULT_CANDLE_SETTINGS
from core_lib.patterns.talib_hikkake import TALIB_HIKKAKE_PATTERNS, TalibStatefulPatternPort
from core_lib.patterns.talib_multi_candle import TALIB_MULTI_CANDLE_PATTERNS
from core_lib.patterns.talib_raw import IntegerJudge, TalibPatternPort
from core_lib.patterns.talib_single_candle import TALIB_SINGLE_CANDLE_PATTERNS
from core_lib.patterns.talib_three_candle import TALIB_THREE_CANDLE_PATTERNS
from core_lib.patterns.talib_two_candle import TALIB_TWO_CANDLE_PATTERNS

from pattern_reference import CAPTURE_INSTRUCTIONS, CAPTURED, REGIME_NAMES, SIGNALS

TalibDocPort = TalibPatternPort | TalibStatefulPatternPort
MarkdownRow = dict[str, str]

_STANDARD_PATH = (
    Path(__file__).resolve().parents[3] / "docs/references/candlestick_pattern_calc_spec.md"
)

_STATELESS_TALIB_PORTS: tuple[TalibPatternPort, ...] = (
    *TALIB_SINGLE_CANDLE_PATTERNS,
    *TALIB_TWO_CANDLE_PATTERNS,
    *TALIB_THREE_CANDLE_PATTERNS,
    *TALIB_MULTI_CANDLE_PATTERNS,
)

_ALL_TALIB_PORTS: tuple[TalibDocPort, ...] = (
    *_STATELESS_TALIB_PORTS,
    *TALIB_HIKKAKE_PATTERNS,
)


def _split_markdown_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _strip_code(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("`") and stripped.endswith("`"):
        return stripped[1:-1]
    return stripped


def _table(headers: Sequence[str]) -> list[MarkdownRow]:
    lines = _STANDARD_PATH.read_text(encoding="utf-8").splitlines()
    matches: list[list[MarkdownRow]] = []

    for index, line in enumerate(lines):
        if not line.strip().startswith("|"):
            continue
        if _split_markdown_row(line) != list(headers):
            continue

        rows: list[MarkdownRow] = []
        for row_line in lines[index + 2 :]:
            if not row_line.strip().startswith("|"):
                break
            cells = _split_markdown_row(row_line)
            if len(cells) != len(headers):
                break
            rows.append(dict(zip(headers, cells, strict=True)))
        matches.append(rows)

    assert len(matches) == 1, f"expected one markdown table with headers {headers}"
    return matches[0]


def _parse_setting_names(value: str) -> frozenset[str]:
    if value == "-":
        return frozenset()
    return frozenset(_strip_code(part) for part in value.split(", "))


def _parse_int_values(value: str) -> frozenset[int]:
    if value == "-":
        return frozenset()
    return frozenset(int(part.strip().removeprefix("+")) for part in value.split(", "))


def _eval_int_expr(
    expr: ast.expr,
    names: Mapping[str, frozenset[int]],
) -> frozenset[int]:
    if (
        isinstance(expr, ast.Constant)
        and isinstance(expr.value, int)
        and not isinstance(expr.value, bool)
    ):
        return frozenset({expr.value})
    if isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.USub):
        return frozenset(-value for value in _eval_int_expr(expr.operand, names))
    if isinstance(expr, ast.Name):
        if expr.id in names:
            return names[expr.id]
        if expr.id == "_MATCH_MAGNITUDE":
            return frozenset({100})
        if expr.id == "color" or expr.id.endswith("_color"):
            return frozenset({-1, 1})
        return frozenset()
    if isinstance(expr, ast.BinOp):
        left = _eval_int_expr(expr.left, names)
        right = _eval_int_expr(expr.right, names)
        if isinstance(expr.op, ast.Mult):
            return frozenset(
                left_value * right_value for left_value in left for right_value in right
            )
        if isinstance(expr.op, ast.Add):
            return frozenset(
                left_value + right_value for left_value in left for right_value in right
            )
        if isinstance(expr.op, ast.Sub):
            return frozenset(
                left_value - right_value for left_value in left for right_value in right
            )
    if isinstance(expr, ast.IfExp):
        return _eval_int_expr(expr.body, names) | _eval_int_expr(expr.orelse, names)
    if isinstance(expr, ast.Call):
        if isinstance(expr.func, ast.Name):
            if expr.func.id == "_mat_hold_with_penetration":
                return frozenset({0, 100})
            if expr.func.id == "_signed_hundred":
                return frozenset({-100, 100})
            if expr.func.id == "candle_color":
                return frozenset({-1, 1})
    return frozenset()


def _function_node(judge: IntegerJudge) -> ast.FunctionDef:
    module = ast.parse(textwrap.dedent(inspect.getsource(judge)))
    functions = [node for node in module.body if isinstance(node, ast.FunctionDef)]
    assert len(functions) == 1
    return functions[0]


def _inferred_stateless_nonzero_values(judge: IntegerJudge) -> frozenset[int]:
    function = _function_node(judge)
    assigned: dict[str, set[int]] = {}

    for node in ast.walk(function):
        if not isinstance(node, ast.Assign):
            continue
        names = {name: frozenset(values) for name, values in assigned.items()}
        assigned_values = _eval_int_expr(node.value, names)
        for target in node.targets:
            if isinstance(target, ast.Name):
                assigned.setdefault(target.id, set()).update(assigned_values)

    names = {name: frozenset(values) for name, values in assigned.items()}
    return_values: set[int] = set()
    for node in ast.walk(function):
        if isinstance(node, ast.Return) and node.value is not None:
            return_values.update(_eval_int_expr(node.value, names))

    nonzero_values = frozenset(value for value in return_values if value != 0)
    assert nonzero_values, f"could not infer source values for {judge.__name__}"
    return nonzero_values


def _source_nonzero_values(port: TalibDocPort) -> frozenset[int]:
    if isinstance(port, TalibStatefulPatternPort):
        return frozenset({-200, -100, 100, 200})
    return _inferred_stateless_nonzero_values(port._judge)


def _observed_nonzero_values(talib_function: str) -> frozenset[int]:
    assert CAPTURED, CAPTURE_INSTRUCTIONS
    values: set[int] = set()
    for regime in REGIME_NAMES:
        values.update(SIGNALS[regime][talib_function].values())
    return frozenset(values)


def _port_setting_names(port: TalibDocPort) -> frozenset[str]:
    if isinstance(port, TalibPatternPort):
        return frozenset(key[0].value for key in port.average_keys)

    state = port.make_state()
    if state._near_average is None:
        return frozenset()
    return frozenset({state._near_average.setting_type.value})


def test_standard_candle_settings_table_matches_defaults() -> None:
    rows = _table(("설정", "범위", "평균 기간", "계수"))

    assert [_strip_code(row["설정"]) for row in rows] == [
        setting_type.value for setting_type in CANDLE_SETTING_ORDER
    ]

    for row, setting_type in zip(rows, CANDLE_SETTING_ORDER, strict=True):
        setting = DEFAULT_CANDLE_SETTINGS[setting_type]
        assert _strip_code(row["설정"]) == setting.setting_type.value
        assert _strip_code(row["범위"]) == setting.range_type.value
        assert int(row["평균 기간"]) == setting.avg_period
        assert float(row["계수"]) == setting.factor


def test_standard_pattern_table_matches_talib_ports_and_capture() -> None:
    headers = (
        "우리 이름",
        "TA-Lib 함수",
        "워밍업",
        "쓰는 설정",
        "소스상 비영 raw",
        "22000봉 관측 비영 raw",
    )
    rows = _table(headers)
    ports = {port.name: port for port in _ALL_TALIB_PORTS}

    assert set(ports) == set(TALIB_FUNCTIONS)
    assert {_strip_code(row["우리 이름"]) for row in rows} == set(ports)
    assert len(rows) == len(ports) == 61

    for row in rows:
        name = _strip_code(row["우리 이름"])
        talib_function = _strip_code(row["TA-Lib 함수"])
        port = ports[name]

        assert talib_function == TALIB_FUNCTIONS[name]
        assert int(row["워밍업"]) == port.min_history
        assert _parse_setting_names(row["쓰는 설정"]) == _port_setting_names(port)

        source_values = _parse_int_values(row["소스상 비영 raw"])
        observed_values = _parse_int_values(row["22000봉 관측 비영 raw"])

        assert source_values == _source_nonzero_values(port)
        assert observed_values == _observed_nonzero_values(talib_function)
        assert source_values <= TALIB_RAW_ALLOWED_VALUES
        assert observed_values <= source_values
