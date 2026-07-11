import subprocess
import unittest

from tester.errors import TesterValidationError, TestExecutionError
from tester.models import BuildStatus, CommandExecutionResult
from tester.runners.build_runner import run_build_check
from tests.tester.fakes import FakeCommandExecutor, make_implementation, make_tester_config


class RunBuildCheckTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.implementation = make_implementation()
        self.config = make_tester_config(build_command=["make", "build"])

    def test_run_build_check_returns_success_status_on_zero_exit_code(self) -> None:
        executor = FakeCommandExecutor(
            default_result=CommandExecutionResult(exit_code=0, stdout="build ok", stderr="", duration_seconds=0.5)
        )

        result = run_build_check(self.implementation, self.config, executor)

        self.assertTrue(result.success)
        report = result.value
        self.assertEqual(report.status, BuildStatus.SUCCESS)
        self.assertTrue(report.is_success)
        self.assertIsNone(report.error_message)
        self.assertEqual(report.command, ["make", "build"])

    def test_run_build_check_returns_failure_status_on_nonzero_exit_code(self) -> None:
        executor = FakeCommandExecutor(
            default_result=CommandExecutionResult(exit_code=1, stdout="", stderr="compile error", duration_seconds=0.3)
        )

        result = run_build_check(self.implementation, self.config, executor)

        self.assertTrue(result.success)
        report = result.value
        self.assertEqual(report.status, BuildStatus.FAILURE)
        self.assertFalse(report.is_success)
        self.assertIn("compile error", report.error_message)

    def test_run_build_check_returns_failure_result_when_command_not_found(self) -> None:
        executor = FakeCommandExecutor(raise_error=FileNotFoundError("make: command not found"))

        result = run_build_check(self.implementation, self.config, executor)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, TestExecutionError)

    def test_run_build_check_returns_failure_result_on_timeout(self) -> None:
        executor = FakeCommandExecutor(raise_error=subprocess.TimeoutExpired(cmd=["make", "build"], timeout=30))

        result = run_build_check(self.implementation, self.config, executor)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, TestExecutionError)

    def test_run_build_check_returns_failure_result_when_implementation_is_none(self) -> None:
        result = run_build_check(None, self.config, FakeCommandExecutor())
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, TesterValidationError)


if __name__ == "__main__":
    unittest.main()
