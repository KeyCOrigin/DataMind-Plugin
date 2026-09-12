from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages/contracts/src"))
sys.path.insert(0, str(ROOT / "services/dataplane/src"))
sys.path.insert(0, str(ROOT / "plugins/datamind-context/vendor/datamind-0.3.2-py3-none-any.whl"))

from datamind_dataplane.authorization import authorize
from datamind_dataplane.tools import catalog
from datamind_dataplane.utility_tools import build_utility_tools, calculate, current_time
from datamind_contracts import AuthorizationError
from datamind.core.tools import ToolRegistry


def test_calculator_handles_arithmetic_and_functions() -> None:
    assert calculate("2 + 3 * 4")["result"] == 14
    assert calculate("sqrt(144)")["result"] == 12
    assert calculate("sin(pi / 2)")["result"] == pytest.approx(1)


@pytest.mark.parametrize("expression", [
    "__import__('os')",
    "(1).__class__",
    "open('secret')",
    "[x for x in range(3)]",
    "1 + " * 200,
])
def test_calculator_rejects_code_and_complex_expressions(expression: str) -> None:
    with pytest.raises(ValueError):
        calculate(expression)


def test_calculator_rejects_unsafe_exponent() -> None:
    with pytest.raises(ValueError, match="安全范围"):
        calculate("2 ** 1001")


def test_current_time_returns_requested_timezone_and_iso_values() -> None:
    result = current_time("Asia/Shanghai")
    assert result["timezone"] == "Asia/Shanghai"
    assert result["datetime"].endswith("+08:00")
    assert len(result["date"]) == 10
    assert result["utc"].endswith("+00:00")


def test_current_time_rejects_unknown_timezone() -> None:
    with pytest.raises(ValueError, match="不支持的时区"):
        current_time("Not/A_Timezone")


@pytest.mark.asyncio
async def test_utility_tools_are_read_only_and_role_scoped() -> None:
    specs = {spec.name: spec for spec in build_utility_tools()}
    assert set(specs) == {"utility_calculate", "utility_current_time"}
    assert all(spec.access.value == "utility" for spec in specs.values())
    assert (await specs["utility_calculate"].handler(expression="6 * 7"))["result"] == 42
    assert (await specs["utility_current_time"].handler(timezone="UTC"))["timezone"] == "UTC"

    authorize("utility_calculate", {"datamind.dataplane.read"})
    authorize("utility_current_time", {"datamind.dataplane.admin"})
    for scope in ({"datamind.dataplane.write"}, {"datamind.dataplane.external_write"}):
        with pytest.raises(AuthorizationError):
            authorize("utility_calculate", scope)

    registry = ToolRegistry()
    registry.extend(build_utility_tools())
    listing = catalog(registry, {"datamind.dataplane.read"})
    assert {item["name"] for item in listing} == set(specs)
    assert all(item["annotations"]["readOnlyHint"] for item in listing)
