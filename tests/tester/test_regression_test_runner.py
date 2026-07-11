import unittest

from tester.errors import TestExecutionError
from tester.models import CommandExecutionResult
from tester.runners.regression_test_runner import run_regression_tests
from tests.tester.fakes import FakeCommandExecutor, make_implementation, make_tester_config


class RunRegressionTestsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.implementation = make_implementation()
        self.config = make_tester_config(regression_test_command=["pytest", "tests/regression"])

    def test_run_regression_tests_returns_report_with_all_cases_passed(self) -> None:
        stdout = "\n".join(
            [
                "test_regression_a|pass|0.05|",
            ]
        )
        executor = FakeCommandExecutor(
            default_result=CommandExecutionResult(exit_code=0, stdout=stdout, stderr="", duration_seconds=0.5)
        )

        result = run_regression_tests(self.implementation, self.config, executor)

        self.assertTrue(result.success)
        report = result.value
        self.assertEqual(report.test_type, "regression")
        self.assertEqual(report.total, 1)
        self.assertEqual(report.failed, 0)
        self.assertTrue(report.is_pass)

    def test_run_regression_tests_returns_report_with_failed_case_recorded(self) -> None:
        stdout = "\n".join(
            [
                "test_regression_a|fail|0.05|regression detected",
            ]
        )
        executor = FakeCommandExecutor(
            default_result=CommandExecutionResult(exit_code=1, stdout=stdout, stderr="", duration_seconds=0.5)
        )

        result = run_regression_tests(self.implementation, self.config, executor)

        self.assertTrue(result.success)
        report = result.value
        self.assertEqual(report.failed, 1)
        self.assertFalse(report.is_pass)
        failed_case = report.cases[0]
        self.assertFalse(failed_case.passed)
        self.assertIn("regression detected", failed_case.failure_message)

    def test_run_regression_tests_returns_failure_result_on_tool_execution_error(self) -> None:
        executor = FakeCommandExecutor(raise_error=RuntimeError("test runner crashed"))

        result = run_regression_tests(self.implementation, self.config, executor)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, TestExecutionError)


if __name__ == "__main__":
    unittest.main()
