"""Scheduler(M14) retry_manager.pyのテスト(IS14仕様書7節 test_retry_manager.py)。

同一Workflowの最大3回リトライ制約(設計書4.3)を検証する。
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from scheduler.exceptions import RetryLimitExceededError
from scheduler.models import FailedExecution
from scheduler.retry_manager import RetryManager

_NOW = datetime(2026, 7, 11, 10, 0, 0, tzinfo=UTC)


def _make_failed_execution(workflow_id: str, retry_count: int) -> FailedExecution:
    return FailedExecution(
        request_id="req-1",
        workflow_id=workflow_id,
        failure_reason="execution failed",
        retry_count=retry_count,
        failed_at=_NOW,
    )


class TestRetryManager(unittest.TestCase):
    def setUp(self) -> None:
        self.retry_manager = RetryManager()

    def test_first_retry_returns_retry_request_with_count_one(self) -> None:
        result = self.retry_manager.next_retry(_make_failed_execution("wf-1", retry_count=0))

        self.assertTrue(result.success)
        self.assertEqual(result.value.retry_count, 1)
        self.assertEqual(result.value.workflow_id, "wf-1")
        self.assertEqual(self.retry_manager.get_retry_count("wf-1"), 1)

    def test_retry_count_increments_up_to_max_of_three(self) -> None:
        # 同一Workflowで最大3回まで、リトライごとにretry_countが1ずつ増加する(4.3制約)。
        for expected_count in (1, 2, 3):
            failed_execution = _make_failed_execution("wf-1", retry_count=expected_count - 1)
            result = self.retry_manager.next_retry(failed_execution)
            self.assertTrue(result.success)
            self.assertEqual(result.value.retry_count, expected_count)

        self.assertEqual(self.retry_manager.get_retry_count("wf-1"), 3)

    def test_retry_beyond_max_count_returns_retry_limit_exceeded_error(self) -> None:
        # retry_count(入力)が既にMAX_RETRY_COUNT(3)に達している場合は超過として扱う。
        failed_execution = _make_failed_execution("wf-1", retry_count=RetryManager.MAX_RETRY_COUNT)

        result = self.retry_manager.next_retry(failed_execution)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, RetryLimitExceededError)
        self.assertIsNone(result.value)

    def test_reset_clears_retry_count_after_successful_execution(self) -> None:
        self.retry_manager.next_retry(_make_failed_execution("wf-1", retry_count=0))
        self.assertEqual(self.retry_manager.get_retry_count("wf-1"), 1)

        self.retry_manager.reset("wf-1")

        self.assertEqual(self.retry_manager.get_retry_count("wf-1"), 0)


if __name__ == "__main__":
    unittest.main()
