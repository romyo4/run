"""TaskQueueManagerのunittest(IS02 7章のテストケース一覧に対応)。"""

import unittest
from datetime import UTC, datetime, timedelta
from typing import Any

from foundation.errors import ConfigurationError
from foundation.interfaces import ConfigurationClient
from foundation.result import Result
from foundation.types import Task
from task_queue.errors import (
    DeadlockDetectedError,
    InvalidQueueTransitionError,
    MaxRetryExceededError,
    QueueCorruptionError,
    TaskNotFoundError,
)
from task_queue.models import QueueStatus, TaskPriority
from task_queue.queue_manager import TaskQueueManager

_QUEUE = "default"


class FakeConfigurationClient(ConfigurationClient):
    """テスト用のConfigurationClient実装。値はコンストラクタで注入する。"""

    def __init__(self, values: dict[str, Any] | None = None) -> None:
        self._values = values or {}

    def get(self, module_name: str, key: str) -> Result[Any]:
        if key in self._values:
            return Result(success=True, value=self._values[key])
        return Result(success=False, error=ConfigurationError(f"unknown key: {key}"))


def _make_manager(**config_values: Any) -> TaskQueueManager:
    return TaskQueueManager(FakeConfigurationClient(config_values))


def _make_task(
    task_id: str,
    *,
    queue_name: str = _QUEUE,
    priority: TaskPriority | None = None,
    depends_on: list[str] | None = None,
    created_at: datetime | None = None,
) -> Task:
    metadata: dict[str, Any] = {"queue_name": queue_name}
    if priority is not None:
        metadata["priority"] = priority
    if depends_on is not None:
        metadata["depends_on"] = depends_on
    kwargs: dict[str, Any] = {"id": task_id, "metadata": metadata}
    if created_at is not None:
        kwargs["created_at"] = created_at
    return Task(**kwargs)


