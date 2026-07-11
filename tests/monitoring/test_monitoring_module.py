"""Monitoring(M16) monitoring_module.pyのテスト(IS16仕様書7節 test_monitoring_module.py)。"""

from __future__ import annotations

import copy
import unittest
from datetime import UTC, datetime
from typing import Any

from foundation.interfaces import ConfigurationClient
from foundation.result import Result
from foundation.utils import utc_now
from monitoring.collector import MetricsCollector
from monitoring.constants import (
    CONFIG_KEY_EXECUTION_TIME_THRESHOLD_MINUTES,
    CONFIG_KEY_FAILURE_RATE_THRESHOLD_PERCENT,
    CONFIG_KEY_HEARTBEAT_FRESHNESS_SECONDS,
    CONFIG_KEY_RETRY_COUNT_THRESHOLD,
    MonitoredModuleName,
    WorkflowState,
)
from monitoring.errors import UnknownMonitoredModuleError
from monitoring.health_checker import HealthChecker
from monitoring.models import (
    ExecutionLogEntry,
    ModuleStatus,
    SystemResourceStatus,
    SystemStatus,
    WorkflowStatus,
)
from monitoring.monitoring_module import MonitoringModule
from monitoring.reporter import ReportGenerator

_NOW = datetime(2026, 7, 11, 10, 0, 0, tzinfo=UTC)


def _make_fake_configuration_client(
    execution_time_threshold_minutes: float = 10.0,
    failure_rate_threshold_percent: float = 20.0,
    retry_count_threshold: float = 3.0,
    heartbeat_freshness_seconds: float = 300.0,
) -> ConfigurationClient:
    values = {
        CONFIG_KEY_EXECUTION_TIME_THRESHOLD_MINUTES: execution_time_threshold_minutes,
        CONFIG_KEY_FAILURE_RATE_THRESHOLD_PERCENT: failure_rate_threshold_percent,
        CONFIG_KEY_RETRY_COUNT_THRESHOLD: retry_count_threshold,
        CONFIG_KEY_HEARTBEAT_FRESHNESS_SECONDS: heartbeat_freshness_seconds,
    }

    class _FakeConfigurationClient(ConfigurationClient):
        def get(self, module_name: str, key: str) -> Result[Any]:
            return Result(success=True, value=values[key])

    return _FakeConfigurationClient()


def _make_monitoring_module(
    fake_configuration_client: ConfigurationClient | None = None,
) -> MonitoringModule:
    client = fake_configuration_client if fake_configuration_client is not None else _make_fake_configuration_client()
    return MonitoringModule(
        collector=MetricsCollector(),
        health_checker=HealthChecker(client),
        reporter=ReportGenerator(),
    )


def _make_system_status(
    *,
    secret_metadata: dict[str, Any] | None = None,
) -> SystemStatus:
    return SystemStatus(
        id="status-1",
        created_at=_NOW,
        updated_at=_NOW,
        metadata=secret_metadata if secret_metadata is not None else {},
        workflows=[
            WorkflowStatus(
                id="ws-1",
                created_at=_NOW,
                updated_at=_NOW,
                metadata={},
                workflow_id="wf-1",
                state=WorkflowState.COMPLETED,
            )
        ],
        modules=[
            ModuleStatus(
                # health_check()の鮮度判定は実際のutc_now()を基準に行われるため、
                # last_heartbeat_atは固定時刻ではなく実行時刻に近い値を用いる。
                id="ms-1",
                created_at=_NOW,
                updated_at=_NOW,
                metadata={},
                module=MonitoredModuleName.EXECUTOR,
                last_heartbeat_at=utc_now(),
                is_responding=True,
            )
        ],
        system_resources=SystemResourceStatus(
            cpu_percent=10.0, memory_percent=20.0, disk_percent=30.0, network_io_bytes_per_sec=100.0
        ),
        execution_log=[
            ExecutionLogEntry(
                timestamp=_NOW,
                workflow_id="wf-1",
                module=MonitoredModuleName.EXECUTOR,
                execution_time_seconds=5.0,
                is_failure=False,
            )
        ],
    )


class TestName(unittest.TestCase):
    def test_name_returns_monitoring(self) -> None:
        module = _make_monitoring_module()
        self.assertEqual(module.name(), "Monitoring")


class TestHealthCheckWithoutModule(unittest.TestCase):
    def test_health_check_without_module_returns_self_health_result(self) -> None:
        module = _make_monitoring_module()
        result = module.health_check()
        self.assertTrue(result.success)
        self.assertTrue(result.value)


class TestHealthCheckWithModule(unittest.TestCase):
    def test_health_check_with_module_returns_module_health_result(self) -> None:
        module = _make_monitoring_module()
        system_status = _make_system_status()
        collect_result = module.collect(system_status)
        self.assertTrue(collect_result.success)

        result = module.health_check(MonitoredModuleName.EXECUTOR)
        self.assertTrue(result.success)
        self.assertTrue(result.value)

    def test_health_check_with_module_returns_failure_when_not_yet_observed(self) -> None:
        module = _make_monitoring_module()
        result = module.health_check(MonitoredModuleName.TESTER)
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, UnknownMonitoredModuleError)


class TestCollectAnalyzeReportEndToEnd(unittest.TestCase):
    def test_collect_analyze_report_end_to_end_flow(self) -> None:
        module = _make_monitoring_module()
        system_status = _make_system_status()

        collect_result = module.collect(system_status)
        self.assertTrue(collect_result.success)
        metrics = collect_result.value

        analyze_result = module.analyze(metrics)
        self.assertTrue(analyze_result.success)
        health_status = analyze_result.value

        report_result = module.report(health_status, metrics)
        self.assertTrue(report_result.success)
        report = report_result.value
        self.assertIs(report.health_status, health_status)
        self.assertIs(report.metrics, metrics)


class TestReadOnlyConstraint(unittest.TestCase):
    def test_module_does_not_modify_system_state(self) -> None:
        module = _make_monitoring_module()
        system_status = _make_system_status()
        before = copy.deepcopy(system_status)

        module.collect(system_status)

        self.assertEqual(system_status, before)


class TestNoOutOfScopeApi(unittest.TestCase):
    def test_module_does_not_expose_notification_or_workflow_control_api(self) -> None:
        module = _make_monitoring_module()
        forbidden_attributes = [
            "notify",
            "send_notification",
            "schedule",
            "trigger",
            "retry",
            "execute",
            "create_pull_request",
            "review",
            "approve",
        ]
        for attribute in forbidden_attributes:
            self.assertFalse(
                hasattr(module, attribute),
                f"MonitoringModule must not expose out-of-scope API: {attribute}",
            )


class TestSecretFieldsNotLogged(unittest.TestCase):
    def test_secret_fields_are_not_present_in_log_output(self) -> None:
        module = _make_monitoring_module()
        secret_value = "SECRET_TOKEN_ABC123"
        system_status = _make_system_status(secret_metadata={"access_token": secret_value})

        with self.assertLogs("Monitoring", level="INFO") as captured:
            result = module.collect(system_status)

        self.assertTrue(result.success)
        for record in captured.output:
            self.assertNotIn(secret_value, record)


if __name__ == "__main__":
    unittest.main()
