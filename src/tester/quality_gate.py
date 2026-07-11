"""品質ゲート判定ロジック(IS10 4.2節)。

6項目(Build/Lint/Unit Test/Integration Test/Regression Test/Static Analysis)の判定
基準はすべて本モジュールに集約する。`runners/*.py`側には合否判定ロジックを持たせない
(IS10 2節)。

各レポート(BuildReport等)は`TestResult.metadata`経由で受け渡される(models.pyの規約に
従う。Foundationの`TestResult`型定義自体は変更しない)。
"""

from __future__ import annotations

from foundation.errors import FoundationError
from foundation.result import Result
from foundation.types import TestResult
from foundation.validation import require_not_none
from tester.errors import TesterValidationError
from tester.models import (
    BuildReport,
    LintReport,
    QualityGateItemResult,
    StaticAnalysisReport,
    TestExecutionReport,
)

__all__ = [
    "evaluate_quality_gate",
    "judge_build",
    "judge_lint",
    "judge_unit_test",
    "judge_integration_test",
    "judge_regression_test",
    "judge_static_analysis",
    "determine_gate_status",
]

_REQUIRED_METADATA_KEYS = (
    "build_report",
    "lint_report",
    "unit_test_report",
    "integration_test_report",
    "regression_test_report",
    "static_analysis_report",
)


def judge_build(build_report: BuildReport) -> QualityGateItemResult:
    """条件: Build == Success"""
    passed = build_report.is_success
    detail = "build succeeded" if passed else (build_report.error_message or "build failed")
    return QualityGateItemResult(item_name="build", passed=passed, detail=detail)


def judge_lint(lint_report: LintReport) -> QualityGateItemResult:
    """条件: Lint Error件数 == 0(Warningは判定対象外)"""
    passed = not lint_report.has_error
    detail = f"lint error_count={lint_report.error_count}, warning_count={lint_report.warning_count}"
    return QualityGateItemResult(item_name="lint", passed=passed, detail=detail)


def judge_unit_test(report: TestExecutionReport) -> QualityGateItemResult:
    """条件: Unit Test すべてPass"""
    return _judge_test_execution_report("unit_test", report)


def judge_integration_test(report: TestExecutionReport) -> QualityGateItemResult:
    """条件: Integration Test すべてPass"""
    return _judge_test_execution_report("integration_test", report)


def judge_regression_test(report: TestExecutionReport) -> QualityGateItemResult:
    """条件: Regression Test すべてPass"""
    return _judge_test_execution_report("regression_test", report)


def judge_static_analysis(report: StaticAnalysisReport) -> QualityGateItemResult:
    """条件: Critical Errorなし(critical_count == 0)"""
    passed = not report.has_critical
    detail = f"static analysis critical_count={report.critical_count}"
    return QualityGateItemResult(item_name="static_analysis", passed=passed, detail=detail)


def determine_gate_status(items: list[QualityGateItemResult]) -> str:
    """全項目passed=Trueの場合のみ'PASS'、それ以外は'FAIL'を返す(設計書3.5節)。"""
    if items and all(item.passed for item in items):
        return "PASS"
    return "FAIL"


def evaluate_quality_gate(test_result: TestResult) -> Result[list[QualityGateItemResult]]:
    """6項目(Build/Lint/Unit/Integration/Regression/Static Analysis)すべてを判定する。"""
    try:
        require_not_none(test_result, "test_result")
        metadata = test_result.metadata or {}
        reports: dict[str, object] = {}
        for key in _REQUIRED_METADATA_KEYS:
            value = metadata.get(key)
            if value is None:
                raise TesterValidationError(f"test_result.metadata is missing required key '{key}'")
            reports[key] = value

        items = [
            judge_build(reports["build_report"]),
            judge_lint(reports["lint_report"]),
            judge_unit_test(reports["unit_test_report"]),
            judge_integration_test(reports["integration_test_report"]),
            judge_regression_test(reports["regression_test_report"]),
            judge_static_analysis(reports["static_analysis_report"]),
        ]
        return Result(success=True, value=items)
    except FoundationError as exc:
        return Result(success=False, error=exc)
    except Exception as exc:  # noqa: BLE001 - モジュール境界を越えて例外を送出しない(F02)
        return Result(success=False, error=TesterValidationError(str(exc)))


def _judge_test_execution_report(item_name: str, report: TestExecutionReport) -> QualityGateItemResult:
    passed = report.is_pass
    detail = (
        f"{item_name} total={report.total}, passed={report.passed}, " f"failed={report.failed}, skipped={report.skipped}"
    )
    return QualityGateItemResult(item_name=item_name, passed=passed, detail=detail)
