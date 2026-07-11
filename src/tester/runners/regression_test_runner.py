"""Regression Testの実行(IS10 4.3節 run_regression_tests)。

外部テストランナーコマンドの実行は`CommandExecutor`(Protocol)を通じてのみ行う。標準出力を
`name|status|duration_seconds|failure_message`形式(1行1ケース、statusは"pass"/"fail"/"skip")
として解析し`TestExecutionReport`へマッピングするのみで、合否判定ロジックは持たない
(判定は`tester.quality_gate.judge_regression_test`に集約)。
"""

from __future__ import annotations

from foundation.errors import ValidationError
from foundation.result import Result
from foundation.types import Implementation
from foundation.validation import require_not_none
from tester.errors import TesterValidationError, TestExecutionError
from tester.models import CommandExecutor, TestCaseResult, TesterConfig, TestExecutionReport
from tester.runners import _execute_command, _parse_case_line

__all__ = ["run_regression_tests"]

_TEST_TYPE = "regression"


def run_regression_tests(
    implementation: Implementation,
    config: TesterConfig,
    executor: CommandExecutor | None = None,
) -> Result[TestExecutionReport]:
    """設定されたRegression Testコマンドを実行し、結果を`TestExecutionReport`として返す。"""
    try:
        require_not_none(implementation, "implementation")
        require_not_none(config, "config")
    except ValidationError as exc:
        return Result(success=False, error=TesterValidationError(str(exc)))

    command = list(config.regression_test_command)
    try:
        execution = _execute_command(executor, command, config.command_timeout_seconds)
    except TestExecutionError as exc:
        return Result(success=False, error=exc)

    cases: list[TestCaseResult] = []
    skipped = 0
    for raw_line in (execution.stdout or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parsed = _parse_case_line(line)
        if parsed is None:
            continue
        name, status, duration_seconds, failure_message = parsed
        if status == "skip":
            skipped += 1
            continue
        cases.append(
            TestCaseResult(
                name=name,
                passed=status == "pass",
                duration_seconds=duration_seconds,
                failure_message=failure_message,
            )
        )

    passed = sum(1 for case in cases if case.passed)
    failed = sum(1 for case in cases if not case.passed)

    report = TestExecutionReport(
        test_type=_TEST_TYPE,
        total=len(cases) + skipped,
        passed=passed,
        failed=failed,
        skipped=skipped,
        cases=cases,
        duration_seconds=execution.duration_seconds,
    )
    return Result(success=True, value=report)
