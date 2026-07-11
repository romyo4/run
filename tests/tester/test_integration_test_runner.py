import unittest

from tester.errors import TestExecutionError
from tester.models import CommandExecutionResult
from tester.runners.integration_test_runner import run_integration_tests
from tests.tester.fakes import FakeCommandExecutor, make_implementation, make_tester_config


class RunIntegrationTestsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.implementation = make_implementation()
        self.config = make_tester_config(integration_test_command=["pytest", "tests/integration"])

    def test_run_integration_tests_returns_report_with_all_cases_passed(self) -> None:
        stdout = "\n".join(
            [
                "test_integration_a|pass|0.10|",
                "test_integration_b|pass|0.20|",
            ]
        )
        executor = FakeCommandExecutor(
            default_result=CommandExecutionResult(exit_code=0, stdout=stdout, stderr="", duration_seconds=0.5)
        )

        result = run_integration_tests(self.implementation, self.config, executor)

        self.assertTrue(result.success)
        report = result.value
        self.assertEqual(report.test_type, "integration")
        self.assertEqual(report.total, 2)
        self.assertEqual(report.failed, 0)
        self.assertTrue(report.is_pass)

    def test_run_integration_tests_returns_report_with_failed_case_recorded(self) -> None:
        stdout = "\n".join(
            [
                "test_integration_a|pass|0.10|",
                "test_integration_b|fail|0.20|connection refused",
            ]
        )
        executor = FakeCommandExecutor(
            default_result=CommandExecutionResult(exit_code=1, stdout=stdout, stderr="", duration_seconds=0.5)
        )

        result = run_integration_tests(self.implementation, self.config, executor)

        self.assertTrue(result.success)
        report = result.value
        self.assertEqual(report.failed, 1)
        self.assertFalse(report.is_pass)
        failed_case = next(case for case in report.cases if not case.passed)
        self.assertEqual(failed_case.name, "test_integration_b")
        self.assertIn("connection refused", failed_case.failure_message)

    def test_run_integration_tests_returns_failure_result_on_tool_execution_error(self) -> None:
        executor = FakeCommandExecutor(raise_error=RuntimeError("test runner crashed"))

        result = run_integration_tests(self.implementation, self.config, executor)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, TestExecutionError)


if __name__ == "__main__":
    unittest.main()
