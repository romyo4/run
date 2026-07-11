"""SlackDiscordConnector(IS21 4.4)に対するテスト(IS21 7.4, 7.6)。"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from connector.connector import MODULE_NAME, SlackDiscordConnector
from connector.exceptions import UnsupportedPlatformError
from connector.types import (
    Attachment,
    ConnectionStatus,
    DeliveryResult,
    EventType,
    MessageContentType,
    NormalizedMessage,
    OutboundMessage,
    Platform,
    PlatformEvent,
)
from foundation.errors import ExternalServiceError
from foundation.result import Result
from tests.connector.fakes import FakeConfigurationClient, FakeMessageAdapter


def _make_normalized_message(**overrides: object) -> NormalizedMessage:
    defaults: dict[str, object] = dict(
        platform=Platform.SLACK,
        user_id="U1",
        channel_id="C1",
        message="secret message body",
        attachments=[],
        timestamp=datetime.now(UTC),
        event_type=EventType.MESSAGE,
    )
    defaults.update(overrides)
    return NormalizedMessage(**defaults)  # type: ignore[arg-type]


def _make_connector(
    slack_adapter: FakeMessageAdapter | None = None,
    discord_adapter: FakeMessageAdapter | None = None,
) -> SlackDiscordConnector:
    config = FakeConfigurationClient()
    return SlackDiscordConnector(
        config,
        slack_adapter=slack_adapter or FakeMessageAdapter(Platform.SLACK),
        discord_adapter=discord_adapter or FakeMessageAdapter(Platform.DISCORD),
    )


class ConnectorReceiveTest(unittest.TestCase):
    def test_receive_delegates_to_slack_adapter_for_slack_platform(self) -> None:
        normalized = _make_normalized_message(platform=Platform.SLACK)
        slack_adapter = FakeMessageAdapter(Platform.SLACK, parse_result=Result(success=True, value=normalized))
        discord_adapter = FakeMessageAdapter(Platform.DISCORD)
        connector = _make_connector(slack_adapter, discord_adapter)
        event = PlatformEvent(platform=Platform.SLACK, raw_payload={"foo": "bar"})

        result = connector.receive(event)

        self.assertTrue(result.success)
        self.assertEqual(slack_adapter.parse_calls, [{"foo": "bar"}])
        self.assertEqual(discord_adapter.parse_calls, [])

    def test_receive_delegates_to_discord_adapter_for_discord_platform(self) -> None:
        normalized = _make_normalized_message(platform=Platform.DISCORD)
        discord_adapter = FakeMessageAdapter(Platform.DISCORD, parse_result=Result(success=True, value=normalized))
        slack_adapter = FakeMessageAdapter(Platform.SLACK)
        connector = _make_connector(slack_adapter, discord_adapter)
        event = PlatformEvent(platform=Platform.DISCORD, raw_payload={"foo": "bar"})

        result = connector.receive(event)

        self.assertTrue(result.success)
        self.assertEqual(discord_adapter.parse_calls, [{"foo": "bar"}])
        self.assertEqual(slack_adapter.parse_calls, [])

    def test_receive_returns_unsupported_platform_error_for_unknown_platform(self) -> None:
        connector = _make_connector()
        event = PlatformEvent(platform="teams", raw_payload={})  # type: ignore[arg-type]

        result = connector.receive(event)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, UnsupportedPlatformError)

    def test_receive_does_not_modify_normalized_message_content(self) -> None:
        normalized = _make_normalized_message(message="untouched content")
        slack_adapter = FakeMessageAdapter(Platform.SLACK, parse_result=Result(success=True, value=normalized))
        connector = _make_connector(slack_adapter=slack_adapter)
        event = PlatformEvent(platform=Platform.SLACK, raw_payload={})

        result = connector.receive(event)

        self.assertIs(result.value, normalized)
        self.assertEqual(result.value.message, "untouched content")

    def test_receive_wraps_adapter_exception_into_failure_result(self) -> None:
        slack_adapter = FakeMessageAdapter(Platform.SLACK, raise_on_parse=RuntimeError("boom"))
        connector = _make_connector(slack_adapter=slack_adapter)
        event = PlatformEvent(platform=Platform.SLACK, raw_payload={})

        result = connector.receive(event)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, ExternalServiceError)


class ConnectorSendTest(unittest.TestCase):
    def test_send_delegates_to_slack_adapter_for_slack_platform(self) -> None:
        delivery = DeliveryResult(platform=Platform.SLACK, channel_id="C1", delivered=True)
        slack_adapter = FakeMessageAdapter(Platform.SLACK, deliver_result=Result(success=True, value=delivery))
        discord_adapter = FakeMessageAdapter(Platform.DISCORD)
        connector = _make_connector(slack_adapter, discord_adapter)
        outbound = OutboundMessage(
            platform=Platform.SLACK,
            channel_id="C1",
            content_type=MessageContentType.TEXT,
            text="hi",
        )

        result = connector.send(outbound)

        self.assertTrue(result.success)
        self.assertEqual(slack_adapter.deliver_calls, [outbound])
        self.assertEqual(discord_adapter.deliver_calls, [])

    def test_send_delegates_to_discord_adapter_for_discord_platform(self) -> None:
        delivery = DeliveryResult(platform=Platform.DISCORD, channel_id="C1", delivered=True)
        discord_adapter = FakeMessageAdapter(Platform.DISCORD, deliver_result=Result(success=True, value=delivery))
        slack_adapter = FakeMessageAdapter(Platform.SLACK)
        connector = _make_connector(slack_adapter, discord_adapter)
        outbound = OutboundMessage(
            platform=Platform.DISCORD,
            channel_id="C1",
            content_type=MessageContentType.TEXT,
            text="hi",
        )

        result = connector.send(outbound)

        self.assertTrue(result.success)
        self.assertEqual(discord_adapter.deliver_calls, [outbound])
        self.assertEqual(slack_adapter.deliver_calls, [])

    def test_send_returns_unsupported_platform_error_for_unknown_platform(self) -> None:
        connector = _make_connector()
        outbound = OutboundMessage(
            platform="teams", channel_id="C1", content_type=MessageContentType.TEXT, text="hi"  # type: ignore[arg-type]
        )

        result = connector.send(outbound)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, UnsupportedPlatformError)

    def test_send_forwards_outbound_message_without_generating_content(self) -> None:
        delivery = DeliveryResult(platform=Platform.SLACK, channel_id="C1", delivered=True)
        slack_adapter = FakeMessageAdapter(Platform.SLACK, deliver_result=Result(success=True, value=delivery))
        connector = _make_connector(slack_adapter=slack_adapter)
        outbound = OutboundMessage(
            platform=Platform.SLACK,
            channel_id="C1",
            content_type=MessageContentType.TEXT,
            text="original text",
        )

        connector.send(outbound)

        self.assertIs(slack_adapter.deliver_calls[0], outbound)
        self.assertEqual(slack_adapter.deliver_calls[0].text, "original text")

    def test_send_wraps_adapter_exception_into_failure_result(self) -> None:
        slack_adapter = FakeMessageAdapter(Platform.SLACK, raise_on_deliver=RuntimeError("boom"))
        connector = _make_connector(slack_adapter=slack_adapter)
        outbound = OutboundMessage(
            platform=Platform.SLACK,
            channel_id="C1",
            content_type=MessageContentType.TEXT,
            text="hi",
        )

        result = connector.send(outbound)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, ExternalServiceError)


class ConnectorHealthTest(unittest.TestCase):
    def test_health_aggregates_slack_and_discord_connection_status(self) -> None:
        slack_adapter = FakeMessageAdapter(Platform.SLACK, connection_result=Result(success=True, value=True))
        discord_adapter = FakeMessageAdapter(Platform.DISCORD, connection_result=Result(success=True, value=False))
        connector = _make_connector(slack_adapter, discord_adapter)

        result = connector.health()

        self.assertTrue(result.success)
        status = result.value
        self.assertIsInstance(status, ConnectionStatus)
        self.assertTrue(status.slack_connected)
        self.assertFalse(status.discord_connected)

    def test_health_continues_when_one_platform_check_raises(self) -> None:
        slack_adapter = FakeMessageAdapter(Platform.SLACK, raise_on_check=RuntimeError("network down"))
        discord_adapter = FakeMessageAdapter(Platform.DISCORD, connection_result=Result(success=True, value=True))
        connector = _make_connector(slack_adapter, discord_adapter)

        result = connector.health()

        self.assertTrue(result.success)
        status = result.value
        self.assertFalse(status.slack_connected)
        self.assertTrue(status.discord_connected)

    def test_health_check_returns_true_when_at_least_one_platform_connected(self) -> None:
        slack_adapter = FakeMessageAdapter(Platform.SLACK, connection_result=Result(success=True, value=False))
        discord_adapter = FakeMessageAdapter(Platform.DISCORD, connection_result=Result(success=True, value=True))
        connector = _make_connector(slack_adapter, discord_adapter)

        result = connector.health_check()

        self.assertTrue(result.success)
        self.assertTrue(result.value)

    def test_health_check_returns_false_when_both_platforms_disconnected(self) -> None:
        slack_adapter = FakeMessageAdapter(Platform.SLACK, connection_result=Result(success=True, value=False))
        discord_adapter = FakeMessageAdapter(Platform.DISCORD, connection_result=Result(success=True, value=False))
        connector = _make_connector(slack_adapter, discord_adapter)

        result = connector.health_check()

        self.assertTrue(result.success)
        self.assertFalse(result.value)


class ConnectorNameTest(unittest.TestCase):
    def test_name_returns_fixed_module_name(self) -> None:
        connector = _make_connector()

        self.assertEqual(connector.name(), MODULE_NAME)
        self.assertEqual(connector.name(), "slack_discord_connector")


class ConnectorLoggingTest(unittest.TestCase):
    def test_receive_log_output_does_not_contain_message_body(self) -> None:
        normalized = _make_normalized_message(message="super secret confidential text")
        slack_adapter = FakeMessageAdapter(Platform.SLACK, parse_result=Result(success=True, value=normalized))
        connector = _make_connector(slack_adapter=slack_adapter)
        event = PlatformEvent(platform=Platform.SLACK, raw_payload={})

        with self.assertLogs("connector", level="INFO") as captured:
            connector.receive(event)

        combined = "\n".join(captured.output)
        self.assertNotIn("super secret confidential text", combined)

    def test_send_log_output_does_not_contain_attachment_data(self) -> None:
        delivery = DeliveryResult(platform=Platform.SLACK, channel_id="C1", delivered=True)
        slack_adapter = FakeMessageAdapter(Platform.SLACK, deliver_result=Result(success=True, value=delivery))
        connector = _make_connector(slack_adapter=slack_adapter)
        outbound = OutboundMessage(
            platform=Platform.SLACK,
            channel_id="C1",
            content_type=MessageContentType.FILE,
            attachments=[Attachment(filename="a.pdf", content_type="application/pdf", data=b"top-secret-bytes")],
        )

        with self.assertLogs("connector", level="INFO") as captured:
            connector.send(outbound)

        combined = "\n".join(captured.output)
        self.assertNotIn("top-secret-bytes", combined)

    def test_log_output_does_not_contain_bot_token(self) -> None:
        normalized = _make_normalized_message()
        slack_adapter = FakeMessageAdapter(Platform.SLACK, parse_result=Result(success=True, value=normalized))
        connector = _make_connector(slack_adapter=slack_adapter)
        event = PlatformEvent(platform=Platform.SLACK, raw_payload={"token": "xoxb-should-not-be-logged"})

        with self.assertLogs("connector", level="INFO") as captured:
            connector.receive(event)

        combined = "\n".join(captured.output)
        self.assertNotIn("xoxb-should-not-be-logged", combined)

    def test_log_output_contains_required_fields(self) -> None:
        normalized = _make_normalized_message(user_id="U9", channel_id="C9", event_type=EventType.MENTION)
        slack_adapter = FakeMessageAdapter(Platform.SLACK, parse_result=Result(success=True, value=normalized))
        connector = _make_connector(slack_adapter=slack_adapter)
        event = PlatformEvent(platform=Platform.SLACK, raw_payload={})

        with self.assertLogs("connector", level="INFO") as captured:
            connector.receive(event)

        combined = "\n".join(captured.output)
        self.assertIn("timestamp=", combined)
        self.assertIn("platform=slack", combined)
        self.assertIn("user_id=U9", combined)
        self.assertIn("channel_id=C9", combined)
        self.assertIn("event_type=mention", combined)
        self.assertIn("result=success", combined)


if __name__ == "__main__":
    unittest.main()
