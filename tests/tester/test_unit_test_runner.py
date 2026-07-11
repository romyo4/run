import unittest

from tester.errors import TestExecutionError
from tester.models import CommandExecutionResult
from tester.runners.unit_test_runner import run_unit_tests
from tests.tester.fakes import FakeCommandExecutor, make_implementation, make_tester_config


class RunUnitTestsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.implementation = make_implementation()
        self.config = make_tester_config(unit_test_command=["pytest", "tests/unit"])

    def test_run_unit_tests_returns_report_with_all_cases_passed(self) -> None:
        stdout = "\n".join(
            [
                "test_a|pass|0.01|",
                "test_b|pass|0.02|",
            ]
        )
        executor = FakeCommandExecutor(
            default_result=CommandExecutionResult(exit_code=0, stdout=stdout, stderr="", duration_seconds=0.5)
        )

        result = run_unit_tests(self.implementation, self.config, executor)

        self.assertTrue(result.success)
        report = result.value
        self.assertEqual(report.test_type, "unit")
        self.assertEqual(report.total, 2)
        self.assertEqual(report.passed, 2)
        self.assertEqual(report.failed, 0)
        self.assertTrue(report.is_pass)

    def test_run_unit_tests_returns_report_with_failed_case_recorded(self) -> None:
        stdout = "\n".join(
            [
                "test_a|pass|0.01|",
                "test_b|fail|0.02|AssertionError: expected 1 got 2",
            ]
        )
        executor = FakeCommandExecutor(
            default_result=CommandExecutionResult(exit_code=1, stdout=stdout, stderr="", duration_seconds=0.5)
        )

        result = run_unit_tests(self.implementation, self.config, executor)

        self.assertTrue(result.success)
        report = result.value
        self.assertEqual(report.total, 2)
        self.assertEqual(report.passed, 1)
        self.assertEqual(report.failed, 1)
        self.assertFalse(report.is_pass)
        failed_case = next(case for case in report.cases if not case.passed)
        self.assertEqual(failed_case.name, "test_b")
        self.assertIn("AssertionError", failed_case.failure_message)

    def test_run_unit_tests_returns_failure_result_on_tool_execution_error(self) -> None:
        executor = FakeCommandExecutor(raise_error=RuntimeError("test runner crashed"))

        result = run_unit_tests(self.implementation, self.config, executor)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, TestExecutionError)


if __name__ == "__main__":
    unittest.main()
