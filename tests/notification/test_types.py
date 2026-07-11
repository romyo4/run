"""IS15 7. `tests/test_types.py` に対応するテスト。"""

from __future__ import annotations

import dataclasses
import unittest

from notification.types import (
    Channel,
    EventType,
    NotificationEvent,
    NotificationMessage,
)


def _build_event() -> NotificationEvent:
    return NotificationEvent(
        workflow_id="wf-001",
        event_type=EventType.WORKFLOW_COMPLETED,
        event_result={"workflow": "LP Improvement", "status": "Completed"},
        recipient="#dev-notifications",
        notification_template="workflow_completed",
        configuration={"channel": "slack"},
    )


class NotificationEventImmutableTest(unittest.TestCase):
    def test_notification_event_is_immutable(self) -> None:
        event = _build_event()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            event.workflow_id = "wf-002"  # type: ignore[misc]


class NotificationMessageDomainFieldsTest(unittest.TestCase):
    def test_notification_message_inherits_notification_domain_fields(self) -> None:
        message = NotificationMessage(
            workflow_id="wf-001",
            event_type=EventType.WORKFLOW_COMPLETED,
            channel=Channel.SLACK,
            recipient="#dev-notifications",
            subject="Workflow Completed",
            body="Workflow Completed\nWorkflow: LP Improvement",
            template_id="workflow_completed",
        )

        self.assertTrue(hasattr(message, "id"))
        self.assertTrue(hasattr(message, "created_at"))
        self.assertTrue(hasattr(message, "updated_at"))
        self.assertTrue(hasattr(message, "metadata"))
        self.assertIsInstance(message.id, str)
        self.assertNotEqual(message.id, "")
        self.assertIsInstance(message.metadata, dict)


if __name__ == "__main__":
    unittest.main()