class TestTaskQueueManager(unittest.TestCase):
    # ------------------------------------------------------------------
    # 基本(BaseModule)
    # ------------------------------------------------------------------

    def test_name_returns_module_name(self) -> None:
        manager = _make_manager()
        self.assertEqual(manager.name(), "task_queue")

    def test_health_check_returns_success_when_queue_intact(self) -> None:
        manager = _make_manager()
        manager.enqueue(_make_task("T-1"))
        result = manager.health_check()
        self.assertTrue(result.success)
        self.assertTrue(result.value)

    # ------------------------------------------------------------------
    # FIFO確認
    # ------------------------------------------------------------------

    def test_enqueue_same_priority_dequeues_in_fifo_order(self) -> None:
        manager = _make_manager(max_parallel_executions=5)
        base_time = datetime(2026, 1, 1, tzinfo=UTC)
        manager.enqueue(_make_task("A", created_at=base_time))
        manager.enqueue(_make_task("B", created_at=base_time + timedelta(seconds=1)))

        first = manager.dequeue(_QUEUE)
        self.assertTrue(first.success)
        self.assertEqual(first.value.task_id, "A")

        second_peek = manager.peek(_QUEUE)
        self.assertTrue(second_peek.success)
        self.assertEqual(second_peek.value.task_id, "B")

    def test_peek_returns_same_task_without_changing_order(self) -> None:
        manager = _make_manager()
        manager.enqueue(_make_task("A"))

        first_peek = manager.peek(_QUEUE)
        second_peek = manager.peek(_QUEUE)

        self.assertTrue(first_peek.success)
        self.assertTrue(second_peek.success)
        self.assertEqual(first_peek.value.task_id, "A")
        self.assertEqual(second_peek.value.task_id, "A")

        listed = manager.list(_QUEUE)
        self.assertEqual(listed.value[0].status, QueueStatus.READY)

    # ------------------------------------------------------------------
    # 優先順位
    # ------------------------------------------------------------------

    def test_dequeue_returns_higher_priority_before_lower(self) -> None:
        manager = _make_manager(max_parallel_executions=5)
        manager.enqueue(_make_task("A", priority=TaskPriority.LOW))
        manager.enqueue(_make_task("B", priority=TaskPriority.HIGH))

        result = manager.dequeue(_QUEUE)
        self.assertTrue(result.success)
        self.assertEqual(result.value.task_id, "B")

    def test_reprioritize_changes_dequeue_order(self) -> None:
        manager = _make_manager(max_parallel_executions=5)
        base_time = datetime(2026, 1, 1, tzinfo=UTC)
        manager.enqueue(_make_task("A", created_at=base_time))
        manager.enqueue(_make_task("B", created_at=base_time + timedelta(seconds=1)))

        reprioritize_result = manager.reprioritize("B", TaskPriority.EMERGENCY)
        self.assertTrue(reprioritize_result.success)

        result = manager.dequeue(_QUEUE)
        self.assertTrue(result.success)
        self.assertEqual(result.value.task_id, "B")

    def test_reprioritize_rejects_running_task(self) -> None:
        manager = _make_manager(max_parallel_executions=5)
        manager.enqueue(_make_task("A"))
        manager.dequeue(_QUEUE)

        result = manager.reprioritize("A", TaskPriority.HIGH)
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, InvalidQueueTransitionError)

    def test_reprioritize_rejects_completed_task(self) -> None:
        manager = _make_manager()
        manager.enqueue(_make_task("A"))
        manager._tasks["A"].status = QueueStatus.COMPLETED

        result = manager.reprioritize("A", TaskPriority.HIGH)
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, InvalidQueueTransitionError)

    # ------------------------------------------------------------------
    # 並列実行制御
    # ------------------------------------------------------------------

    def test_dequeue_respects_max_parallel_executions_limit(self) -> None:
        manager = _make_manager(max_parallel_executions=1)
        manager.enqueue(_make_task("A"))
        manager.enqueue(_make_task("B"))

        first = manager.dequeue(_QUEUE)
        self.assertTrue(first.success)

        second = manager.dequeue(_QUEUE)
        self.assertFalse(second.success)

    def test_dequeue_returns_error_when_no_ready_task_available(self) -> None:
        manager = _make_manager(max_parallel_executions=10)
        manager.enqueue(_make_task("A"))
        manager.dequeue(_QUEUE)

        result = manager.dequeue(_QUEUE)
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, TaskNotFoundError)

    # ------------------------------------------------------------------
    # リトライ
    # ------------------------------------------------------------------

    def test_retry_increments_retry_count_and_returns_to_queued(self) -> None:
        manager = _make_manager(max_retry_count=3)
        manager.enqueue(_make_task("A"))
        manager._tasks["A"].status = QueueStatus.FAILED

        result = manager.retry("A")
        self.assertTrue(result.success)
        self.assertEqual(result.value.retry_count, 1)
        self.assertEqual(result.value.status, QueueStatus.QUEUED)

    def test_retry_exceeds_max_retry_count_transitions_to_failed(self) -> None:
        manager = _make_manager(max_retry_count=1)
        manager.enqueue(_make_task("A"))
        manager._tasks["A"].status = QueueStatus.FAILED

        result = manager.retry("A")
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, MaxRetryExceededError)
        self.assertEqual(manager._tasks["A"].status, QueueStatus.FAILED)
        self.assertEqual(manager._tasks["A"].retry_count, 1)

    def test_retry_rejects_task_not_in_failed_or_retrywaiting_state(self) -> None:
        manager = _make_manager()
        manager.enqueue(_make_task("A"))

        result = manager.retry("A")
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, InvalidQueueTransitionError)

    # ------------------------------------------------------------------
    # キャンセル
    # ------------------------------------------------------------------

    def test_cancel_queued_task_transitions_to_cancelled(self) -> None:
        manager = _make_manager()
        manager.enqueue(_make_task("A"))

        result = manager.cancel("A")
        self.assertTrue(result.success)
        self.assertTrue(result.value)
        self.assertEqual(manager._tasks["A"].status, QueueStatus.CANCELLED)

    def test_cancel_running_task_transitions_to_cancelled(self) -> None:
        manager = _make_manager()
        manager.enqueue(_make_task("A"))
        manager.dequeue(_QUEUE)

        result = manager.cancel("A")
        self.assertTrue(result.success)
        self.assertTrue(result.value)
        self.assertEqual(manager._tasks["A"].status, QueueStatus.CANCELLED)

    def test_cancel_already_completed_task_returns_false_without_error(self) -> None:
        manager = _make_manager()
        manager.enqueue(_make_task("A"))
        manager._tasks["A"].status = QueueStatus.COMPLETED

        result = manager.cancel("A")
        self.assertTrue(result.success)
        self.assertFalse(result.value)

    # ------------------------------------------------------------------
    # 依存関係
    # ------------------------------------------------------------------

    def test_enqueue_with_unresolved_dependency_sets_waiting_dependency(self) -> None:
        manager = _make_manager()
        result = manager.enqueue(_make_task("B", depends_on=["A"]))

        self.assertTrue(result.success)
        self.assertEqual(result.value.status, QueueStatus.WAITING_DEPENDENCY)

    def test_dependency_completion_transitions_dependent_task_to_ready(self) -> None:
        manager = _make_manager()
        manager.enqueue(_make_task("A"))
        manager.enqueue(_make_task("B", depends_on=["A"]))
        self.assertEqual(manager._tasks["B"].status, QueueStatus.WAITING_DEPENDENCY)

        manager._tasks["A"].status = QueueStatus.COMPLETED
        manager._resolve_dependencies("A")

        self.assertEqual(manager._tasks["B"].status, QueueStatus.READY)

    def test_enqueue_rejects_circular_dependency(self) -> None:
        manager = _make_manager()
        manager.enqueue(_make_task("B", depends_on=["A"]))

        result = manager.enqueue(_make_task("A", depends_on=["B"]))

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, DeadlockDetectedError)
        self.assertNotIn("A", manager._tasks)

    # ------------------------------------------------------------------
    # 障害復旧
    # ------------------------------------------------------------------

    def test_worker_failure_transitions_task_to_retry_waiting(self) -> None:
        manager = _make_manager(worker_timeout_seconds=1)
        manager.enqueue(_make_task("A"))
        manager.dequeue(_QUEUE)
        manager._tasks["A"].started_at = datetime.now(UTC) - timedelta(seconds=1000)

        manager._detect_stale_workers()

        self.assertEqual(manager._tasks["A"].status, QueueStatus.RETRY_WAITING)

    def test_stale_worker_detected_by_timeout_and_task_requeued(self) -> None:
        manager = _make_manager(worker_timeout_seconds=1, max_retry_count=3)
        manager.enqueue(_make_task("A"))
        manager.dequeue(_QUEUE)
        manager._tasks["A"].started_at = datetime.now(UTC) - timedelta(seconds=1000)

        stale_ids = manager._detect_stale_workers()
        self.assertIn("A", stale_ids)

        retry_result = manager.retry("A")
        self.assertTrue(retry_result.success)
        self.assertEqual(retry_result.value.status, QueueStatus.QUEUED)

    def test_queue_corruption_detected_returns_error_without_auto_repair(self) -> None:
        manager = _make_manager()
        manager.enqueue(_make_task("A"))
        manager._tasks["A"].worker_id = "ghost-worker"

        result = manager.dequeue(_QUEUE)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, QueueCorruptionError)
        self.assertEqual(manager._tasks["A"].status, QueueStatus.READY)
        self.assertEqual(manager._tasks["A"].worker_id, "ghost-worker")

    def test_task_timeout_transitions_to_retry_waiting(self) -> None:
        manager = _make_manager(worker_timeout_seconds=5)
        manager.enqueue(_make_task("A"))
        manager.dequeue(_QUEUE)
        # ちょうど閾値を超えたケース(実行タイムアウト)を再現する。
        manager._tasks["A"].started_at = datetime.now(UTC) - timedelta(seconds=10)

        stale_ids = manager._detect_stale_workers()

        self.assertIn("A", stale_ids)
        self.assertEqual(manager._tasks["A"].status, QueueStatus.RETRY_WAITING)


if __name__ == "__main__":
    unittest.main()
