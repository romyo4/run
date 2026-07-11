"""Build確認の実行(IS10 4.3節 run_build_check)。

外部ビルドコマンドの実行は`CommandExecutor`(Protocol, `tester.models`)を通じてのみ行う。
本関数はコマンド実行結果(終了コード・標準出力)を解析し`BuildReport`へマッピングするのみで、
合否判定ロジックは持たない(判定は`tester.quality_gate.judge_build`に集約)。
"""

from __future__ import annotations

from foundation.errors import ValidationError
from foundation.result import Result
from foundation.types import Implementation
from foundation.validation import require_not_none
from tester.errors import TesterValidationError, TestExecutionError
from tester.models import BuildReport, BuildStatus, CommandExecutor, TesterConfig
from tester.runners import _execute_command

__all__ = ["run_build_check"]

_LOG_EXCERPT_MAX_CHARS = 4000


def run_build_check(
    implementation: Implementation,
    config: TesterConfig,
    executor: CommandExecutor | None = None,
) -> Result[BuildReport]:
    """設定されたBuildコマンドを実行し、結果を`BuildReport`として返す。"""
    try:
        require_not_none(implementation, "implementation")
        require_not_none(config, "config")
    except ValidationError as exc:
        return Result(success=False, error=TesterValidationError(str(exc)))

    command = list(config.build_command)
    try:
        execution = _execute_command(executor, command, config.command_timeout_seconds)
    except TestExecutionError as exc:
        return Result(success=False, error=exc)

    status = BuildStatus.SUCCESS if execution.exit_code == 0 else BuildStatus.FAILURE
    combined_output = (execution.stdout or "") + (execution.stderr or "")
    error_message = None
    if status is BuildStatus.FAILURE:
        error_message = (execution.stderr.strip() or execution.stdout.strip() or "build command failed")[
            -_LOG_EXCERPT_MAX_CHARS:
        ]

    report = BuildReport(
        status=status,
        command=command,
        duration_seconds=execution.duration_seconds,
        log_excerpt=combined_output[-_LOG_EXCERPT_MAX_CHARS:],
        error_message=error_message,
    )
    return Result(success=True, value=report)
