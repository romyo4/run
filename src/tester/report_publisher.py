"""Test Report生成ロジック(IS10 4.4節、publish_reportの実処理)。"""

from __future__ import annotations

from foundation.errors import FoundationError
from foundation.result import Result
from foundation.utils import generate_id, utc_now
from foundation.validation import require_not_none
from tester.errors import TesterValidationError
from tester.models import QualityGateResult, TestReport

__all__ = ["build_test_report"]

_REQUIRED_METADATA_KEYS = (
    "build_report",
    "lint_report",
    "unit_test_report",
    "integration_test_report",
    "regression_test_report",
    "static_analysis_report",
)


def build_test_report(quality_gate_result: QualityGateResult) -> Result[TestReport]:
    """QualityGateResult.test_resultから各Reportを取り出しTestReportを構築する。"""
    try:
        require_not_none(quality_gate_result, "quality_gate_result")
        test_result = quality_gate_result.test_result
        require_not_none(test_result, "quality_gate_result.test_result")

        metadata = test_result.metadata or {}
        reports: dict[str, object] = {}
        for key in _REQUIRED_METADATA_KEYS:
            value = metadata.get(key)
            if value is None:
                raise TesterValidationError(f"quality_gate_result.test_result.metadata is missing required key '{key}'")
            reports[key] = value

        duration_seconds = float(metadata.get("duration_seconds", 0.0))
        passed_count = sum(1 for item in quality_gate_result.items if item.passed)
        summary = (
            f"Quality Gate {quality_gate_result.status}: " f"{passed_count}/{len(quality_gate_result.items)} item(s) passed."
        )

        report = TestReport(
            id=generate_id(),
            workflow_id=quality_gate_result.workflow_id,
            quality_gate_result=quality_gate_result,
            build_report=reports["build_report"],
            lint_report=reports["lint_report"],
            unit_test_report=reports["unit_test_report"],
            integration_test_report=reports["integration_test_report"],
            regression_test_report=reports["regression_test_report"],
            static_analysis_report=reports["static_analysis_report"],
            summary=summary,
            duration_seconds=duration_seconds,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        return Result(success=True, value=report)
    except FoundationError as exc:
        return Result(success=False, error=exc)
    except Exception as exc:  # noqa: BLE001 - モジュール境界を越えて例外を送出しない(F02)
        return Result(success=False, error=TesterValidationError(str(exc)))
