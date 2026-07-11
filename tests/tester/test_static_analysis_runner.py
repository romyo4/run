import unittest

from tester.errors import TestExecutionError
from tester.models import CommandExecutionResult
from tester.runners.static_analysis_runner import run_static_analysis
from tests.tester.fakes import FakeCommandExecutor, make_implementation, make_tester_config


class RunStaticAnalysisTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.implementation = make_implementation()
        self.config = make_tester_config(static_analysis_command=["semgrep", "scan"])

    def test_run_static_analysis_returns_zero_critical_when_no_issues(self) -> None:
        executor = FakeCommandExecutor(
            default_result=CommandExecutionResult(exit_code=0, stdout="", stderr="", duration_seconds=0.1)
        )

        result = run_static_analysis(self.implementation, self.config, executor)

        self.assertTrue(result.success)
        report = result.value
        self.assertEqual(report.critical_count, 0)
        self.assertFalse(report.has_critical)

    def test_run_static_analysis_returns_critical_count_matching_issues(self) -> None:
        stdout = "\n".join(
            [
                "critical|src/foo.py|1|SEC001|hardcoded credential",
                "minor|src/bar.py|2|STY001|naming convention",
                "critical|src/baz.py|3|SEC002|sql injection",
            ]
        )
        executor = FakeCommandExecutor(
            default_result=CommandExecutionResult(exit_code=1, stdout=stdout, stderr="", duration_seconds=0.2)
        )

        result = run_static_analysis(self.implementation, self.config, executor)

        self.assertTrue(result.success)
        report = result.value
        self.assertEqual(report.critical_count, 2)
        self.assertEqual(len(report.issues), 3)
        self.assertTrue(report.has_critical)

    def test_run_static_analysis_returns_failure_result_on_tool_execution_error(self) -> None:
        executor = FakeCommandExecutor(raise_error=RuntimeError("analyzer crashed"))

        result = run_static_analysis(self.implementation, self.config, executor)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, TestExecutionError)


if __name__ == "__main__":
    unittest.main()
