import unittest
from datetime import UTC, datetime
from unittest import mock

from foundation.logger import get_logger
from foundation.result import Result
from foundation.types import TestResult
from tester.errors import TesterValidationError
from tester.models import CommandExecutionResult, QualityGateResult
from tester.quality_gate import determine_gate_status, evaluate_quality_gate
from tester.tester import Tester
from tests.tester.fakes import (
    FakeCommandExecutor,
    make_build_report,
    make_implementation,
    make_lint_report,
    make_passing_test_result,
    make_static_analysis_report,
    make_test_execution_report,
    make_tester_config,
)


def _make_gate_result(test_result: TestResult) -> QualityGateResult:
    items_result = evaluate_quality_gate(test_result)
    assert items_result.success
    items = items_result.value
    now = datetime.now(UTC)
    return QualityGateResult(
        id="gate-1",
        workflow_id="workflow-1",
        test_result=test_result,
        items=items,
        status=determine_gate_status(items),
        evaluated_at=now,
        created_at=now,
        updated_at=now,
    )


class TesterBaseModuleTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tester = Tester(config=make_tester_config(), logger=get_logger("test_tester"))

    def test_name_returns_tester(self) -> None:
        self.assertEqual(self.tester.name(), "tester")

    def test_health_check_returns_success_result(self) -> None:
        result = self.tester.health_check()
        self.assertTrue(result.success)
        self.assertTrue(result.value)


class ExecuteTestsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.config = make_tester_config(
            build_command=["build"],
            lint_command=["lint"],
            unit_test_command=["unit_test"],
            integration_test_command=["integration_test"],
            regression_test_command=["regression_test"],
            static_analysis_command=["static_analysis"],
        )
        self.implementation = make_implementation()

    def test_execute_tests_returns_success_result_when_all_stages_succeed(self) -> None:
        results_by_command = {
            ("build",): CommandExecutionResult(exit_code=0, stdout="", stderr="", duration_seconds=0.1),
            ("lint",): CommandExecutionResult(exit_code=0, stdout="", stderr="", duration_seconds=0.1),
            ("unit_test",): CommandExecutionResult(exit_code=0, stdout="test_a|pass|0.01|", stderr="", duration_seconds=0.1),
            ("integration_test",): CommandExecutionResult(
                exit_code=0, stdout="test_b|pass|0.02|", stderr="", duration_seconds=0.1
            ),
            ("regression_test",): CommandExecutionResult(
                exit_code=0, stdout="test_c|pass|0.03|", stderr="", duration_seconds=0.1
            ),
            ("static_analysis",): CommandExecutionResult(exit_code=0, stdout="", stderr="", duration_seconds=0.1),
        }
        executor = FakeCommandExecutor(results_by_command=results_by_command)
        tester = Tester(config=self.config, logger=get_logger("test_tester"), command_executor=executor)

        result = tester.execute_tests(self.implementation)

        self.assertTrue(result.success)
        test_result = result.value
        self.assertEqual(test_result.metadata["workflow_id"], "workflow-1")
        self.assertTrue(test_result.metadata["build_report"].is_success)
        self.assertFalse(test_result.metadata["lint_report"].has_error)
        self.assertTrue(test_result.metadata["unit_test_report"].is_pass)
        self.assertTrue(test_result.metadata["integration_test_report"].is_pass)
        self.assertTrue(test_result.metadata["regression_test_report"].is_pass)
        self.assertFalse(test_result.metadata["static_analysis_report"].has_critical)
        self.assertGreaterEqual(test_result.metadata["duration_seconds"], 0.0)
        self.assertEqual(len(executor.calls), 6)

    def test_execute_tests_returns_failure_result_when_implementation_is_none(self) -> None:
        tester = Tester(
            config=self.config,
            logger=get_logger("test_tester"),
            command_executor=FakeCommandExecutor(),
        )

        result = tester.execute_tests(None)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, TesterValidationError)

    def test_execute_tests_returns_failure_result_when_build_execution_raises_test_execution_error(
        self,
    ) -> None:
        executor = FakeCommandExecutor(raise_error=RuntimeError("build tool crashed"))
        tester = Tester(config=self.config, logger=get_logger("test_tester"), command_executor=executor)

        result = tester.execute_tests(self.implementation)

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)

    def test_execute_tests_stops_pipeline_on_build_tool_execution_error(self) -> None:
        executor = FakeCommandExecutor(raise_error=RuntimeError("build tool crashed"))
        tester = Tester(config=self.config, logger=get_logger("test_tester"), command_executor=executor)

        result = tester.execute_tests(self.implementation)

        self.assertFalse(result.success)
        # Buildの実行のみが試みられ、Lint以降は一切呼び出されない(パイプライン即停止)。
        self.assertEqual(len(executor.calls), 1)
        self.assertEqual(executor.calls[0][0], ["build"])

    def test_execute_tests_fetches_tester_config_once_per_call(self) -> None:
        config = make_tester_config()
        implementation = make_implementation()

        build_report = make_build_report(success=True)
        lint_report = make_lint_report()
        unit_report = make_test_execution_report(test_type="unit")
        integration_report = make_test_execution_report(test_type="integration")
        regression_report = make_test_execution_report(test_type="regression")
        static_report = make_static_analysis_report()

        with (
            mock.patch("tester.tester.run_build_check") as mock_build,
            mock.patch("tester.tester.run_lint_check") as mock_lint,
            mock.patch("tester.tester.run_unit_tests") as mock_unit,
            mock.patch("tester.tester.run_integration_tests") as mock_integration,
            mock.patch("tester.tester.run_regression_tests") as mock_regression,
            mock.patch("tester.tester.run_static_analysis") as mock_static,
        ):
            mock_build.return_value = Result(success=True, value=build_report)
            mock_lint.return_value = Result(success=True, value=lint_report)
            mock_unit.return_value = Result(success=True, value=unit_report)
            mock_integration.return_value = Result(success=True, value=integration_report)
            mock_regression.return_value = Result(success=True, value=regression_report)
            mock_static.return_value = Result(success=True, value=static_report)

            tester = Tester(config=config, logger=get_logger("test_tester"))
            result = tester.execute_tests(implementation)

            self.assertTrue(result.success)
            for mock_fn in (
                mock_build,
                mock_lint,
                mock_unit,
                mock_integration,
                mock_regression,
                mock_static,
            ):
                self.assertEqual(mock_fn.call_count, 1)
                passed_config = mock_fn.call_args[0][1]
                self.assertIs(passed_config, config)


class ValidateQualityTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tester = Tester(config=make_tester_config(), logger=get_logger("test_tester"))

    def test_validate_quality_returns_pass_result_when_all_items_pass(self) -> None:
        test_result = make_passing_test_result()

        result = self.tester.validate_quality(test_result)

        self.assertTrue(result.success)
        gate_result = result.value
        self.assertEqual(gate_result.status, "PASS")
        self.assertTrue(gate_result.is_pass)
        self.assertEqual(len(gate_result.items), 6)

    def test_validate_quality_returns_fail_result_when_any_item_fails(self) -> None:
        test_result = make_passing_test_result()
        test_result.metadata["lint_report"] = make_lint_report(error_count=1)

        result = self.tester.validate_quality(test_result)

        self.assertTrue(result.success)
        gate_result = result.value
        self.assertEqual(gate_result.status, "FAIL")
        self.assertFalse(gate_result.is_pass)

    def test_validate_quality_returns_failure_result_when_test_result_is_none(self) -> None:
        result = self.tester.validate_quality(None)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, TesterValidationError)


class PublishReportTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tester = Tester(config=make_tester_config(), logger=get_logger("test_tester"))

    def test_publish_report_returns_test_report_when_quality_gate_result_is_valid(self) -> None:
        test_result = make_passing_test_result()
        gate_result = _make_gate_result(test_result)

        result = self.tester.publish_report(gate_result)

        self.assertTrue(result.success)
        report = result.value
        self.assertEqual(report.workflow_id, "workflow-1")
        self.assertIs(report.quality_gate_result, gate_result)

    def test_publish_report_returns_failure_result_when_quality_gate_result_is_none(self) -> None:
        result = self.tester.publish_report(None)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, TesterValidationError)


if __name__ == "__main__":
    unittest.main()
