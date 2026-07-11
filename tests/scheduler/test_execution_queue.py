"""Scheduler(M14) execution_queue.pyのテスト(IS14仕様書7節 test_execution_queue.py)。"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from scheduler.exceptions import DuplicateWorkflowExecutionError
from scheduler.execution_queue import ExecutionQueue
from scheduler.models import ExecutionRequest, TriggerType

_NOW = datetime(2026, 7, 11, 10, 0, 0, tzinfo=UTC)


def _make_request(workflow_id: str, request_id: str = "req-1") -> ExecutionRequest:
    return ExecutionRequest(
        request_id=request_id,
        workflow_id=workflow_id,
        trigger_type=TriggerType.MANUAL,
        source="cli",
        requested_at=_NOW,
    )


class TestExecutionQueue(unittest.TestCase):
    def setUp(self) -> None:
        self.queue = ExecutionQueue()

    def test_try_enqueue_succeeds_for_new_workflow(self) -> None:
        result = self.queue.try_enqueue(_make_request("wf-1"))
        self.assertTrue(result.success)
        self.assertTrue(result.value)
        self.assertTrue(self.queue.is_running("wf-1"))

    def test_try_enqueue_rejects_duplicate_running_workflow(self) -> None:
        first = self.queue.try_enqueue(_make_request("wf-1", "req-1"))
        self.assertTrue(first.success)

        second = self.queue.try_enqueue(_make_request("wf-1", "req-2"))
        self.assertFalse(second.success)
        self.assertIsInstance(second.error, DuplicateWorkflowExecutionError)

    def test_try_enqueue_allows_different_workflow_ids_concurrently(self) -> None:
        result_a = self.queue.try_enqueue(_make_request("wf-1"))
        result_b = self.queue.try_enqueue(_make_request("wf-2"))

        self.assertTrue(result_a.success)
        self.assertTrue(result_b.success)
        self.assertTrue(self.queue.is_running("wf-1"))
        self.assertTrue(self.queue.is_running("wf-2"))

    def test_mark_finished_allows_requeue_of_same_workflow(self) -> None:
        self.queue.try_enqueue(_make_request("wf-1", "req-1"))
        self.queue.mark_finished("wf-1")

        self.assertFalse(self.queue.is_running("wf-1"))

        result = self.queue.try_enqueue(_make_request("wf-1", "req-2"))
        self.assertTrue(result.success)

    def test_is_running_reflects_current_queue_state(self) -> None:
        self.assertFalse(self.queue.is_running("wf-1"))

        self.queue.mark_running("wf-1")
        self.assertTrue(self.queue.is_running("wf-1"))

        self.queue.mark_finished("wf-1")
        self.assertFalse(self.queue.is_running("wf-1"))


if __name__ == "__main__":
    unittest.main()
