import unittest
from datetime import UTC, datetime

from tester.models import (
    BuildReport,
    BuildStatus,
    LintReport,
    QualityGateResult,
    StaticAnalysisReport,
    TestExecutionReport,
)
from tests.tester.fakes import make_passing_test_result


class BuildReportTestCase(unittest.TestCase):
    def test_build_report_is_success_true_when_status_success(self) -> None:
        report = BuildReport(
            status=BuildStatus.SUCCESS,
            command=["build"],
            duration_seconds=1.0,
            log_excerpt="ok",
        )
        self.assertTrue(report.is_success)

    def test_build_report_is_success_false_when_status_failure(self) -> None:
        report = BuildReport(
            status=BuildStatus.FAILURE,
            command=["build"],
            duration_seconds=1.0,
            log_excerpt="ng",
        )
        self.assertFalse(report.is_success)


class LintReportTestCase(unittest.TestCase):
    def test_lint_report_has_error_true_when_error_count_positive(self) -> None:
        report = LintReport(error_count=1, warning_count=0, issues=[], duration_seconds=0.1)
        self.assertTrue(report.has_error)

    def test_lint_report_has_error_false_when_error_count_zero(self) -> None:
        report = LintReport(error_count=0, warning_count=3, issues=[], duration_seconds=0.1)
        self.assertFalse(report.has_error)


class TestExecutionReportTestCase(unittest.TestCase):
    def test_test_execution_report_is_pass_true_when_no_failures_and_total_positive(self) -> None:
        report = TestExecutionReport(
            test_type="unit", total=3, passed=3, failed=0, skipped=0, cases=[], duration_seconds=0.1
        )
        self.assertTrue(report.is_pass)

    def test_test_execution_report_is_pass_false_when_any_failure(self) -> None:
        report = TestExecutionReport(
            test_type="unit", total=3, passed=2, failed=1, skipped=0, cases=[], duration_seconds=0.1
        )
        self.assertFalse(report.is_pass)

    def test_test_execution_report_is_pass_false_when_total_is_zero(self) -> None:
        report = TestExecutionReport(
            test_type="unit", total=0, passed=0, failed=0, skipped=0, cases=[], duration_seconds=0.1
        )
        self.assertFalse(report.is_pass)


class StaticAnalysisReportTestCase(unittest.TestCase):
    def test_static_analysis_report_has_critical_true_when_critical_count_positive(self) -> None:
        report = StaticAnalysisReport(critical_count=1, issues=[], duration_seconds=0.1)
        self.assertTrue(report.has_critical)

    def test_static_analysis_report_has_critical_false_when_critical_count_zero(self) -> None:
        report = StaticAnalysisReport(critical_count=0, issues=[], duration_seconds=0.1)
        self.assertFalse(report.has_critical)


class QualityGateResultTestCase(unittest.TestCase):
    def _make_gate_result(self, status: str) -> QualityGateResult:
        now = datetime.now(UTC)
        return QualityGateResult(
            id="gate-1",
            workflow_id="workflow-1",
            test_result=make_passing_test_result(),
            items=[],
            status=status,
            evaluated_at=now,
            created_at=now,
            updated_at=now,
        )

    def test_quality_gate_result_is_pass_true_when_status_pass(self) -> None:
        self.assertTrue(self._make_gate_result("PASS").is_pass)

    def test_quality_gate_result_is_pass_false_when_status_fail(self) -> None:
        self.assertFalse(self._make_gate_result("FAIL").is_pass)


if __name__ == "__main__":
    unittest.main()
