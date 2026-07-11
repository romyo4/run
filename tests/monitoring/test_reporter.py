"""Monitoring(M16) reporter.pyのテスト(IS16仕様書7節 test_reporter.py)。"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from foundation.errors import ValidationError
from monitoring.constants import MonitoredModuleName, WorkflowState
from monitoring.models import (
    HealthStatus,
    Metrics,
    ModuleHealth,
    ModuleMetrics,
    SystemResourceStatus,
    WorkflowMetrics,
)
from monitoring.reporter import ReportGenerator

_NOW = datetime(2026, 7, 11, 10, 0, 0, tzinfo=UTC)


def _make_health_status(
    overall_healthy: bool = True,
    warnings: list[str] | None = None,
    failures: list[str] | None = None,
) -> HealthStatus:
    return HealthStatus(
        id="hs-1",
        created_at=_NOW,
        updated_at=_NOW,
        metadata={},
        evaluated_at=_NOW,
        overall_healthy=overall_healthy,
        module_health=[ModuleHealth(module=MonitoredModuleName.EXECUTOR, alive=True, ready=True, healthy=overall_healthy)],
        warnings=warnings if warnings is not None else [],
        failures=failures if failures is not None else [],
    )


def _make_metrics(
    workflow_metrics: list[WorkflowMetrics] | None = None,
    module_metrics: list[ModuleMetrics] | None = None,
) -> Metrics:
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
        module_metrics=module_metrics if module_metrics is not None else [],
    )


class TestReportGeneratesMonitoringReport(unittest.TestCase):
    def test_report_generates_monitoring_report_from_health_status_and_metrics(self) -> None:
        health_status = _make_health_status()
        metrics = _make_metrics()
        result = ReportGenerator().generate(health_status, metrics)
        self.assertTrue(result.success)
        self.assertIs(result.value.health_status, health_status)
        self.assertIs(result.value.metrics, metrics)


class TestReportPerformanceSummary(unittest.TestCase):
    def test_report_includes_performance_summary_totals(self) -> None:
        workflow_metrics = [
            WorkflowMetrics(workflow_id="wf-1", state=WorkflowState.COMPLETED, execution_time_seconds=10.0),
            WorkflowMetrics(workflow_id="wf-2", state=WorkflowState.FAILED, execution_time_seconds=30.0),
        ]
        module_metrics = [
            ModuleMetrics(
                module=MonitoredModuleName.EXECUTOR,
                execution_time_seconds=20.0,
                success_rate=80.0,
                failure_rate=20.0,
                retry_count=1,
                queue_length=0,
            ),
            ModuleMetrics(
                module=MonitoredModuleName.TESTER,
                execution_time_seconds=20.0,
                success_rate=100.0,
                failure_rate=0.0,
                retry_count=0,
                queue_length=0,
            ),
        ]
        metrics = _make_metrics(workflow_metrics=workflow_metrics, module_metrics=module_metrics)
        result = ReportGenerator().generate(_make_health_status(), metrics)
        self.assertTrue(result.success)
        summary = result.value.performance_summary
        self.assertEqual(summary.total_workflows, 2)
        self.assertAlmostEqual(summary.average_execution_time_seconds, 20.0)
        self.assertAlmostEqual(summary.success_rate, 90.0)
        self.assertAlmostEqual(summary.failure_rate, 10.0)


class TestReportFailuresAndWarnings(unittest.TestCase):
    def test_report_includes_failures_and_warnings_from_health_status(self) -> None:
        health_status = _make_health_status(overall_healthy=False, warnings=["warn-1"], failures=["workflow wf-1 failed"])
        result = ReportGenerator().generate(health_status, _make_metrics())
        self.assertTrue(result.success)
        self.assertEqual(result.value.warnings, ["warn-1"])
        self.assertEqual(result.value.failures, ["workflow wf-1 failed"])


class TestReportHealthStatusNone(unittest.TestCase):
    def test_report_returns_failure_result_when_health_status_is_none(self) -> None:
        result = ReportGenerator().generate(None, _make_metrics())
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, ValidationError)


if __name__ == "__main__":
    unittest.main()
