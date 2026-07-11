"""Monitoring(M16) health_checker.pyのテスト(IS16仕様書7節 test_health_checker.py)。"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from typing import Any

from foundation.errors import ConfigurationError
from foundation.interfaces import ConfigurationClient
from foundation.result import Result
from foundation.utils import utc_now
from monitoring.constants import (
    CONFIG_KEY_EXECUTION_TIME_THRESHOLD_MINUTES,
    CONFIG_KEY_FAILURE_RATE_THRESHOLD_PERCENT,
    CONFIG_KEY_HEARTBEAT_FRESHNESS_SECONDS,
    CONFIG_KEY_RETRY_COUNT_THRESHOLD,
    MonitoredModuleName,
)
from monitoring.errors import UnknownMonitoredModuleError
from monitoring.health_checker import HealthChecker
from monitoring.models import (
    Metrics,
    ModuleMetrics,
    ModuleStatus,
    SystemResourceStatus,
    WorkflowMetrics,
)

_NOW = datetime(2026, 7, 11, 10, 0, 0, tzinfo=UTC)


def make_fake_configuration_client(
    execution_time_threshold_minutes: float = 10.0,
    failure_rate_threshold_percent: float = 20.0,
    retry_count_threshold: float = 3.0,
    heartbeat_freshness_seconds: float = 300.0,
    fail: bool = False,
) -> ConfigurationClient:
    """呼び出しごとに独立した状態を持つ`ConfigurationClient`実装インスタンスを生成する。"""

    values = {
        CONFIG_KEY_EXECUTION_TIME_THRESHOLD_MINUTES: execution_time_threshold_minutes,
        CONFIG_KEY_FAILURE_RATE_THRESHOLD_PERCENT: failure_rate_threshold_percent,
        CONFIG_KEY_RETRY_COUNT_THRESHOLD: retry_count_threshold,
        CONFIG_KEY_HEARTBEAT_FRESHNESS_SECONDS: heartbeat_freshness_seconds,
    }

    class _FakeConfigurationClient(ConfigurationClient):
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def get(self, module_name: str, key: str) -> Result[Any]:
            self.calls.append((module_name, key))
            if fail:
                return Result(success=False, error=ConfigurationError("configuration unavailable"))
            return Result(success=True, value=values[key])

    return _FakeConfigurationClient()


def _make_module_status(last_heartbeat_at: datetime | None, is_responding: bool) -> ModuleStatus:
    return ModuleStatus(
        id="ms-1",
        created_at=_NOW,
        updated_at=_NOW,
        metadata={},
        module=MonitoredModuleName.EXECUTOR,
        last_heartbeat_at=last_heartbeat_at,
        is_responding=is_responding,
    )


def _make_module_metrics(
    module: MonitoredModuleName,
    execution_time_seconds: float = 60.0,
    success_rate: float = 100.0,
    failure_rate: float = 0.0,
    retry_count: int = 0,
    queue_length: int = 0,
) -> ModuleMetrics:
    return ModuleMetrics(
        module=module,
        execution_time_seconds=execution_time_seconds,
        success_rate=success_rate,
        failure_rate=failure_rate,
        retry_count=retry_count,
        queue_length=queue_length,
    )


def _make_metrics(module_metrics: list[ModuleMetrics], workflow_metrics: list[WorkflowMetrics] | None = None) -> Metrics:
    return Metrics(
        id="metrics-1",
        created_at=_NOW,
        updated_at=_NOW,
        metadata={},
        collected_at=_NOW,
        system_resources=SystemResourceStatus(
            cpu_percent=1.0, memory_percent=2.0, disk_percent=3.0, network_io_bytes_per_sec=4.0
        ),
        workflow_metrics=workflow_metrics if workflow_metrics is not None else [],
        module_metrics=module_metrics,
    )


class TestCheckModule(unittest.TestCase):
    def setUp(self) -> None:
        self.checker = HealthChecker(make_fake_configuration_client())

    def test_check_module_returns_healthy_when_alive_ready_healthy_all_true(self) -> None:
        # 鮮度判定はcheck_module内部で実際のutc_now()を基準に行われるため、
        # last_heartbeat_atは固定時刻ではなく実行時刻に近い値を用いる。
        module_status = _make_module_status(last_heartbeat_at=utc_now(), is_responding=True)
        result = self.checker.check_module(MonitoredModuleName.EXECUTOR, module_status)
        self.assertTrue(result.success)
        self.assertTrue(result.value.alive)
        self.assertTrue(result.value.ready)
        self.assertTrue(result.value.healthy)
        self.assertTrue(result.value.is_healthy)

    def test_check_module_returns_unhealthy_when_alive_is_false(self) -> None:
        module_status = _make_module_status(last_heartbeat_at=None, is_responding=True)
        result = self.checker.check_module(MonitoredModuleName.EXECUTOR, module_status)
        self.assertTrue(result.success)
        self.assertFalse(result.value.alive)
        self.assertFalse(result.value.is_healthy)

    def test_check_module_returns_unhealthy_when_ready_is_false(self) -> None:
        module_status = _make_module_status(last_heartbeat_at=_NOW, is_responding=False)
        result = self.checker.check_module(MonitoredModuleName.EXECUTOR, module_status)
        self.assertTrue(result.success)
        self.assertFalse(result.value.ready)
        self.assertFalse(result.value.is_healthy)

    def test_check_module_returns_unhealthy_when_healthy_is_false(self) -> None:
        # 鮮度判定はcheck_module内部で実際のutc_now()を基準に行われるため、
        # 実行時刻から十分離れた過去のheartbeatを用いて意図的に古い状態を作る。
        stale_heartbeat = utc_now() - timedelta(seconds=400)
        module_status = _make_module_status(last_heartbeat_at=stale_heartbeat, is_responding=True)
        result = self.checker.check_module(MonitoredModuleName.EXECUTOR, module_status)
        self.assertTrue(result.success)
        self.assertTrue(result.value.alive)
        self.assertTrue(result.value.ready)
        self.assertFalse(result.value.healthy)
        self.assertFalse(result.value.is_healthy)

    def test_check_module_returns_failure_result_for_unknown_module(self) -> None:
        module_status = _make_module_status(last_heartbeat_at=_NOW, is_responding=True)
        result = self.checker.check_module("NotAModule", module_status)  # type: ignore[arg-type]
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, UnknownMonitoredModuleError)


class TestAnalyze(unittest.TestCase):
    def test_analyze_flags_warning_when_execution_time_exceeds_threshold(self) -> None:
        checker = HealthChecker(make_fake_configuration_client(execution_time_threshold_minutes=10.0))
        metrics = _make_metrics(
            module_metrics=[_make_module_metrics(MonitoredModuleName.EXECUTOR, execution_time_seconds=700.0)]
        )
        result = checker.analyze(metrics)
        self.assertTrue(result.success)
        self.assertTrue(any("execution time" in warning for warning in result.value.warnings))
        self.assertFalse(result.value.overall_healthy)

    def test_analyze_flags_warning_when_failure_rate_exceeds_threshold(self) -> None:
        checker = HealthChecker(make_fake_configuration_client(failure_rate_threshold_percent=20.0))
        metrics = _make_metrics(module_metrics=[_make_module_metrics(MonitoredModuleName.TESTER, failure_rate=25.0)])
        result = checker.analyze(metrics)
        self.assertTrue(result.success)
        self.assertTrue(any("failure rate" in warning for warning in result.value.warnings))
        self.assertFalse(result.value.overall_healthy)

    def test_analyze_flags_warning_when_retry_count_exceeds_threshold(self) -> None:
        checker = HealthChecker(make_fake_configuration_client(retry_count_threshold=3.0))
        metrics = _make_metrics(module_metrics=[_make_module_metrics(MonitoredModuleName.REVIEWER, retry_count=5)])
        result = checker.analyze(metrics)
        self.assertTrue(result.success)
        self.assertTrue(any("retry count" in warning for warning in result.value.warnings))
        self.assertFalse(result.value.overall_healthy)

    def test_analyze_reads_thresholds_via_configuration_client(self) -> None:
        fake_client = make_fake_configuration_client()
        checker = HealthChecker(fake_client)
        metrics = _make_metrics(module_metrics=[_make_module_metrics(MonitoredModuleName.PLANNER)])
        checker.analyze(metrics)
        called_keys = {key for _module_name, key in fake_client.calls}
        self.assertIn(CONFIG_KEY_EXECUTION_TIME_THRESHOLD_MINUTES, called_keys)
        self.assertIn(CONFIG_KEY_FAILURE_RATE_THRESHOLD_PERCENT, called_keys)
        self.assertIn(CONFIG_KEY_RETRY_COUNT_THRESHOLD, called_keys)
        for module_name, _key in fake_client.calls:
            self.assertEqual(module_name, "Monitoring")

    def test_analyze_overall_healthy_false_when_any_module_unhealthy(self) -> None:
        checker = HealthChecker(make_fake_configuration_client())
        metrics = _make_metrics(
            module_metrics=[
                _make_module_metrics(MonitoredModuleName.PLANNER),
                _make_module_metrics(MonitoredModuleName.EXECUTOR, failure_rate=50.0),
            ]
        )
        result = checker.analyze(metrics)
        self.assertTrue(result.success)
        self.assertFalse(result.value.overall_healthy)

    def test_analyze_returns_failure_result_when_configuration_client_fails(self) -> None:
        checker = HealthChecker(make_fake_configuration_client(fail=True))
        metrics = _make_metrics(module_metrics=[])
        result = checker.analyze(metrics)
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, ConfigurationError)


if __name__ == "__main__":
    unittest.main()
