"""DiscordAdapter(IS21 4.3)に対するテスト(IS21 7.3)。"""

import unittest

from connector.discord_adapter import DiscordAdapter
from connector.exceptions import DiscordApiError, EventParseError
from connector.http_client import HttpResponse
from connector.types import Attachment, EventType, MessageContentType, OutboundMessage, Platform
from tests.connector.fakes import FakeConfigurationClient, FakeHttpClient


def _make_adapter(
    http_client: FakeHttpClient | None = None,
    token: str = "discord-secret-token",
    bot_user_id: str = "BOT1",
) -> DiscordAdapter:
    config = FakeConfigurationClient({"discord_bot_token": token, "discord_bot_user_id": bot_user_id})
    return DiscordAdapter(config, http_client=http_client or FakeHttpClient())


class DiscordAdapterParseEventTest(unittest.TestCase):
    def test_parse_event_normalizes_discord_message_event(self) -> None:
        adapter = _make_adapter()
        raw_payload = {
            "type": "MESSAGE_CREATE",
            "channel_id": "C1",
            "author": {"id": "U1", "bot": False},
            "content": "hello there",
            "mentions": [],
            "attachments": [],
            "timestamp": "2024-01-01T00:00:00.000000+00:00",
        }

        result = adapter.parse_event(raw_payload)

        self.assertTrue(result.success)
        message = result.value
        self.assertEqual(message.platform, Platform.DISCORD)
        self.assertEqual(message.user_id, "U1")
        self.assertEqual(message.channel_id, "C1")
        self.assertEqual(message.message, "hello there")
        self.assertEqual(message.event_type, EventType.MESSAGE)

    def test_parse_event_normalizes_discord_mention_event(self) -> None:
        adapter = _make_adapter()
        raw_payload = {
            "type": "MESSAGE_CREATE",
            "channel_id": "C1",
            "author": {"id": "U1", "bot": False},
            "content": "<@BOT1> do something",
            "mentions": [{"id": "BOT1"}],
            "attachments": [],
            "timestamp": "2024-01-01T00:00:00.000000+00:00",
        }

        result = adapter.parse_event(raw_payload)

        self.assertTrue(result.success)
        self.assertEqual(result.value.event_type, EventType.MENTION)

    def test_parse_event_normalizes_discord_file_upload_event(self) -> None:
        adapter = _make_adapter()
        raw_payload = {
            "type": "MESSAGE_CREATE",
            "channel_id": "C1",
            "author": {"id": "U1", "bot": False},
            "content": "here is a file",
            "mentions": [],
            "attachments": [
                {
                    "filename": "report.pdf",
                    "content_type": "application/pdf",
                    "url": "https://cdn/f1",
                }
            ],
            "timestamp": "2024-01-01T00:00:00.000000+00:00",
        }

        result = adapter.parse_event(raw_payload)

        self.assertTrue(result.success)
        message = result.value
        self.assertEqual(message.event_type, EventType.FILE_UPLOAD)
        self.assertEqual(len(message.attachments), 1)
        attachment = message.attachments[0]
        self.assertEqual(attachment.filename, "report.pdf")
        self.assertEqual(attachment.content_type, "application/pdf")
        self.assertEqual(attachment.url, "https://cdn/f1")

    def test_parse_event_returns_event_parse_error_for_unrecognized_payload(self) -> None:
        adapter = _make_adapter()

        result = adapter.parse_event({"type": "PRESENCE_UPDATE"})

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, EventParseError)


