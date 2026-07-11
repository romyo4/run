"""外部ツール実行系(IS10 4.3節)。

各`runners/*.py`は外部ツール(ビルドコマンド・Linter・テストランナー・静的解析ツール)を
`tester.models.CommandExecutor`(Protocol)経由で呼び出す薄いアダプタとし、Foundation
原則のAdapter Patternに従う。判定ロジック(合否基準)は`tester.quality_gate`に集約し、
`runners/`側には持たせない。

本`__init__.py`は各runner共通の「CommandExecutor呼び出し→例外をTestExecutionErrorへ
正規化」処理、および「行志向のツール出力パース」処理を共通ヘルパーとして定義したうえで、
6つのrunner関数を再エクスポートする(重複実装を避けるため)。

NOTE: 下記ヘルパー定義(`_execute_command`等)を各`runners/*.py`サブモジュールが
import するため、本ファイル内ではヘルパー定義 → サブモジュールimportの順序を厳守する
(逆順にすると循環importが未定義エラーになる)。
"""

from __future__ import annotations

from tester.errors import TestExecutionError
from tester.models import CommandExecutionResult, CommandExecutor, NotImplementedCommandExecutor

__all__ = [
    "run_build_check",
    "run_lint_check",
    "run_unit_tests",
    "run_integration_tests",
    "run_regression_tests",
    "run_static_analysis",
]


def _resolve_executor(executor: CommandExecutor | None) -> CommandExecutor:
    """`executor`が未指定の場合、既定の`NotImplementedCommandExecutor`を返す。"""
    return executor if executor is not None else NotImplementedCommandExecutor()


def _execute_command(executor: CommandExecutor | None, command: list[str], timeout_seconds: int) -> CommandExecutionResult:
    """`CommandExecutor.run()`を呼び出し、失敗は`TestExecutionError`として送出し直す。

    ツール実行そのものの失敗(起動不可・タイムアウト・異常終了・未実装)のみを対象とし、
    テスト結果がFailであること自体はここでは扱わない(呼び出し元でReportへマッピングする)。
    """
    active_executor = _resolve_executor(executor)
    try:
        return active_executor.run(command, timeout_seconds)
    except Exception as exc:  # noqa: BLE001 - 外部ツール実行時の任意の例外を一律ラップする
        raise TestExecutionError(f"command execution failed: {command} ({exc})") from exc


def _parse_issue_line(line: str) -> tuple[str, int, str, str, str] | None:
    """`severity|file_path|line|rule|message`形式の1行を解析する。

    Lint/Static Analysis共通のパース処理。解析できない行はNoneを返す(無視する)。
    戻り値は(file_path, line_number, rule, severity, message)のタプル。
    """
    parts = line.split("|", 4)
    if len(parts) != 5:
        return None
    severity, file_path, line_no, rule, message = (part.strip() for part in parts)
    try:
        line_number = int(line_no)
    except ValueError:
        return None
    if not file_path or not severity:
        return None
    return file_path, line_number, rule, severity, message


def _parse_case_line(line: str) -> tuple[str, str, float, str | None] | None:
    """`name|status|duration_seconds|failure_message`形式の1行を解析する。

    Unit/Integration/Regression Test共通のパース処理。statusは"pass"/"fail"/"skip"の
    いずれか(大文字小文字を区別しない)。解析できない行はNoneを返す(無視する)。
    戻り値は(name, status, duration_seconds, failure_message)のタプル。
    """
    parts = line.split("|", 3)
    if len(parts) < 3:
        return None
    name = parts[0].strip()
    status = parts[1].strip().lower()
    if not name or status not in ("pass", "fail", "skip"):
        return None
    try:
        duration_seconds = float(parts[2].strip())
    except ValueError:
        return None
    failure_message = parts[3].strip() if len(parts) > 3 and parts[3].strip() else None
    return name, status, duration_seconds, failure_message


# サブモジュールのimportはヘルパー定義より後に行う(循環import対策)。
from tester.runners.build_runner import run_build_check  # noqa: E402
from tester.runners.integration_test_runner import run_integration_tests  # noqa: E402
from tester.runners.lint_runner import run_lint_check  # noqa: E402
from tester.runners.regression_test_runner import run_regression_tests  # noqa: E402
from tester.runners.static_analysis_runner import run_static_analysis  # noqa: E402
from tester.runners.unit_test_runner import run_unit_tests  # noqa: E402
