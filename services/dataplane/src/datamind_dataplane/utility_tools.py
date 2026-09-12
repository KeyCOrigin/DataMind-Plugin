"""Read-only utility tools for the internal DataPlane.

The calculator uses an allow-listed AST evaluator instead of ``eval`` so a
model cannot turn a math request into arbitrary Python execution.
"""
from __future__ import annotations

import ast
import math
from datetime import datetime, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


_MAX_EXPRESSION_LENGTH = 512
_MAX_AST_NODES = 80
_MAX_RESULT_MAGNITUDE = 1e300

_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "log": math.log, "log10": math.log10, "exp": math.exp,
    "ceil": math.ceil, "floor": math.floor, "fabs": math.fabs,
    "abs": abs, "round": round, "pow": pow, "min": min, "max": max,
}
_CONSTANTS = {"pi": math.pi, "e": math.e, "tau": math.tau}
_BINARY_OPERATORS: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: lambda left, right: left + right,
    ast.Sub: lambda left, right: left - right,
    ast.Mult: lambda left, right: left * right,
    ast.Div: lambda left, right: left / right,
    ast.FloorDiv: lambda left, right: left // right,
    ast.Mod: lambda left, right: left % right,
    ast.Pow: lambda left, right: left ** right,
}


def _validate_number(value: Any) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("只允许整数或实数")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("结果必须是有限数值")
    if abs(value) > _MAX_RESULT_MAGNITUDE:
        raise ValueError("数值超过安全范围")
    return value


def _evaluate(node: ast.AST) -> int | float:
    if isinstance(node, ast.Constant):
        return _validate_number(node.value)
    if isinstance(node, ast.Name):
        if node.id not in _CONSTANTS:
            raise ValueError(f"不支持的名称: {node.id}")
        return _CONSTANTS[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _evaluate(node.operand)
        return _validate_number(value if isinstance(node.op, ast.UAdd) else -value)
    if isinstance(node, ast.BinOp):
        operator = next((fn for kind, fn in _BINARY_OPERATORS.items() if isinstance(node.op, kind)), None)
        if operator is None:
            raise ValueError("不支持的运算符")
        left = _evaluate(node.left)
        right = _evaluate(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 1000:
            raise ValueError("幂指数超过安全范围")
        return _validate_number(operator(left, right))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        function = _FUNCTIONS.get(node.func.id)
        if function is None or node.keywords:
            raise ValueError(f"不支持的函数: {getattr(node.func, 'id', '')}")
        return _validate_number(function(*[_evaluate(argument) for argument in node.args]))
    raise ValueError("表达式包含不允许的语法")


def calculate(expression: str) -> dict[str, Any]:
    """Safely evaluate a bounded arithmetic expression."""
    if not isinstance(expression, str) or not expression.strip():
        raise ValueError("expression 不能为空")
    expression = expression.strip()
    if len(expression) > _MAX_EXPRESSION_LENGTH:
        raise ValueError(f"expression 不能超过 {_MAX_EXPRESSION_LENGTH} 个字符")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError("expression 不是有效的数学表达式") from exc
    if sum(1 for _ in ast.walk(tree)) > _MAX_AST_NODES:
        raise ValueError("expression 结构过于复杂")
    try:
        result = _evaluate(tree.body)
    except (ArithmeticError, TypeError, ValueError) as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError(f"计算失败: {exc}") from exc
    return {"expression": expression, "result": result}


def current_time(timezone_name: str = "UTC") -> dict[str, Any]:
    """Return current time in a standard IANA timezone."""
    requested = (timezone_name or "UTC").strip()
    if requested.casefold() in {"local", "system"}:
        zone = datetime.now().astimezone().tzinfo
        label = "local"
    else:
        try:
            zone = ZoneInfo(requested)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"不支持的时区: {requested}") from exc
        label = requested
    now = datetime.now(zone)
    utc_now = now.astimezone(timezone.utc)
    local_now = datetime.now().astimezone()
    return {
        "timezone": label,
        "datetime": now.isoformat(timespec="seconds"),
        "date": now.date().isoformat(),
        "time": now.strftime("%H:%M:%S"),
        "weekday": now.isoweekday(),
        "utc": utc_now.isoformat(timespec="seconds"),
        "local": local_now.isoformat(timespec="seconds"),
    }


def build_utility_tools() -> list[Any]:
    """Build utility ToolSpecs; both tools are read-only and side-effect free."""
    from datamind.core.tools import ToolSpec

    async def _calculate_handler(expression: str) -> dict[str, Any]:
        return calculate(expression)

    async def _current_time_handler(timezone: str = "UTC") -> dict[str, Any]:
        return current_time(timezone)

    return [
        ToolSpec(
            name="utility_calculate",
            description=(
                "安全计算数学表达式。支持加减乘除、整除、取模、幂、括号、"
                "sqrt/sin/cos/tan/log/log10/ceil/floor/abs/round/min/max 以及 pi、e、tau；"
                "不执行任意 Python。"
            ),
            input_schema={
                "type": "object",
                "properties": {"expression": {"type": "string", "maxLength": _MAX_EXPRESSION_LENGTH}},
                "required": ["expression"],
                "additionalProperties": False,
            },
            handler=_calculate_handler,
            metadata={"group": "utility", "access": "utility"},
        ),
        ToolSpec(
            name="utility_current_time",
            description="获取当前时间。timezone 使用 IANA 时区名，例如 Asia/Shanghai、UTC 或 local。",
            input_schema={
                "type": "object",
                "properties": {"timezone": {"type": "string", "default": "UTC"}},
                "additionalProperties": False,
            },
            handler=_current_time_handler,
            metadata={"group": "utility", "access": "utility"},
        ),
    ]


__all__ = ["build_utility_tools", "calculate", "current_time"]
