"""IS15 7. `tests/test_service.py` に対応するテスト。"""

from __future__ import annotations

import copy
import unittest

from foundation.errors import ValidationError
from notification.constants import MAX_RETRY_COUNT
from notification.errors import UnsupportedChannelError
from notification.history import NotificationHistoryStore
from notification.service import NotificationModule
from notification.types import (
    Channel,
    DeliveryResult,
    DeliveryStatus,
    EventType,
    NotificationEvent,
)

from .fakes import FakeChannelConnector, make_fake_configuration_client

TEMPLATE_ID = "workflow_completed"
TEMPLATE_STR = "Workflow Completed\n\nWorkflow:\n{workflow}\n\nStatus:\n{status}"


def _build_event(
    workflow_id: str = "wf-001",
    channel_value: str = "slack",
) -> NotificationEvent:
    return NotificationEvent(
        workflow_id=workflow_id,
        event_type=EventType.WORKFLOW_COMPLETED,
        event_result={"workflow": "LP Improvement", "status": "Completed"},
        recipient="#dev-notifications",
        notification_template=TEMPLATE_ID,
        configuration={"channel": channel_value},
    )


def _build_module(
    connector: FakeChannelConnector | None = None,
    channel: Channel = Channel.SLACK,
) -> tuple[NotificationModule, FakeChannelConnector, NotificationHistoryStore]:
    config_client = make_fake_configuration_client({TEMPLATE_ID: TEMPLATE_STR})()
    connector = connector if connector is not None else FakeChannelConnector()
    history_store = NotificationHistoryStore()
    module = NotificationModule(
        config_client=config_client,
        channel_connectors={channel: connector},
        history_store=history_store,
    )
    return module, connector, history_store


class NameReturnsNotificationTest(unittest.TestCase):
    def test_name_returns_notification(self) -> None:
        module, _, _ = _build_module()
        self.assertEqual(module.name(), "notification")


class HealthCheckSuccessTest(unittest.TestCase):
    def test_health_check_success(self) -> None:
        module, _, _ = _build_module()
        result = module.health_check()
        self.assertTrue(result.success)
        self.assertTrue(result.value)


class CreateMessageSuccessTest(unittest.TestCase):
    def test_create_message_success(self) -> None:
        module, _, _ = _build_module()
        event = _build_event()

        result = module.create_message(event)

        self.assertTrue(result.success)
        message = result.value
        assert message is not None
        self.assertEqual(message.workflow_id, "wf-001")
        self.assertEqual(message.event_type, EventType.WORKFLOW_COMPLETED)
        self.assertEqual(message.channel, Channel.SLACK)
        self.assertIn("LP Improvement", message.body)
        self.assertEqual(message.template_id, TEMPLATE_ID)


class CreateMessageMissingRequiredFieldTest(unittest.TestCase):
    def test_create_message_missing_required_field_returns_validation_error(self) -> None:
        module, _, _ = _build_module()
        event = NotificationEvent(
            workflow_id="",
            event_type=EventType.WORKFLOW_COMPLETED,
            event_result={"workflow": "LP Improvement", "status": "Completed"},
            recipient="#dev-notifications",
            notification_template=TEMPLATE_ID,
            configuration={"channel": "slack"},
        )

        result = module.create_message(event)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, ValidationError)


class CreateMessageDoesNotMutateEventTest(unittest.TestCase):
    def test_create_message_does_not_mutate_event(self) -> None:
        module, _, _ = _build_module()
        event = _build_event()
        before = copy.deepcopy(event)

        result = module.create_message(event)

        self.assertTrue(result.success)
        self.assertEqual(event, before)


class SendSuccessOnFirstAttemptTest(unittest.TestCase):
    def test_send_success_on_first_attempt(self) -> None:
        connector = FakeChannelConnector(fail_count=0)
        module, connector, _ = _build_module(connector=connector)
        message = module.create_message(_build_event()).value
        assert message is not None

        result = module.send(message)

        self.assertTrue(result.success)
        delivery_result = result.value
        assert delivery_result is not None
        self.assertEqual(delivery_result.status, DeliveryStatus.SUCCESS)
        self.assertEqual(delivery_result.retry_count, 0)


class SendRetriesThenSucceedsTest(unittest.TestCase):
    def test_send_retries_up_to_three_times_then_succeeds(self) -> None:
        connector = FakeChannelConnector(fail_count=2)
        module, connector, _ = _build_module(connector=connector)
        message = module.create_message(_build_event()).value
        assert message is not None

        result = module.send(message)

        self.assertTrue(result.success)
        delivery_result = result.value
        assert delivery_result is not None
        self.assertEqual(delivery_result.status, DeliveryStatus.SUCCESS)
        self.assertEqual(delivery_result.retry_count, 2)
        self.assertEqual(len(connector.send_calls), 3)


