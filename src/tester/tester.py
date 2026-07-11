"""Testerクラス本体(IS10 4.1節)。BaseModule継承、公開インターフェース3関数の実装。

Tester(M10)は、Executorが生成した実装成果物(Implementation)に対してBuild確認・
Lint確認・Unit Test・Integration Test・Regression Test・Static Analysisを機械的に
実行し、その結果を基に品質ゲートを判定するモジュールである。コード修正・テストコード
修正・設計変更・Pull Request作成・GitHub操作・コードレビュー・マージ判定は一切行わない
(IS10 1節)。

Testerは遷移先の呼び出し(PR Creator起動やExecutorへの差し戻し実行)そのものは行わない。
`QualityGateResult.status`("PASS"/"FAIL")および`TestReport`を戻り値として返すことで、
呼び出し元のWorkflow制御(Command Router等)がPASS→PR Creator, FAIL→Executorのフローを
実現する(IS10 3.6節、4.1節)。
"""

from __future__ import annotations

import logging
import time

from foundation.base_module import BaseModule
from foundation.errors import FoundationError, ValidationError
from foundation.result import Result
from foundation.types import Implementation, TestResult
from foundation.utils import generate_id, utc_now
from foundation.validation import require_not_none
from tester import quality_gate, report_publisher
from tester.errors import TesterValidationError
from tester.logging_utils import build_log_message
from tester.models import CommandExecutor, QualityGateResult, TesterConfig, TestReport
from tester.runners import (
    run_build_check,
    run_integration_tests,
    run_lint_check,
    run_regression_tests,
    run_static_analysis,
    run_unit_tests,
)

__all__ = ["Tester"]

_MODULE_NAME = "tester"


