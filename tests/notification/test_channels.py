"""IS15 7. `tests/test_channels.py` に対応するテスト。"""

from __future__ import annotations

import unittest

from foundation.errors import ValidationError
from notification.channels import select_channel
from notification.errors import UnsupportedChannelError
from notification.types import Channel, EventType, NotificationEvent


def _build_event(channel_value: str) -> NotificationEvent:
    return NotificationEvent(
        workflow_id="wf-001",
        event_type=EventType.WORKFLOW_COMPLETED,
        event_result={},
        recipient="#dev-notifications",
        notification_template="workflow_completed",
        configuration={"channel": channel_value},
    )


class SelectChannelSlackTest(unittest.TestCase):
    def test_select_channel_slack(self) -> None:
        result = select_channel(_build_event("slack"))
        self.assertTrue(result.success)
        self.assertEqual(result.value, Channel.SLACK)


class SelectChannelDiscordTest(unittest.TestCase):
    def test_select_channel_discord(self) -> None:
        result = select_channel(_build_event("discord"))
        self.assertTrue(result.success)
        self.assertEqual(result.value, Channel.DISCORD)


class SelectChannelEmailTest(unittest.TestCase):
    def test_select_channel_email(self) -> None:
        result = select_channel(_build_event("email"))
        self.assertTrue(result.success)
        self.assertEqual(result.value, Channel.EMAIL)


class SelectChannelUnsupportedTest(unittest.TestCase):
    def test_select_channel_unsupported_returns_error(self) -> None:
        result = select_channel(_build_event("line"))
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, UnsupportedChannelError)
        # UnsupportedChannelErrorはValidationError派生(IS15 5章)であること
        self.assertIsInstance(result.error, ValidationError)


if __name__ == "__main__":
    unittest.main()
