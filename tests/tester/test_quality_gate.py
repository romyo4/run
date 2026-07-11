import unittest

from tester.quality_gate import (
    determine_gate_status,
    evaluate_quality_gate,
    judge_build,
    judge_integration_test,
    judge_lint,
    judge_regression_test,
    judge_static_analysis,
    judge_unit_test,
)
from tests.tester.fakes import (
    make_build_report,
    make_lint_report,
    make_passing_test_result,
    make_static_analysis_report,
    make_test_execution_report,
)


class JudgeBuildTestCase(unittest.TestCase):
    def test_judge_build_passes_on_success_status(self) -> None:
        result = judge_build(make_build_report(success=True))
        self.assertTrue(result.passed)
        self.assertEqual(result.item_name, "build")

    def test_judge_build_fails_on_failure_status(self) -> None:
        result = judge_build(make_build_report(success=False))
        self.assertFalse(result.passed)


class JudgeLintTestCase(unittest.TestCase):
    def test_judge_lint_passes_when_no_error(self) -> None:
        result = judge_lint(make_lint_report(error_count=0, warning_count=0))
        self.assertTrue(result.passed)

    def test_judge_lint_fails_when_error_count_positive(self) -> None:
        result = judge_lint(make_lint_report(error_count=1, warning_count=0))
        self.assertFalse(result.passed)

    def test_judge_lint_passes_when_only_warnings_present(self) -> None:
        result = judge_lint(make_lint_report(error_count=0, warning_count=5))
        self.assertTrue(result.passed)


class JudgeUnitTestTestCase(unittest.TestCase):
    def test_judge_unit_test_passes_when_all_pass(self) -> None:
        report = make_test_execution_report(total=3, passed=3, failed=0)
        self.assertTrue(judge_unit_test(report).passed)

    def test_judge_unit_test_fails_when_any_case_fails(self) -> None:
        report = make_test_execution_report(total=3, passed=2, failed=1)
        self.assertFalse(judge_unit_test(report).passed)


class JudgeIntegrationTestTestCase(unittest.TestCase):
    def test_judge_integration_test_passes_when_all_pass(self) -> None:
        report = make_test_execution_report(test_type="integration", total=2, passed=2, failed=0)
        self.assertTrue(judge_integration_test(report).passed)

    def test_judge_integration_test_fails_when_any_case_fails(self) -> None:
        report = make_test_execution_report(test_type="integration", total=2, passed=1, failed=1)
        self.assertFalse(judge_integration_test(report).passed)


class JudgeRegressionTestTestCase(unittest.TestCase):
    def test_judge_regression_test_passes_when_all_pass(self) -> None:
        report = make_test_execution_report(test_type="regression", total=1, passed=1, failed=0)
        self.assertTrue(judge_regression_test(report).passed)

    def test_judge_regression_test_fails_when_any_case_fails(self) -> None:
        report = make_test_execution_report(test_type="regression", total=1, passed=0, failed=1)
        self.assertFalse(judge_regression_test(report).passed)


class JudgeStaticAnalysisTestCase(unittest.TestCase):
    def test_judge_static_analysis_passes_when_no_critical_error(self) -> None:
        report = make_static_analysis_report(critical_count=0)
        self.assertTrue(judge_static_analysis(report).passed)

    def test_judge_static_analysis_fails_when_critical_error_present(self) -> None:
        report = make_static_analysis_report(critical_count=1)
        self.assertFalse(judge_static_analysis(report).passed)


class DetermineGateStatusTestCase(unittest.TestCase):
    def test_determine_gate_status_returns_pass_when_all_items_passed(self) -> None:
        items = [judge_build(make_build_report(success=True)), judge_lint(make_lint_report())]
        self.assertEqual(determine_gate_status(items), "PASS")

    def test_determine_gate_status_returns_fail_when_one_item_failed(self) -> None:
        items = [
            judge_build(make_build_report(success=True)),
            judge_lint(make_lint_report(error_count=1)),
        ]
        self.assertEqual(determine_gate_status(items), "FAIL")

    def test_determine_gate_status_returns_fail_when_all_items_failed(self) -> None:
        items = [
            judge_build(make_build_report(success=False)),
            judge_lint(make_lint_report(error_count=1)),
        ]
        self.assertEqual(determine_gate_status(items), "FAIL")


class EvaluateQualityGateTestCase(unittest.TestCase):
    def test_evaluate_quality_gate_returns_six_items_in_fixed_order(self) -> None:
        test_result = make_passing_test_result()
        result = evaluate_quality_gate(test_result)
        self.assertTrue(result.success)
        items = result.value
        self.assertEqual(len(items), 6)
        self.assertEqual(
            [item.item_name for item in items],
            [
                "build",
                "lint",
                "unit_test",
                "integration_test",
                "regression_test",
                "static_analysis",
            ],
        )
        self.assertTrue(all(item.passed for item in items))

    def test_evaluate_quality_gate_returns_failure_result_when_test_result_is_none(self) -> None:
        result = evaluate_quality_gate(None)
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)

    def test_evaluate_quality_gate_returns_failure_result_when_metadata_missing_report(
        self,
    ) -> None:
        test_result = make_passing_test_result()
        del test_result.metadata["static_analysis_report"]
        result = evaluate_quality_gate(test_result)
        self.assertFalse(result.success)


if __name__ == "__main__":
    unittest.main()
