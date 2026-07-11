"""types.py(IS21 3節)のデータクラス定義に対するテスト(IS21 7.1)。"""

import unittest
from datetime import UTC, datetime

from connector.types import (
    Attachment,
    ConnectionStatus,
    DeliveryResult,
    EventType,
    MessageContentType,
    NormalizedMessage,
    OutboundMessage,
    Platform,
)
from foundation.types import CommunicationMessage, Notification


class NormalizedMessageTest(unittest.TestCase):
    def test_normalized_message_holds_all_designed_fields(self) -> None:
        timestamp = datetime.now(UTC)
        attachment = Attachment(filename="a.png", content_type="image/png", url="https://example.com/a.png")

        message = NormalizedMessage(
            platform=Platform.SLACK,
            user_id="U1",
            channel_id="C1",
            message="hello",
            attachments=[attachment],
            timestamp=timestamp,
            event_type=EventType.MESSAGE,
        )

        self.assertEqual(message.platform, Platform.SLACK)
        self.assertEqual(message.user_id, "U1")
        self.assertEqual(message.channel_id, "C1")
        self.assertEqual(message.message, "hello")
        self.assertEqual(message.attachments, [attachment])
        self.assertEqual(message.timestamp, timestamp)

    def test_normalized_message_communication_message_defaults(self) -> None:
        message = NormalizedMessage(
            platform=Platform.DISCORD,
            user_id="U1",
            channel_id="C1",
            message="hello",
            attachments=[],
            timestamp=datetime.now(UTC),
            event_type=EventType.MESSAGE,
        )

        self.assertIsInstance(message.communication_message, CommunicationMessage)
        self.assertTrue(message.communication_message.id)
        self.assertIsNotNone(message.communication_message.created_at)
        self.assertIsNotNone(message.communication_message.updated_at)
        self.assertEqual(message.communication_message.metadata, {})


class OutboundMessageTest(unittest.TestCase):
    def test_outbound_message_defaults_notification_when_not_given(self) -> None:
        outbound = OutboundMessage(
            platform=Platform.SLACK,
            channel_id="C1",
            content_type=MessageContentType.TEXT,
            text="hi",
        )

        self.assertIsInstance(outbound.notification, Notification)
        self.assertEqual(outbound.attachments, [])


class DeliveryResultTest(unittest.TestCase):
    def test_delivery_result_defaults_delivered_at(self) -> None:
        result = DeliveryResult(platform=Platform.SLACK, channel_id="C1", delivered=True)

        self.assertIsNotNone(result.delivered_at)
        self.assertIsInstance(result.delivered_at, datetime)


class ConnectionStatusTest(unittest.TestCase):
    def test_connection_status_defaults_checked_at(self) -> None:
        status = ConnectionStatus(slack_connected=True, discord_connected=False)

        self.assertIsNotNone(status.checked_at)
        self.assertIsInstance(status.checked_at, datetime)
        self.assertEqual(status.detail, {})


class AttachmentTest(unittest.TestCase):
    def test_attachment_supports_url_or_data_independently(self) -> None:
        url_attachment = Attachment(filename="a.png", content_type="image/png", url="https://example.com/a.png")
        data_attachment = Attachment(filename="b.png", content_type="image/png", data=b"binary-data")

        self.assertIsNone(url_attachment.data)
        self.assertEqual(url_attachment.url, "https://example.com/a.png")
        self.assertIsNone(data_attachment.url)
        self.assertEqual(data_attachment.data, b"binary-data")


if __name__ == "__main__":
    unittest.main()
