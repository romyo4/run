"""Monitoring(M16) models.pyのテスト(IS16仕様書7節 test_models.py)。"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from monitoring.constants import MonitoredModuleName, WorkflowState
from monitoring.models import (
    HealthStatus,
    Metrics,
    ModuleHealth,
    ModuleMetrics,
    MonitoringReport,
    PerformanceSummary,
    SystemResourceStatus,
    WorkflowMetrics,
    WorkflowStatus,
)

_NOW = datetime(2026, 7, 11, 10, 0, 0, tzinfo=UTC)


class TestWorkflowStatusCommonAttributes(unittest.TestCase):
    def test_workflow_status_holds_common_attributes(self) -> None:
        status = WorkflowStatus(
            id="ws-1",
            created_at=_NOW,
            updated_at=_NOW,
            metadata={"source": "scheduler"},
            workflow_id="wf-1",
            state=WorkflowState.RUNNING,
        )
        self.assertEqual(status.id, "ws-1")
        self.assertEqual(status.created_at, _NOW)
        self.assertEqual(status.updated_at, _NOW)
        self.assertEqual(status.metadata, {"source": "scheduler"})
        self.assertEqual(status.workflow_id, "wf-1")
        self.assertEqual(status.state, WorkflowState.RUNNING)


class TestMetricsAggregation(unittest.TestCase):
    def test_metrics_aggregates_workflow_and_module_metrics(self) -> None:
        workflow_metrics = [WorkflowMetrics(workflow_id="wf-1", state=WorkflowState.COMPLETED, execution_time_seconds=12.0)]
        module_metrics = [
            ModuleMetrics(
                module=MonitoredModuleName.EXECUTOR,
                execution_time_seconds=12.0,
                success_rate=100.0,
                failure_rate=0.0,
                retry_count=0,
                queue_length=0,
            )
        ]
        metrics = Metrics(
            id="metrics-1",
            created_at=_NOW,
            updated_at=_NOW,
            metadata={},
            collected_at=_NOW,
            system_resources=SystemResourceStatus(
                cpu_percent=10.0,
                memory_percent=20.0,
                disk_percent=30.0,
                network_io_bytes_per_sec=1000.0,
            ),
            workflow_metrics=workflow_metrics,
            module_metrics=module_metrics,
        )
        self.assertEqual(metrics.workflow_metrics, workflow_metrics)
        self.assertEqual(metrics.module_metrics, module_metrics)


class TestModuleHealthIsHealthy(unittest.TestCase):
    def test_module_health_is_healthy_true_when_all_checks_pass(self) -> None:
        health = ModuleHealth(module=MonitoredModuleName.TESTER, alive=True, ready=True, healthy=True)
        self.assertTrue(health.is_healthy)

    def test_module_health_is_healthy_false_when_any_check_fails(self) -> None:
        self.assertFalse(ModuleHealth(module=MonitoredModuleName.TESTER, alive=False, ready=True, healthy=True).is_healthy)
        self.assertFalse(ModuleHealth(module=MonitoredModuleName.TESTER, alive=True, ready=False, healthy=True).is_healthy)
        self.assertFalse(ModuleHealth(module=MonitoredModuleName.TESTER, alive=True, ready=True, healthy=False).is_healthy)


class TestMonitoringReportSections(unittest.TestCase):
    def test_monitoring_report_contains_all_required_sections(self) -> None:
        module_health = [ModuleHealth(module=MonitoredModuleName.EXECUTOR, alive=True, ready=True, healthy=True)]
        health_status = HealthStatus(
            id="hs-1",
            created_at=_NOW,
            updated_at=_NOW,
            metadata={},
            evaluated_at=_NOW,
            overall_healthy=True,
            module_health=module_health,
            warnings=["warn-1"],
            failures=["fail-1"],
        )
        metrics = Metrics(
            id="metrics-1",
            created_at=_NOW,
            updated_at=_NOW,
            metadata={},
            collected_at=_NOW,
            system_resources=SystemResourceStatus(
                cpu_percent=1.0, memory_percent=2.0, disk_percent=3.0, network_io_bytes_per_sec=4.0
            ),
            workflow_metrics=[],
            module_metrics=[],
        )
        performance_summary = PerformanceSummary(
            average_execution_time_seconds=0.0,
            success_rate=100.0,
            failure_rate=0.0,
            total_workflows=0,
        )
        report = MonitoringReport(
            id="report-1",
            created_at=_NOW,
            updated_at=_NOW,
            metadata={},
            health_status=health_status,
            metrics=metrics,
            failures=["fail-1"],
            warnings=["warn-1"],
            performance_summary=performance_summary,
        )
        # 3.4 Monitoring Report(Health Status/Metrics/Failures/Warnings/Performance Summary)
        self.assertIs(report.health_status, health_status)
        self.assertIs(report.metrics, metrics)
        self.assertEqual(report.failures, ["fail-1"])
        self.assertEqual(report.warnings, ["warn-1"])
        self.assertIs(report.performance_summary, performance_summary)


if __name__ == "__main__":
    unittest.main()
