"""IS15 7. `tests/test_history.py` に対応するテスト。"""

from __future__ import annotations

import unittest

from notification.history import NotificationHistoryStore
from notification.types import Channel, DeliveryStatus, EventType, NotificationHistory


def _build_history() -> NotificationHistory:
    return NotificationHistory(
        workflow_id="wf-001",
        event_type=EventType.WORKFLOW_COMPLETED,
        channel=Channel.SLACK,
        delivery_status=DeliveryStatus.SUCCESS,
        retry_count=0,
        duration_ms=12.5,
    )


class AppendAndListAllTest(unittest.TestCase):
    def test_append_and_list_all(self) -> None:
        store = NotificationHistoryStore()
        history = _build_history()

        append_result = store.append(history)
        self.assertTrue(append_result.success)

        list_result = store.list_all()
        self.assertTrue(list_result.success)
        self.assertIsNotNone(list_result.value)
        assert list_result.value is not None
        self.assertIn(history, list_result.value)


class HistoryContainsLoggingFieldsTest(unittest.TestCase):
    def test_history_contains_logging_fields(self) -> None:
        history = _build_history()

        # IS15 4.5のログ項目(timestampはcreated_atに対応)をすべて保持すること
        self.assertEqual(history.workflow_id, "wf-001")
        self.assertEqual(history.event_type, EventType.WORKFLOW_COMPLETED)
        self.assertEqual(history.channel, Channel.SLACK)
        self.assertEqual(history.delivery_status, DeliveryStatus.SUCCESS)
        self.assertEqual(history.retry_count, 0)
        self.assertEqual(history.duration_ms, 12.5)
        self.assertTrue(hasattr(history, "created_at"))
        self.assertIsNotNone(history.created_at)


if __name__ == "__main__":
    unittest.main()
