"""Scheduler(M14) history_recorder.pyのテスト(IS14仕様書7節 test_history_recorder.py)。"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from scheduler.history_recorder import HistoryRecorder
from scheduler.models import ExecutionHistory, ExecutionResultStatus, TriggerType

_BASE_TIME = datetime(2026, 7, 11, 10, 0, 0, tzinfo=UTC)


def _make_history(
    workflow_id: str,
    history_id: str,
    started_at: datetime,
    execution_result: ExecutionResultStatus = ExecutionResultStatus.SUCCESS,
) -> ExecutionHistory:
    return ExecutionHistory(
        history_id=history_id,
        workflow_id=workflow_id,
        request_id=f"req-{history_id}",
        trigger_type=TriggerType.MANUAL,
        execution_result=execution_result,
        retry_count=0,
        started_at=started_at,
        finished_at=started_at + timedelta(seconds=5),
        duration_seconds=5.0,
    )


class TestHistoryRecorder(unittest.TestCase):
    def setUp(self) -> None:
        self.recorder = HistoryRecorder()

    def test_record_stores_execution_history_entry(self) -> None:
        history = _make_history("wf-1", "hist-1", _BASE_TIME)

        result = self.recorder.record(history)

        self.assertTrue(result.success)
        self.assertEqual(self.recorder.all_for("wf-1"), [history])

    def test_latest_returns_most_recent_history_for_workflow(self) -> None:
        first = _make_history("wf-1", "hist-1", _BASE_TIME)
        second = _make_history("wf-1", "hist-2", _BASE_TIME + timedelta(minutes=5))

        self.recorder.record(first)
        self.recorder.record(second)

        self.assertEqual(self.recorder.latest("wf-1"), second)

    def test_all_for_returns_entries_in_chronological_order(self) -> None:
        first = _make_history("wf-1", "hist-1", _BASE_TIME)
        second = _make_history("wf-1", "hist-2", _BASE_TIME + timedelta(minutes=5))
        third = _make_history("wf-1", "hist-3", _BASE_TIME + timedelta(minutes=10))

        self.recorder.record(first)
        self.recorder.record(second)
        self.recorder.record(third)

        self.assertEqual(self.recorder.all_for("wf-1"), [first, second, third])

    def test_latest_returns_none_when_no_history_exists(self) -> None:
        self.assertIsNone(self.recorder.latest("unknown-workflow"))


if __name__ == "__main__":
    unittest.main()