class SendFailsAfterMaxRetriesTest(unittest.TestCase):
    def test_send_fails_after_max_retries(self) -> None:
        connector = FakeChannelConnector(always_fail=True)
        module, connector, _ = _build_module(connector=connector)
        message = module.create_message(_build_event()).value
        assert message is not None

        result = module.send(message)

        self.assertTrue(result.success)
        delivery_result = result.value
        assert delivery_result is not None
        self.assertEqual(delivery_result.status, DeliveryStatus.FAILED)
        self.assertEqual(delivery_result.retry_count, MAX_RETRY_COUNT)
        self.assertEqual(len(connector.send_calls), MAX_RETRY_COUNT)


class SendUnsupportedChannelTest(unittest.TestCase):
    def test_send_unsupported_channel_returns_error(self) -> None:
        # channel_connectorsにEMAILが登録されていない状態でEMAIL宛メッセージを送信する
        module, _, _ = _build_module(channel=Channel.SLACK)
        message = module.create_message(_build_event()).value
        assert message is not None
        message.channel = Channel.EMAIL

        result = module.send(message)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, UnsupportedChannelError)


class SendRecordsDurationTest(unittest.TestCase):
    def test_send_records_duration(self) -> None:
        module, _, _ = _build_module()
        message = module.create_message(_build_event()).value
        assert message is not None

        result = module.send(message)

        self.assertTrue(result.success)
        delivery_result = result.value
        assert delivery_result is not None
        self.assertGreaterEqual(delivery_result.duration_ms, 0)


class PublishCreatesHistoryTest(unittest.TestCase):
    def test_publish_creates_history_from_delivery_result(self) -> None:
        module, _, history_store = _build_module()
        delivery_result = DeliveryResult(
            message_id="msg-001",
            workflow_id="wf-001",
            event_type=EventType.WORKFLOW_COMPLETED,
            channel=Channel.SLACK,
            status=DeliveryStatus.SUCCESS,
            retry_count=0,
            duration_ms=5.0,
        )

        result = module.publish(delivery_result)

        self.assertTrue(result.success)
        history = result.value
        assert history is not None
        self.assertEqual(history.workflow_id, "wf-001")
        self.assertEqual(history.event_type, EventType.WORKFLOW_COMPLETED)
        self.assertEqual(history.channel, Channel.SLACK)
        self.assertEqual(history.delivery_status, DeliveryStatus.SUCCESS)
        self.assertEqual(history.retry_count, 0)
        self.assertEqual(history.duration_ms, 5.0)

        list_result = history_store.list_all()
        assert list_result.value is not None
        self.assertIn(history, list_result.value)


class PublishDoesNotSendOrGenerateMessageTest(unittest.TestCase):
    def test_publish_does_not_send_or_generate_message(self) -> None:
        connector = FakeChannelConnector()
        config_client = make_fake_configuration_client({TEMPLATE_ID: TEMPLATE_STR})()
        history_store = NotificationHistoryStore()
        module = NotificationModule(
            config_client=config_client,
            channel_connectors={Channel.SLACK: connector},
            history_store=history_store,
        )
        delivery_result = DeliveryResult(
            message_id="msg-001",
            workflow_id="wf-001",
            event_type=EventType.WORKFLOW_COMPLETED,
            channel=Channel.SLACK,
            status=DeliveryStatus.SUCCESS,
            retry_count=0,
            duration_ms=5.0,
        )

        result = module.publish(delivery_result)

        self.assertTrue(result.success)
        self.assertEqual(len(connector.send_calls), 0)
        self.assertEqual(len(config_client.calls), 0)


class NoWorkflowControlMethodsTest(unittest.TestCase):
    def test_notification_module_does_not_expose_workflow_control_methods(self) -> None:
        public_methods = {
            name
            for name in dir(NotificationModule)
            if not name.startswith("_") and callable(getattr(NotificationModule, name))
        }
        # 3.6公開インターフェース(name/health_check/create_message/send/publish)のみ
        self.assertEqual(
            public_methods,
            {"name", "health_check", "create_message", "send", "publish"},
        )

        forbidden_names = {
            "run_workflow",
            "start_workflow",
            "generate_code",
            "create_pull_request",
            "review",
            "review_code",
        }
        for forbidden in forbidden_names:
            self.assertFalse(hasattr(NotificationModule, forbidden))


if __name__ == "__main__":
    unittest.main()
