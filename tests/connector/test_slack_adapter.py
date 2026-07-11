"""SlackAdapter(IS21 4.2)に対するテスト(IS21 7.2)。"""

import unittest

from connector.exceptions import EventParseError, SlackApiError
from connector.http_client import HttpResponse
from connector.slack_adapter import SlackAdapter
from connector.types import Attachment, EventType, MessageContentType, OutboundMessage, Platform
from tests.connector.fakes import FakeConfigurationClient, FakeHttpClient


def _make_adapter(http_client: FakeHttpClient | None = None, token: str = "xoxb-secret-token") -> SlackAdapter:
    config = FakeConfigurationClient({"slack_bot_token": token})
    return SlackAdapter(config, http_client=http_client or FakeHttpClient())


class SlackAdapterParseEventTest(unittest.TestCase):
    def test_parse_event_normalizes_slack_message_event(self) -> None:
        adapter = _make_adapter()
        raw_payload = {
            "type": "event_callback",
            "event": {
                "type": "message",
                "channel": "C1",
                "user": "U1",
                "text": "hello there",
                "ts": "1700000000.000100",
            },
        }

        result = adapter.parse_event(raw_payload)

        self.assertTrue(result.success)
        message = result.value
        self.assertEqual(message.platform, Platform.SLACK)
        self.assertEqual(message.user_id, "U1")
        self.assertEqual(message.channel_id, "C1")
        self.assertEqual(message.message, "hello there")
        self.assertEqual(message.event_type, EventType.MESSAGE)
        self.assertEqual(message.attachments, [])

    def test_parse_event_normalizes_slack_mention_event(self) -> None:
        adapter = _make_adapter()
        raw_payload = {
            "type": "event_callback",
            "event": {
                "type": "app_mention",
                "channel": "C1",
                "user": "U1",
                "text": "<@BOT1> do something",
                "ts": "1700000000.000100",
            },
        }

        result = adapter.parse_event(raw_payload)

        self.assertTrue(result.success)
        self.assertEqual(result.value.event_type, EventType.MENTION)

    def test_parse_event_normalizes_slack_slash_command_event(self) -> None:
        adapter = _make_adapter()
        raw_payload = {
            "command": "/deploy",
            "channel_id": "C1",
            "user_id": "U1",
            "text": "staging",
        }

        result = adapter.parse_event(raw_payload)

        self.assertTrue(result.success)
        message = result.value
        self.assertEqual(message.event_type, EventType.SLASH_COMMAND)
        self.assertEqual(message.channel_id, "C1")
        self.assertEqual(message.user_id, "U1")
        self.assertIn("/deploy", message.message)
        self.assertIn("staging", message.message)

    def test_parse_event_normalizes_slack_file_upload_event(self) -> None:
        adapter = _make_adapter()
        raw_payload = {
            "type": "event_callback",
            "event": {
                "type": "message",
                "channel": "C1",
                "user": "U1",
                "text": "here is a file",
                "ts": "1700000000.000100",
                "files": [
                    {
                        "name": "report.pdf",
                        "mimetype": "application/pdf",
                        "url_private": "https://slack/f1",
                    }
                ],
            },
        }

        result = adapter.parse_event(raw_payload)

        self.assertTrue(result.success)
        message = result.value
        self.assertEqual(message.event_type, EventType.FILE_UPLOAD)
        self.assertEqual(len(message.attachments), 1)
        attachment = message.attachments[0]
        self.assertEqual(attachment.filename, "report.pdf")
        self.assertEqual(attachment.content_type, "application/pdf")
        self.assertEqual(attachment.url, "https://slack/f1")

    def test_parse_event_returns_event_parse_error_for_unrecognized_payload(self) -> None:
        adapter = _make_adapter()

        result = adapter.parse_event({"type": "event_callback", "event": {"type": "reaction_added"}})

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, EventParseError)


class SlackAdapterDeliverTest(unittest.TestCase):
    def test_deliver_sends_text_message(self) -> None:
        http_client = FakeHttpClient(responses=[HttpResponse(status_code=200, json_body={"ok": True, "ts": "111.222"})])
        adapter = _make_adapter(http_client)
        outbound = OutboundMessage(
            platform=Platform.SLACK,
            channel_id="C1",
            content_type=MessageContentType.TEXT,
            text="hi",
        )

        result = adapter.deliver(outbound)

        self.assertTrue(result.success)
        self.assertTrue(result.value.delivered)
        self.assertEqual(result.value.message_id, "111.222")
        self.assertEqual(http_client.calls[0]["json_body"]["text"], "hi")

    def test_deliver_sends_markdown_message(self) -> None:
        http_client = FakeHttpClient(responses=[HttpResponse(status_code=200, json_body={"ok": True, "ts": "111.223"})])
        adapter = _make_adapter(http_client)
        outbound = OutboundMessage(
            platform=Platform.SLACK,
            channel_id="C1",
            content_type=MessageContentType.MARKDOWN,
            text="*hi*",
        )

        result = adapter.deliver(outbound)

        self.assertTrue(result.success)
        self.assertTrue(http_client.calls[0]["json_body"]["mrkdwn"])

    def test_deliver_sends_file(self) -> None:
        http_client = FakeHttpClient(responses=[HttpResponse(status_code=200, json_body={"ok": True, "file": {"id": "F1"}})])
        adapter = _make_adapter(http_client)
        outbound = OutboundMessage(
            platform=Platform.SLACK,
            channel_id="C1",
            content_type=MessageContentType.FILE,
            attachments=[Attachment(filename="a.pdf", content_type="application/pdf", data=b"data")],
        )

        result = adapter.deliver(outbound)

        self.assertTrue(result.success)
        self.assertEqual(result.value.message_id, "F1")

    def test_deliver_sends_image(self) -> None:
        http_client = FakeHttpClient(responses=[HttpResponse(status_code=200, json_body={"ok": True, "file": {"id": "F2"}})])
        adapter = _make_adapter(http_client)
        outbound = OutboundMessage(
            platform=Platform.SLACK,
            channel_id="C1",
            content_type=MessageContentType.IMAGE,
            attachments=[Attachment(filename="a.png", content_type="image/png", data=b"data")],
        )

        result = adapter.deliver(outbound)

        self.assertTrue(result.success)
        self.assertEqual(result.value.message_id, "F2")

    def test_deliver_returns_slack_api_error_on_api_failure(self) -> None:
        http_client = FakeHttpClient(
            responses=[HttpResponse(status_code=200, json_body={"ok": False, "error": "channel_not_found"})]
        )
        adapter = _make_adapter(http_client)
        outbound = OutboundMessage(
            platform=Platform.SLACK,
            channel_id="C1",
            content_type=MessageContentType.TEXT,
            text="hi",
        )

        result = adapter.deliver(outbound)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, SlackApiError)

    def test_deliver_does_not_leak_token_in_error_message(self) -> None:
        http_client = FakeHttpClient(exception=RuntimeError("failed with token xoxb-secret-token"))
        adapter = _make_adapter(http_client, token="xoxb-secret-token")
        outbound = OutboundMessage(
            platform=Platform.SLACK,
            channel_id="C1",
            content_type=MessageContentType.TEXT,
            text="hi",
        )

        result = adapter.deliver(outbound)

        self.assertFalse(result.success)
        self.assertNotIn("xoxb-secret-token", result.error.message)


class SlackAdapterCheckConnectionTest(unittest.TestCase):
    def test_check_connection_returns_true_when_api_reachable(self) -> None:
        http_client = FakeHttpClient(responses=[HttpResponse(status_code=200, json_body={"ok": True})])
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
