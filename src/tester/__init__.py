"""Tester (M10) 公開API(IS10 2節)。公開クラス・関数(Tester, execute_tests/validate_quality/
publish_report)および付随するdataclass・例外の再エクスポートのみを行う。
"""

from __future__ import annotations

from tester.errors import TesterConfigurationError, TesterValidationError, TestExecutionError
from tester.models import (
    BuildReport,
    BuildStatus,
    CommandExecutionResult,
    CommandExecutor,
    LintIssue,
    LintReport,
    NotImplementedCommandExecutor,
    QualityGateItemResult,
    QualityGateResult,
    StaticAnalysisIssue,
    StaticAnalysisReport,
    TestCaseResult,
    TesterConfig,
    TestExecutionReport,
    TestReport,
)
from tester.tester import Tester

__all__ = [
    "Tester",
    "BuildReport",
    "BuildStatus",
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
    "TesterValidationError",
    "TesterConfigurationError",
    "TestExecutionError",
]
