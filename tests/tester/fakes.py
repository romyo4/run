"""Testerテスト用の共有フェイク・ビルダー(unittestテストコードそのものではない)。

実際の外部ツール(ビルドコマンド・Linter・テストランナー・静的解析ツール)のsubprocess
呼び出しは行わない。`tester.models.CommandExecutor`インターフェース(Protocol)を満たす
決定的なフェイク実装、および各テストで再利用するテストデータビルダーを提供する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from foundation.types import Implementation, TestResult
from tester.models import (
    BuildReport,
    BuildStatus,
    CommandExecutionResult,
    LintReport,
    StaticAnalysisReport,
    TesterConfig,
    TestExecutionReport,
)


@dataclass
class FakeCommandExecutor:
    """`tester.models.CommandExecutor`プロトコルを満たすフェイク実装。

    あらかじめ登録した`CommandExecutionResult`(コマンドのタプル表現をキーとする)を
    そのまま返す決定的な実装。実際のsubprocess呼び出しは一切行わない。
    """

    results_by_command: dict[tuple[str, ...], CommandExecutionResult] = field(default_factory=dict)
    default_result: CommandExecutionResult = field(
        default_factory=lambda: CommandExecutionResult(exit_code=0, stdout="", stderr="", duration_seconds=0.01)
    )
    raise_error: Exception | None = None
    calls: list[tuple[list[str], int]] = field(default_factory=list)

    def run(self, command: list[str], timeout_seconds: int) -> CommandExecutionResult:
        self.calls.append((list(command), timeout_seconds))
        if self.raise_error is not None:
            raise self.raise_error
        return self.results_by_command.get(tuple(command), self.default_result)


def make_tester_config(**overrides: Any) -> TesterConfig:
    defaults: dict[str, Any] = dict(
        build_command=["build"],
        lint_command=["lint"],
        unit_test_command=["unit_test"],
        integration_test_command=["integration_test"],
        regression_test_command=["regression_test"],
        static_analysis_command=["static_analysis"],
        command_timeout_seconds=30,
    )
    defaults.update(overrides)
    return TesterConfig(**defaults)


def make_implementation(workflow_id: str = "workflow-1", **metadata_overrides: Any) -> Implementation:
    metadata: dict[str, Any] = {"workflow_id": workflow_id}
    metadata.update(metadata_overrides)
    return Implementation(metadata=metadata)


def make_build_report(success: bool = True) -> BuildReport:
    return BuildReport(
        status=BuildStatus.SUCCESS if success else BuildStatus.FAILURE,
        command=["build"],
        duration_seconds=0.1,
        log_excerpt="build output",
        error_message=None if success else "build failed",
    )


def make_lint_report(error_count: int = 0, warning_count: int = 0) -> LintReport:
    return LintReport(error_count=error_count, warning_count=warning_count, issues=[], duration_seconds=0.1)


def make_test_execution_report(
    test_type: str = "unit", total: int = 2, passed: int = 2, failed: int = 0, skipped: int = 0
) -> TestExecutionReport:
    return TestExecutionReport(
        test_type=test_type,
        total=total,
        passed=passed,
        failed=failed,
        skipped=skipped,
        cases=[],
        duration_seconds=0.1,
    )


def make_static_analysis_report(critical_count: int = 0) -> StaticAnalysisReport:
    return StaticAnalysisReport(critical_count=critical_count, issues=[], duration_seconds=0.1)


def make_passing_test_result(workflow_id: str = "workflow-1") -> TestResult:
    """全項目がPASSする`TestResult`(metadata経由でTester固有6レポートを保持)を作る。"""
    return TestResult(
        metadata={
            "workflow_id": workflow_id,
            "build_report": make_build_report(success=True),
            "lint_report": make_lint_report(error_count=0),
            "unit_test_report": make_test_execution_report(test_type="unit"),
            "integration_test_report": make_test_execution_report(test_type="integration"),
            "regression_test_report": make_test_execution_report(test_type="regression"),
            "static_analysis_report": make_static_analysis_report(critical_count=0),
            "duration_seconds": 1.23,
        }
    )
