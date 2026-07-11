"""Monitoring(M16) collector.pyのテスト(IS16仕様書7節 test_collector.py)。"""

from __future__ import annotations

import copy
import unittest
from datetime import UTC, datetime

from monitoring.collector import MetricsCollector
from monitoring.constants import MonitoredModuleName, WorkflowState
from monitoring.errors import InvalidSystemStatusError
from monitoring.models import (
    ExecutionLogEntry,
    ModuleStatus,
    SystemResourceStatus,
    SystemStatus,
    WorkflowStatus,
)

_NOW = datetime(2026, 7, 11, 10, 0, 0, tzinfo=UTC)


def _make_system_status(
    workflows: list[WorkflowStatus] | None = None,
    modules: list[ModuleStatus] | None = None,
    system_resources: SystemResourceStatus | None = None,
    execution_log: list[ExecutionLogEntry] | None = None,
) -> SystemStatus:
    return SystemStatus(
        id="status-1",
        created_at=_NOW,
        updated_at=_NOW,
        metadata={},
        workflows=workflows if workflows is not None else [],
        modules=modules if modules is not None else [],
        system_resources=(
            system_resources
            if system_resources is not None
            else SystemResourceStatus(
                cpu_percent=10.0,
                memory_percent=20.0,
                disk_percent=30.0,
                network_io_bytes_per_sec=100.0,
            )
        ),
        execution_log=execution_log if execution_log is not None else [],
    )


class TestCollectReturnsMetrics(unittest.TestCase):
    def test_collect_returns_success_result_with_metrics(self) -> None:
        system_status = _make_system_status(
            workflows=[
                WorkflowStatus(
                    id="ws-1",
                    created_at=_NOW,
                    updated_at=_NOW,
                    metadata={},
                    workflow_id="wf-1",
                    state=WorkflowState.RUNNING,
                )
            ],
            modules=[
                ModuleStatus(
                    id="ms-1",
                    created_at=_NOW,
                    updated_at=_NOW,
                    metadata={},
                    module=MonitoredModuleName.EXECUTOR,
                    last_heartbeat_at=_NOW,
                    is_responding=True,
                )
            ],
        )
        result = MetricsCollector().collect(system_status)
        self.assertTrue(result.success)
        self.assertIsNotNone(result.value)
        self.assertEqual(len(result.value.workflow_metrics), 1)
        self.assertEqual(len(result.value.module_metrics), 1)


class TestCollectSuccessAndFailureRate(unittest.TestCase):
    def test_collect_computes_success_rate_and_failure_rate_from_execution_log(self) -> None:
        execution_log = [
            ExecutionLogEntry(
                timestamp=_NOW,
                workflow_id="wf-1",
                module=MonitoredModuleName.TESTER,
                execution_time_seconds=1.0,
                is_failure=False,
            ),
            ExecutionLogEntry(
                timestamp=_NOW,
                workflow_id="wf-1",
                module=MonitoredModuleName.TESTER,
                execution_time_seconds=2.0,
                is_failure=False,
            ),
            ExecutionLogEntry(
                timestamp=_NOW,
                workflow_id="wf-1",
                module=MonitoredModuleName.TESTER,
                execution_time_seconds=3.0,
                is_failure=True,
            ),
        ]
        system_status = _make_system_status(
            modules=[
                ModuleStatus(
                    id="ms-1",
                    created_at=_NOW,
                    updated_at=_NOW,
                    metadata={},
                    module=MonitoredModuleName.TESTER,
                    last_heartbeat_at=_NOW,
                    is_responding=True,
                )
            ],
            execution_log=execution_log,
        )
        result = MetricsCollector().collect(system_status)
        self.assertTrue(result.success)
        module_metrics = result.value.module_metrics[0]
        self.assertAlmostEqual(module_metrics.failure_rate, 100.0 / 3.0)
        self.assertAlmostEqual(module_metrics.success_rate, 200.0 / 3.0)


class TestCollectExecutionTimePerWorkflow(unittest.TestCase):
    def test_collect_computes_execution_time_per_workflow(self) -> None:
        execution_log = [
            ExecutionLogEntry(
                timestamp=_NOW,
                workflow_id="wf-1",
                module=MonitoredModuleName.EXECUTOR,
                execution_time_seconds=5.0,
                is_failure=False,
            ),
            ExecutionLogEntry(
                timestamp=_NOW,
                workflow_id="wf-1",
                module=MonitoredModuleName.EXECUTOR,
                execution_time_seconds=7.0,
                is_failure=False,
            ),
            ExecutionLogEntry(
                timestamp=_NOW,
                workflow_id="wf-2",
                module=MonitoredModuleName.EXECUTOR,
                execution_time_seconds=100.0,
                is_failure=False,
            ),
        ]
        system_status = _make_system_status(
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
            execution_log=execution_log,
        )
        result = MetricsCollector().collect(system_status)
        self.assertTrue(result.success)
        workflow_metrics = result.value.workflow_metrics[0]
        self.assertEqual(workflow_metrics.workflow_id, "wf-1")
        self.assertEqual(workflow_metrics.execution_time_seconds, 12.0)


class TestCollectMissingRequiredField(unittest.TestCase):
    def test_collect_returns_failure_result_when_system_status_missing_required_field(self) -> None:
        result = MetricsCollector().collect(None)
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, InvalidSystemStatusError)

        system_status = _make_system_status()
        system_status.workflows = None  # type: ignore[assignment]
        result2 = MetricsCollector().collect(system_status)
        self.assertFalse(result2.success)
        self.assertIsInstance(result2.error, InvalidSystemStatusError)


class TestCollectDoesNotMutateInput(unittest.TestCase):
    def test_collect_does_not_mutate_input_system_status(self) -> None:
        system_status = _make_system_status(
            workflows=[
                WorkflowStatus(
                    id="ws-1",
                    created_at=_NOW,
                    updated_at=_NOW,
                    metadata={},
                    workflow_id="wf-1",
                    state=WorkflowState.RUNNING,
                )
            ],
            modules=[
                ModuleStatus(
                    id="ms-1",
                    created_at=_NOW,
                    updated_at=_NOW,
                    metadata={},
                    module=MonitoredModuleName.EXECUTOR,
                    last_heartbeat_at=_NOW,
                    is_responding=True,
                )
            ],
            execution_log=[
                ExecutionLogEntry(
                    timestamp=_NOW,
                    workflow_id="wf-1",
                    module=MonitoredModuleName.EXECUTOR,
                    execution_time_seconds=3.0,
                    is_failure=False,
                )
            ],
        )
        before = copy.deepcopy(system_status)
        MetricsCollector().collect(system_status)
        self.assertEqual(system_status, before)


if __name__ == "__main__":
    unittest.main()
