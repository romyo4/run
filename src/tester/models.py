"""Tester(M10)固有のdataclass定義(IS10 3節)。

Foundation `types.py` の `TestResult` Domain(共通属性 id/created_at/updated_at/metadata)を
そのまま利用し、Tester固有の6レポート(Build/Lint/Unit/Integration/Regression/Static
Analysis)と所要時間は `TestResult.metadata` 経由で保持する(他モジュール(Executor/
PR Creator)と同じ規約。Design Freeze後のFoundation型定義自体は変更しない)。

本モジュールにはあわせて、外部ツール(ビルドコマンド・Linter・テストランナー・
静的解析ツール)呼び出しの抽象契約(`CommandExecutor` Protocol)を定義する。実際の
subprocess呼び出し実装は行わない(タスク指示により、インターフェース定義に留め、
テストではフェイク実装(`tests/tester/fakes.py`)を注入する)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from foundation.types import TestResult

__all__ = [
    "BuildStatus",
    "BuildReport",
    "LintIssue",
    "LintReport",
    "TestCaseResult",
    "TestExecutionReport",
    "StaticAnalysisIssue",
    "StaticAnalysisReport",
    "QualityGateItemResult",
    "QualityGateResult",
    "TestReport",
    "TesterConfig",
    "CommandExecutionResult",
    "CommandExecutor",
    "NotImplementedCommandExecutor",
]


class BuildStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"


@dataclass
class BuildReport:
    status: BuildStatus
    command: list[str]
    duration_seconds: float
    log_excerpt: str
    error_message: str | None = None

    @property
    def is_success(self) -> bool:
        return self.status is BuildStatus.SUCCESS


@dataclass
class LintIssue:
    file_path: Path
    line: int
    rule: str
    severity: str  # "error" | "warning"
    message: str


@dataclass
class LintReport:
    error_count: int
    warning_count: int
    issues: list[LintIssue]
    duration_seconds: float

    @property
    def has_error(self) -> bool:
        return self.error_count > 0


@dataclass
class TestCaseResult:
    name: str
    passed: bool
    duration_seconds: float
    failure_message: str | None = None


@dataclass
class TestExecutionReport:
    """Unit Test / Integration Test / Regression Test 共通の実行結果"""

    test_type: str  # "unit" | "integration" | "regression"
    total: int
    passed: int
    failed: int
    skipped: int
    cases: list[TestCaseResult]
    duration_seconds: float

    @property
    def is_pass(self) -> bool:
        return self.total > 0 and self.failed == 0


@dataclass
class StaticAnalysisIssue:
    file_path: Path
    line: int
    rule: str
    severity: str  # "critical" | "major" | "minor" | "info"
    message: str


@dataclass
class StaticAnalysisReport:
    critical_count: int
    issues: list[StaticAnalysisIssue]
    duration_seconds: float

    @property
    def has_critical(self) -> bool:
        return self.critical_count > 0


@dataclass
class QualityGateItemResult:
    item_name: str  # "build" | "lint" | "unit_test" | "integration_test" | "regression_test" | "static_analysis"
    passed: bool
    detail: str


@dataclass
class QualityGateResult:
    id: str
    workflow_id: str
    test_result: TestResult
    items: list[QualityGateItemResult]
    status: str  # "PASS" | "FAIL"
    evaluated_at: datetime
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_pass(self) -> bool:
        return self.status == "PASS"


@dataclass
class TestReport:
    id: str
    workflow_id: str
    quality_gate_result: QualityGateResult
    build_report: BuildReport
    lint_report: LintReport
    unit_test_report: TestExecutionReport
    integration_test_report: TestExecutionReport
    regression_test_report: TestExecutionReport
    static_analysis_report: StaticAnalysisReport
    summary: str
    duration_seconds: float
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TesterConfig:
    """F03: ConfigurationClient.get("tester", key) 経由で取得する設定値の型"""

    build_command: list[str]
    lint_command: list[str]
    unit_test_command: list[str]
    integration_test_command: list[str]
    regression_test_command: list[str]
    static_analysis_command: list[str]
    command_timeout_seconds: int


@dataclass(frozen=True)
class CommandExecutionResult:
    """外部コマンド実行結果の生データ(終了コード・標準出力・標準エラー・所要時間)。"""

    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float


class CommandExecutor(Protocol):
    """外部ツール(ビルドコマンド・Linter・テストランナー・静的解析ツール)実行の抽象契約
    (F00 Adapter Pattern)。

    各runnerはsubprocess等を直接呼び出さず、本Protocolの実装を通じてのみ外部コマンドを
    実行する。実際のsubprocess呼び出し実装(本番用アダプタ)はMVP対象外であり、テストでは
    本Protocolを満たすフェイク実装(`tests/tester/fakes.py`)を注入する。
    """

    def run(self, command: list[str], timeout_seconds: int) -> CommandExecutionResult: ...


class NotImplementedCommandExecutor:
    """`CommandExecutor`の既定実装。実際の外部ツール呼び出しは行わず、呼び出されると
    常に`NotImplementedError`を送出する(タスク指示: 実際のBuild/Lint/Testツール実行は
    行わずインターフェースとして定義するに留める)。
    """

    def run(self, command: list[str], timeout_seconds: int) -> CommandExecutionResult:
        raise NotImplementedError(
            "実際の外部ツール実行(subprocess呼び出し等)はMVP対象外です。"
            "CommandExecutorの実装(本番用アダプタまたはテスト用フェイク)を注入してください。"
        )
