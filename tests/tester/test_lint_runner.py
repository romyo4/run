import unittest

from tester.errors import TestExecutionError
from tester.models import CommandExecutionResult
from tester.runners.lint_runner import run_lint_check
from tests.tester.fakes import FakeCommandExecutor, make_implementation, make_tester_config


class RunLintCheckTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.implementation = make_implementation()
        self.config = make_tester_config(lint_command=["ruff", "check"])

    def test_run_lint_check_parses_error_and_warning_counts(self) -> None:
        stdout = "\n".join(
            [
                "error|src/foo.py|10|E001|unused import",
                "warning|src/bar.py|20|W002|line too long",
                "error|src/baz.py|30|E003|undefined name",
            ]
        )
        executor = FakeCommandExecutor(
            default_result=CommandExecutionResult(exit_code=1, stdout=stdout, stderr="", duration_seconds=0.2)
        )

        result = run_lint_check(self.implementation, self.config, executor)

        self.assertTrue(result.success)
        report = result.value
        self.assertEqual(report.error_count, 2)
        self.assertEqual(report.warning_count, 1)
        self.assertEqual(len(report.issues), 3)
        self.assertTrue(report.has_error)

    def test_run_lint_check_returns_zero_errors_when_no_issues(self) -> None:
        executor = FakeCommandExecutor(
            default_result=CommandExecutionResult(exit_code=0, stdout="", stderr="", duration_seconds=0.1)
        )

        result = run_lint_check(self.implementation, self.config, executor)

        self.assertTrue(result.success)
        report = result.value
        self.assertEqual(report.error_count, 0)
        self.assertEqual(report.warning_count, 0)
        self.assertFalse(report.has_error)

    def test_run_lint_check_returns_failure_result_on_tool_execution_error(self) -> None:
        executor = FakeCommandExecutor(raise_error=RuntimeError("linter crashed"))

        result = run_lint_check(self.implementation, self.config, executor)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, TestExecutionError)


if __name__ == "__main__":
    unittest.main()
