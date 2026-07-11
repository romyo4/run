import unittest
from datetime import UTC, datetime

from tester.models import QualityGateResult
from tester.quality_gate import determine_gate_status, evaluate_quality_gate
from tester.report_publisher import build_test_report
from tests.tester.fakes import make_passing_test_result


def _make_gate_result(test_result, status_override: str | None = None) -> QualityGateResult:
    items_result = evaluate_quality_gate(test_result)
    assert items_result.success
    items = items_result.value
    status = status_override or determine_gate_status(items)
    now = datetime.now(UTC)
    return QualityGateResult(
        id="gate-1",
        workflow_id="workflow-1",
        test_result=test_result,
        items=items,
        status=status,
        evaluated_at=now,
        created_at=now,
        updated_at=now,
    )


class BuildTestReportTestCase(unittest.TestCase):
    def test_build_test_report_includes_all_six_reports(self) -> None:
        test_result = make_passing_test_result()
        gate_result = _make_gate_result(test_result)

        result = build_test_report(gate_result)

        self.assertTrue(result.success)
        report = result.value
        self.assertIs(report.build_report, test_result.metadata["build_report"])
        self.assertIs(report.lint_report, test_result.metadata["lint_report"])
        self.assertIs(report.unit_test_report, test_result.metadata["unit_test_report"])
        self.assertIs(report.integration_test_report, test_result.metadata["integration_test_report"])
        self.assertIs(report.regression_test_report, test_result.metadata["regression_test_report"])
        self.assertIs(report.static_analysis_report, test_result.metadata["static_analysis_report"])

    def test_build_test_report_preserves_quality_gate_status(self) -> None:
        test_result = make_passing_test_result()
        gate_result = _make_gate_result(test_result, status_override="FAIL")

        result = build_test_report(gate_result)

        self.assertTrue(result.success)
        report = result.value
        self.assertEqual(report.quality_gate_result.status, "FAIL")
        self.assertIn("FAIL", report.summary)

    def test_build_test_report_returns_failure_result_when_test_result_missing_in_gate_result(
        self,
    ) -> None:
        test_result = make_passing_test_result()
        gate_result = _make_gate_result(test_result)
        gate_result.test_result = None

        result = build_test_report(gate_result)

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)

    def test_build_test_report_returns_failure_result_when_quality_gate_result_is_none(
        self,
    ) -> None:
        result = build_test_report(None)
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)


if __name__ == "__main__":
    unittest.main()