class Tester(BaseModule):
    """AI Development PipelineのTest実行・品質ゲート判定モジュール(M10)。"""

    def __init__(
        self,
        config: TesterConfig,
        logger: logging.Logger,
        command_executor: CommandExecutor | None = None,
    ) -> None:
        """IS10 4.1節の公開インターフェース。

        `command_executor`はIS10本文の必須引数ではないが、外部ツール(Build/Lint/Test/
        Static Analysis)の実行方法をProtocolとして注入可能にするための拡張点である
        (未指定時は既定の`NotImplementedCommandExecutor`が使われ、実際のツール実行は
        MVP対象外として`TestExecutionError`を返す。テストではフェイク実装を注入する)。
        """
        self._config = config
        self._logger = logger
        self._command_executor = command_executor

    # --- BaseModule (F02) ---
    def name(self) -> str:
        return _MODULE_NAME

    def health_check(self) -> Result[bool]:
        return Result(success=True, value=True)

    # --- 公開インターフェース(IS10 3.4節) ---
    def execute_tests(self, implementation: Implementation) -> Result[TestResult]:
        """Build/Lint/Unit/Integration/Regression/Static Analysisを順次実行しTestResultを返す。

        いずれかがツール実行自体に失敗した場合(判定結果ではなく実行エラー)は即座に
        `Result[TestResult]`として失敗を返す(IS10 4.5節)。
        """
        started_at = time.monotonic()
        try:
            require_not_none(implementation, "implementation")
        except ValidationError as exc:
            error = TesterValidationError(str(exc))
            self._log_execute_tests(workflow_id="", duration_seconds=0.0, result="failure", error=error)
            return Result(success=False, error=error)

        # IS10 5節: execute_tests呼び出し開始時に一度だけTesterConfigを取得し、
        # 以降のrunner呼び出しへ同一インスタンスを渡す(実行中の判定基準変更を防ぐ)。
        config = self._config
        executor = self._command_executor
        workflow_id = str((implementation.metadata or {}).get("workflow_id", ""))

        build_result = run_build_check(implementation, config, executor)
        if not build_result.success:
            return self._fail_execute_tests(workflow_id, started_at, build_result.error)
        build_report = build_result.value

        lint_result = run_lint_check(implementation, config, executor)
        if not lint_result.success:
            return self._fail_execute_tests(workflow_id, started_at, lint_result.error)
        lint_report = lint_result.value

        unit_result = run_unit_tests(implementation, config, executor)
        if not unit_result.success:
            return self._fail_execute_tests(workflow_id, started_at, unit_result.error)
        unit_test_report = unit_result.value

        integration_result = run_integration_tests(implementation, config, executor)
        if not integration_result.success:
            return self._fail_execute_tests(workflow_id, started_at, integration_result.error)
        integration_test_report = integration_result.value

        regression_result = run_regression_tests(implementation, config, executor)
        if not regression_result.success:
            return self._fail_execute_tests(workflow_id, started_at, regression_result.error)
        regression_test_report = regression_result.value

        static_analysis_result = run_static_analysis(implementation, config, executor)
        if not static_analysis_result.success:
            return self._fail_execute_tests(workflow_id, started_at, static_analysis_result.error)
        static_analysis_report = static_analysis_result.value

        duration_seconds = time.monotonic() - started_at
        test_result = TestResult(
            metadata={
                "workflow_id": workflow_id,
                "build_report": build_report,
                "lint_report": lint_report,
                "unit_test_report": unit_test_report,
                "integration_test_report": integration_test_report,
                "regression_test_report": regression_test_report,
                "static_analysis_report": static_analysis_report,
                "duration_seconds": duration_seconds,
            }
        )
        self._log_execute_tests(
            workflow_id=workflow_id,
            duration_seconds=duration_seconds,
            result="success",
            build_report=build_report,
            lint_report=lint_report,
            unit_test_report=unit_test_report,
            integration_test_report=integration_test_report,
            regression_test_report=regression_test_report,
        )
        return Result(success=True, value=test_result)

    def validate_quality(self, test_result: TestResult) -> Result[QualityGateResult]:
        """TestResultの各項目を品質ゲート基準(IS10 3.5節)で判定しQualityGateResultを返す。"""
        try:
            require_not_none(test_result, "test_result")
        except ValidationError as exc:
            error = TesterValidationError(str(exc))
            self._log_validate_quality(workflow_id="", test_result=None, status="FAIL", result="failure")
            return Result(success=False, error=error)

        items_result = quality_gate.evaluate_quality_gate(test_result)
        if not items_result.success:
            self._log_validate_quality(
                workflow_id=str((test_result.metadata or {}).get("workflow_id", "")),
                test_result=test_result,
                status="FAIL",
                result="failure",
            )
            return Result(success=False, error=items_result.error)

        items = items_result.value
        status = quality_gate.determine_gate_status(items)
        workflow_id = str((test_result.metadata or {}).get("workflow_id", ""))
        now = utc_now()
        gate_result = QualityGateResult(
            id=generate_id(),
            workflow_id=workflow_id,
            test_result=test_result,
            items=items,
            status=status,
            evaluated_at=now,
            created_at=now,
            updated_at=now,
        )
        self._log_validate_quality(workflow_id=workflow_id, test_result=test_result, status=status, result="success")
        return Result(success=True, value=gate_result)

    def publish_report(self, quality_gate_result: QualityGateResult) -> Result[TestReport]:
        """QualityGateResultからTestReportを生成する。

        PASS時はPR Creatorへ、FAIL時はExecutorへの引き渡し判断は呼び出し元(Command
        Router / Workflow制御)が行い、Tester自身は遷移制御を持たない(IS10 4.1節)。
        """
        try:
            require_not_none(quality_gate_result, "quality_gate_result")
        except ValidationError as exc:
            return Result(success=False, error=TesterValidationError(str(exc)))
        return report_publisher.build_test_report(quality_gate_result)

    # --- 内部ヘルパー(ログ出力、IS10 6節) ---
    def _fail_execute_tests(self, workflow_id: str, started_at: float, error: FoundationError | None) -> Result[TestResult]:
        duration_seconds = time.monotonic() - started_at
        self._log_execute_tests(workflow_id=workflow_id, duration_seconds=duration_seconds, result="failure")
        return Result(success=False, error=error)

    def _log_execute_tests(
        self,
        *,
        workflow_id: str,
        duration_seconds: float,
        result: str,
        build_report: object | None = None,
        lint_report: object | None = None,
        unit_test_report: object | None = None,
        integration_test_report: object | None = None,
        regression_test_report: object | None = None,
        error: FoundationError | None = None,
    ) -> None:
        build_result = getattr(build_report, "status", None)
        build_result_str = getattr(build_result, "value", "unknown") if build_result else "unknown"
        lint_result_str = "unknown"
        if lint_report is not None:
            lint_result_str = "error" if getattr(lint_report, "has_error", False) else "no_error"
        test_reports = [unit_test_report, integration_test_report, regression_test_report]
        if any(report is None for report in test_reports):
            test_result_str = "unknown"
        else:
            test_result_str = "pass" if all(getattr(report, "is_pass", False) for report in test_reports) else "fail"
        message = build_log_message(
            workflow_id=workflow_id,
            build_result=build_result_str,
            lint_result=lint_result_str,
            test_result=test_result_str,
            quality_gate="N/A",
            duration_seconds=duration_seconds,
            result=result,
        )
        if result == "success":
            self._logger.info(message)
        else:
            self._logger.error(message)

    def _log_validate_quality(
        self,
        *,
        workflow_id: str,
        test_result: TestResult | None,
        status: str,
        result: str,
    ) -> None:
        metadata = (test_result.metadata or {}) if test_result is not None else {}
        build_report = metadata.get("build_report")
        lint_report = metadata.get("lint_report")
        build_result_str = "unknown"
        if build_report is not None:
            build_result_str = getattr(build_report, "status", None)
            build_result_str = getattr(build_result_str, "value", "unknown")
        lint_result_str = "unknown"
        if lint_report is not None:
            lint_result_str = "error" if getattr(lint_report, "has_error", False) else "no_error"
        test_reports = [
            metadata.get("unit_test_report"),
            metadata.get("integration_test_report"),
            metadata.get("regression_test_report"),
        ]
        if any(report is None for report in test_reports):
            test_result_str = "unknown"
        else:
            test_result_str = "pass" if all(getattr(report, "is_pass", False) for report in test_reports) else "fail"
        duration_seconds = float(metadata.get("duration_seconds", 0.0))
        message = build_log_message(
            workflow_id=workflow_id,
            build_result=build_result_str,
            lint_result=lint_result_str,
            test_result=test_result_str,
            quality_gate=status,
            duration_seconds=duration_seconds,
            result=result,
        )
        if result == "success":
            self._logger.info(message)
        else:
            self._logger.error(message)