class DiscordAdapterDeliverTest(unittest.TestCase):
    def test_deliver_sends_text_message(self) -> None:
        http_client = FakeHttpClient(responses=[HttpResponse(status_code=200, json_body={"id": "M1"})])
        adapter = _make_adapter(http_client)
        outbound = OutboundMessage(
            platform=Platform.DISCORD,
            channel_id="C1",
            content_type=MessageContentType.TEXT,
            text="hi",
        )

        result = adapter.deliver(outbound)

        self.assertTrue(result.success)
        self.assertTrue(result.value.delivered)
        self.assertEqual(result.value.message_id, "M1")
        self.assertEqual(http_client.calls[0]["json_body"]["content"], "hi")

    def test_deliver_sends_markdown_message(self) -> None:
        http_client = FakeHttpClient(responses=[HttpResponse(status_code=200, json_body={"id": "M2"})])
        adapter = _make_adapter(http_client)
        outbound = OutboundMessage(
            platform=Platform.DISCORD,
            channel_id="C1",
            content_type=MessageContentType.MARKDOWN,
            text="**hi**",
        )

        result = adapter.deliver(outbound)

        self.assertTrue(result.success)
        self.assertEqual(http_client.calls[0]["json_body"]["content"], "**hi**")

    def test_deliver_sends_file(self) -> None:
        http_client = FakeHttpClient(responses=[HttpResponse(status_code=200, json_body={"id": "M3"})])
        adapter = _make_adapter(http_client)
        outbound = OutboundMessage(
            platform=Platform.DISCORD,
            channel_id="C1",
            content_type=MessageContentType.FILE,
            attachments=[Attachment(filename="a.pdf", content_type="application/pdf", data=b"data")],
        )

        result = adapter.deliver(outbound)

        self.assertTrue(result.success)
        self.assertEqual(result.value.message_id, "M3")
        self.assertEqual(http_client.calls[0]["json_body"]["attachments"][0]["filename"], "a.pdf")

    def test_deliver_sends_image(self) -> None:
        http_client = FakeHttpClient(responses=[HttpResponse(status_code=200, json_body={"id": "M4"})])
        adapter = _make_adapter(http_client)
        outbound = OutboundMessage(
            platform=Platform.DISCORD,
            channel_id="C1",
            content_type=MessageContentType.IMAGE,
            attachments=[Attachment(filename="a.png", content_type="image/png", data=b"data")],
        )

        result = adapter.deliver(outbound)

        self.assertTrue(result.success)
        self.assertEqual(result.value.message_id, "M4")

    def test_deliver_returns_discord_api_error_on_api_failure(self) -> None:
        http_client = FakeHttpClient(
            responses=[HttpResponse(status_code=404, json_body={"code": 10003, "message": "Unknown Channel"})]
        )
        adapter = _make_adapter(http_client)
        outbound = OutboundMessage(
            platform=Platform.DISCORD,
            channel_id="C1",
            content_type=MessageContentType.TEXT,
            text="hi",
        )

        result = adapter.deliver(outbound)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, DiscordApiError)

    def test_deliver_does_not_leak_token_in_error_message(self) -> None:
        http_client = FakeHttpClient(exception=RuntimeError("failed with token discord-secret-token"))
        adapter = _make_adapter(http_client, token="discord-secret-token")
        outbound = OutboundMessage(
            platform=Platform.DISCORD,
            channel_id="C1",
            content_type=MessageContentType.TEXT,
            text="hi",
        )

        result = adapter.deliver(outbound)

        self.assertFalse(result.success)
        self.assertNotIn("discord-secret-token", result.error.message)


class DiscordAdapterCheckConnectionTest(unittest.TestCase):
    def test_check_connection_returns_true_when_api_reachable(self) -> None:
        http_client = FakeHttpClient(responses=[HttpResponse(status_code=200, json_body={"id": "BOT1"})])
        adapter = _make_adapter(http_client)

        result = adapter.check_connection()

        self.assertTrue(result.success)
        self.assertTrue(result.value)

    def test_check_connection_returns_false_when_api_unreachable(self) -> None:
        http_client = FakeHttpClient(exception=ConnectionError("network unreachable"))
        adapter = _make_adapter(http_client)

        result = adapter.check_connection()

        self.assertTrue(result.success)
        self.assertFalse(result.value)


if __name__ == "__main__":
    unittest.main()
