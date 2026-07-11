"""Static Analysisの実行(IS10 4.3節 run_static_analysis)。

外部静的解析ツールコマンドの実行は`CommandExecutor`(Protocol)を通じてのみ行う。標準出力を
`severity|file_path|line|rule|message`形式(1行1件、severityは"critical"/"major"/"minor"/
"info")として解析し`StaticAnalysisReport`へマッピングするのみで、合否判定ロジックは持たない
(判定は`tester.quality_gate.judge_static_analysis`に集約)。
"""

from __future__ import annotations

from pathlib import Path

from foundation.errors import ValidationError
from foundation.result import Result
from foundation.types import Implementation
from foundation.validation import require_not_none
from tester.errors import TesterValidationError, TestExecutionError
from tester.models import CommandExecutor, StaticAnalysisIssue, StaticAnalysisReport, TesterConfig
from tester.runners import _execute_command, _parse_issue_line

__all__ = ["run_static_analysis"]


def run_static_analysis(
    implementation: Implementation,
    config: TesterConfig,
    executor: CommandExecutor | None = None,
) -> Result[StaticAnalysisReport]:
    """設定されたStatic Analysisコマンドを実行し、結果を`StaticAnalysisReport`として返す。"""
    try:
        require_not_none(implementation, "implementation")
        require_not_none(config, "config")
    except ValidationError as exc:
        return Result(success=False, error=TesterValidationError(str(exc)))

    command = list(config.static_analysis_command)
    try:
        execution = _execute_command(executor, command, config.command_timeout_seconds)
    except TestExecutionError as exc:
        return Result(success=False, error=exc)

    issues: list[StaticAnalysisIssue] = []
    for raw_line in (execution.stdout or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parsed = _parse_issue_line(line)
        if parsed is None:
            continue
        file_path, line_number, rule, severity, message = parsed
        issues.append(
            StaticAnalysisIssue(
                file_path=Path(file_path),
                line=line_number,
                rule=rule,
                severity=severity,
                message=message,
            )
        )

    critical_count = sum(1 for issue in issues if issue.severity == "critical")

    report = StaticAnalysisReport(
        critical_count=critical_count,
        issues=issues,
        duration_seconds=execution.duration_seconds,
    )
    return Result(success=True, value=report)
