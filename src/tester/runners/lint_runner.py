"""Lint確認の実行(IS10 4.3節 run_lint_check)。

外部Linterコマンドの実行は`CommandExecutor`(Protocol)を通じてのみ行う。標準出力を
`severity|file_path|line|rule|message`形式(1行1件)として解析し`LintReport`へマッピング
するのみで、合否判定ロジックは持たない(判定は`tester.quality_gate.judge_lint`に集約)。
"""

from __future__ import annotations

from pathlib import Path

from foundation.errors import ValidationError
from foundation.result import Result
from foundation.types import Implementation
from foundation.validation import require_not_none
from tester.errors import TesterValidationError, TestExecutionError
from tester.models import CommandExecutor, LintIssue, LintReport, TesterConfig
from tester.runners import _execute_command, _parse_issue_line

__all__ = ["run_lint_check"]


def run_lint_check(
    implementation: Implementation,
    config: TesterConfig,
    executor: CommandExecutor | None = None,
) -> Result[LintReport]:
    """設定されたLintコマンドを実行し、結果を`LintReport`として返す。"""
    try:
        require_not_none(implementation, "implementation")
        require_not_none(config, "config")
    except ValidationError as exc:
        return Result(success=False, error=TesterValidationError(str(exc)))

    command = list(config.lint_command)
    try:
        execution = _execute_command(executor, command, config.command_timeout_seconds)
    except TestExecutionError as exc:
        return Result(success=False, error=exc)

    issues: list[LintIssue] = []
    for raw_line in (execution.stdout or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parsed = _parse_issue_line(line)
        if parsed is None:
            continue
        file_path, line_number, rule, severity, message = parsed
        issues.append(
            LintIssue(
                file_path=Path(file_path),
                line=line_number,
                rule=rule,
                severity=severity,
                message=message,
            )
        )

    error_count = sum(1 for issue in issues if issue.severity == "error")
    warning_count = sum(1 for issue in issues if issue.severity == "warning")

    report = LintReport(
        error_count=error_count,
        warning_count=warning_count,
        issues=issues,
        duration_seconds=execution.duration_seconds,
    )
    return Result(success=True, value=report)
