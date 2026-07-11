"""Scheduler(M14) scheduler_module.pyのテスト(IS14仕様書7節 test_scheduler_module.py)。

公開インターフェース schedule()/trigger()/retry()/status() の挙動、
同一Workflow重複起動禁止(4.4)・最大3回リトライ(4.3)を検証する。
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from typing import Any

from foundation.errors import ExternalServiceError
from foundation.interfaces import ConfigurationClient
from foundation.result import Result
from scheduler.command_router_client import RawCommand
from scheduler.exceptions import (
    DuplicateWorkflowExecutionError,
    InvalidScheduleDefinitionError,
    RetryLimitExceededError,
    UnknownWorkflowError,
)
from scheduler.history_recorder import HistoryRecorder
from scheduler.models import (
    Event,
    EventType,
    ExecutionResultStatus,
    FailedExecution,
    ScheduleDefinition,
    ScheduleFrequency,
    TriggerType,
    WorkflowRunState,
)
from scheduler.retry_manager import RetryManager
from scheduler.scheduler_module import SchedulerModule

_NOW = datetime(2026, 7, 11, 10, 0, 0, tzinfo=UTC)


class _FakeCommandRouter:
    """CommandRouterClient Protocolを満たすテスト用フェイク。receive()のみ提供する。

    実際のCommand Router(M05)のreceive()と同様、引数はRaw Command形状
    (属性アクセス可能な`RawCommand`)であることを前提とする。
    """

    def __init__(self, result: Result[Any] | None = None) -> None:
        self._result = result if result is not None else Result(success=True, value={"accepted": True})
        self.received_raw_commands: list[RawCommand] = []

    def receive(self, raw_command: RawCommand) -> Result[Any]:
        self.received_raw_commands.append(raw_command)
        return self._result


class _FakeConfigurationClient(ConfigurationClient):
    @staticmethod
    def get(module_name: str, key: str) -> Result[Any]:
        return Result(success=True, value=None, error=None)


def _make_manual_event(workflow_id: str = "wf-1") -> Event:
    return Event(
        workflow_id=workflow_id,
        trigger_type=TriggerType.MANUAL,
        source="slack",
        occurred_at=_NOW,
        payload={"instruction": "LP改善を実装して"},
    )


def _make_scheduled_event(workflow_id: str = "wf-1") -> Event:
    return Event(
        workflow_id=workflow_id,
        trigger_type=TriggerType.SCHEDULED,
        source="scheduler",
        occurred_at=_NOW,
    )


def _make_pr_merged_event(workflow_id: str = "wf-1") -> Event:
    return Event(
        workflow_id=workflow_id,
        trigger_type=TriggerType.EVENT,
        source="github_webhook",
        occurred_at=_NOW,
        event_type=EventType.PULL_REQUEST_MERGED,
    )


def _make_failed_execution(workflow_id: str, retry_count: int, request_id: str = "req-1") -> FailedExecution:
    return FailedExecution(
        request_id=request_id,
        workflow_id=workflow_id,
        failure_reason="execution failed",
        retry_count=retry_count,
        failed_at=_NOW,
    )


class _SchedulerModuleTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.fake_router = _FakeCommandRouter()
        self.history_recorder = HistoryRecorder()
        self.retry_manager = RetryManager()
        self.scheduler = SchedulerModule(
            command_router_client=self.fake_router,
            configuration_client=_FakeConfigurationClient(),
            history_recorder=self.history_recorder,
            retry_manager=self.retry_manager,
        )


class TestSchedulerModuleHealth(_SchedulerModuleTestCase):
    def test_health_check_returns_success_result(self) -> None:
        result = self.scheduler.health_check()
        self.assertTrue(result.success)
        self.assertTrue(result.value)


class TestSchedulerModuleSchedule(_SchedulerModuleTestCase):
    def test_schedule_registers_daily_schedule_definition(self) -> None:
        definition = ScheduleDefinition(
            workflow_id="wf-1",
            frequency=ScheduleFrequency.DAILY,
            time_of_day="09:00",
        )

        result = self.scheduler.schedule(definition)

        self.assertTrue(result.success)
        self.assertEqual(result.value.workflow_id, "wf-1")
        self.assertEqual(result.value.definition, definition)
        self.assertTrue(result.value.enabled)
        self.assertIsNotNone(result.value.schedule_id)

    def test_schedule_registers_cron_schedule_definition(self) -> None:
        definition = ScheduleDefinition(
            workflow_id="wf-1",
            frequency=ScheduleFrequency.CRON,
            cron_expression="0 20 * * SUN",
        )

        result = self.scheduler.schedule(definition)

        self.assertTrue(result.success)
        self.assertEqual(result.value.workflow_id, "wf-1")
        self.assertEqual(result.value.definition.cron_expression, "0 20 * * SUN")

    def test_schedule_rejects_cron_frequency_without_cron_expression(self) -> None:
        definition = ScheduleDefinition(
            workflow_id="wf-1",
            frequency=ScheduleFrequency.CRON,
            cron_expression=None,
        )

        result = self.scheduler.schedule(definition)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, InvalidScheduleDefinitionError)
        self.assertIsNone(result.value)


class TestSchedulerModuleTrigger(_SchedulerModuleTestCase):
    def test_trigger_manual_request_creates_execution_request(self) -> None:
        result = self.scheduler.trigger(_make_manual_event("wf-1"))

        self.assertTrue(result.success)
        self.assertEqual(result.value.workflow_id, "wf-1")
        self.assertEqual(result.value.trigger_type, TriggerType.MANUAL)
        self.assertEqual(result.value.source, "slack")
        self.assertEqual(result.value.retry_count, 0)

    def test_trigger_scheduled_time_creates_execution_request(self) -> None:
        result = self.scheduler.trigger(_make_scheduled_event("wf-1"))

        self.assertTrue(result.success)
        self.assertEqual(result.value.workflow_id, "wf-1")
        self.assertEqual(result.value.trigger_type, TriggerType.SCHEDULED)

    def test_trigger_event_creates_execution_request(self) -> None:
        result = self.scheduler.trigger(_make_pr_merged_event("wf-1"))

        self.assertTrue(result.success)
        self.assertEqual(result.value.workflow_id, "wf-1")
        self.assertEqual(result.value.trigger_type, TriggerType.EVENT)

    def test_trigger_rejects_duplicate_workflow_execution_when_already_running(self) -> None:
        first_result = self.scheduler.trigger(_make_manual_event("wf-1"))
        self.assertTrue(first_result.success)

        second_result = self.scheduler.trigger(_make_manual_event("wf-1"))

        self.assertFalse(second_result.success)
        self.assertIsInstance(second_result.error, DuplicateWorkflowExecutionError)
        self.assertIsNone(second_result.value)
        # 重複起動時は新規Execution RequestをCommand Routerへ引き渡さない(4.4制約)。
        self.assertEqual(len(self.fake_router.received_raw_commands), 1)

    def test_trigger_dispatches_execution_request_to_command_router(self) -> None:
        result = self.scheduler.trigger(_make_manual_event("wf-1"))

        self.assertTrue(result.success)
        self.assertEqual(len(self.fake_router.received_raw_commands), 1)
        raw_command = self.fake_router.received_raw_commands[0]
        self.assertEqual(raw_command.command, "wf-1")
        self.assertEqual(raw_command.command_id, result.value.request_id)
        self.assertEqual(raw_command.metadata["trigger_type"], "MANUAL")

    def test_trigger_records_execution_history_on_success(self) -> None:
        result = self.scheduler.trigger(_make_manual_event("wf-1"))
        self.assertTrue(result.success)

        history = self.history_recorder.latest("wf-1")
        self.assertIsNotNone(history)
        self.assertEqual(history.workflow_id, "wf-1")
        self.assertEqual(history.execution_result, ExecutionResultStatus.RUNNING)
        self.assertEqual(history.retry_count, 0)

    def test_trigger_records_execution_history_on_command_router_failure(self) -> None:
        failing_router = _FakeCommandRouter(Result(success=False, value=None, error=ExternalServiceError("router down")))
        scheduler = SchedulerModule(
            command_router_client=failing_router,
            configuration_client=_FakeConfigurationClient(),
            history_recorder=self.history_recorder,
            retry_manager=self.retry_manager,
        )

        result = scheduler.trigger(_make_manual_event("wf-1"))

        self.assertFalse(result.success)
        history = self.history_recorder.latest("wf-1")
        self.assertIsNotNone(history)
        self.assertEqual(history.execution_result, ExecutionResultStatus.FAILURE)
        # Command Router呼び出し失敗時はキューを解放し、再起動を妨げない。
        self.assertFalse(scheduler._execution_queue.is_running("wf-1"))


class TestSchedulerModuleRetry(_SchedulerModuleTestCase):
    def test_retry_creates_retry_request_within_max_count(self) -> None:
        failed_execution = _make_failed_execution("wf-1", retry_count=0)

        result = self.scheduler.retry(failed_execution)

        self.assertTrue(result.success)
        self.assertEqual(result.value.workflow_id, "wf-1")
        self.assertEqual(result.value.retry_count, 1)
        self.assertEqual(result.value.original_request_id, "req-1")

    def test_retry_returns_error_when_max_retry_count_exceeded(self) -> None:
        failed_execution = _make_failed_execution("wf-1", retry_count=RetryManager.MAX_RETRY_COUNT)

        result = self.scheduler.retry(failed_execution)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, RetryLimitExceededError)
        self.assertIsNone(result.value)

    def test_retry_records_failure_history_when_max_retry_count_exceeded(self) -> None:
        failed_execution = _make_failed_execution("wf-1", retry_count=RetryManager.MAX_RETRY_COUNT)

        result = self.scheduler.retry(failed_execution)
        self.assertFalse(result.success)

        history = self.history_recorder.latest("wf-1")
        self.assertIsNotNone(history)
        self.assertEqual(history.execution_result, ExecutionResultStatus.RETRY_LIMIT_EXCEEDED)
        self.assertEqual(history.retry_count, RetryManager.MAX_RETRY_COUNT)


class TestSchedulerModuleStatus(_SchedulerModuleTestCase):
    def test_status_returns_current_schedule_status_for_known_workflow(self) -> None:
        trigger_result = self.scheduler.trigger(_make_manual_event("wf-1"))
        self.assertTrue(trigger_result.success)

        result = self.scheduler.status("wf-1")

        self.assertTrue(result.success)
        self.assertEqual(result.value.workflow_id, "wf-1")
        self.assertTrue(result.value.is_running)
        self.assertEqual(result.value.state, WorkflowRunState.RUNNING)
        self.assertEqual(result.value.retry_count, 0)

    def test_status_returns_unknown_workflow_error_for_unregistered_workflow_id(self) -> None:
        result = self.scheduler.status("never-registered-workflow")

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, UnknownWorkflowError)
        self.assertIsNone(result.value)


if __name__ == "__main__":
    unittest.main()
