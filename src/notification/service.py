"""NotificationModule (M15) 本体(IS15 4.4)。

`BaseModule`(F02)を継承した`NotificationModule`。公開インターフェース3メソッド
(create_message/send/publish)を実装するオーケストレーション層。

責務外操作の禁止(設計書4.1 / IS15 5.1): 本モジュールは通知の生成・チャネル選択・
配信結果の記録までを担当し、Workflow起動・コード生成・Pull Request作成・レビュー
等は一切行わない。
"""

from __future__ import annotations

import logging
import time

from foundation.base_module import BaseModule
from foundation.errors import ExternalServiceError, ValidationError
from foundation.interfaces import ConfigurationClient
from foundation.logger import get_logger
from foundation.result import Result
from foundation.validation import require_non_empty, require_not_none
from notification.channels import ChannelConnector, select_channel
from notification.constants import MAX_RETRY_COUNT, MODULE_NAME
from notification.errors import UnsupportedChannelError
from notification.history import NotificationHistoryStore
from notification.templates import render_message_body
from notification.types import (
    Channel,
    DeliveryResult,
    DeliveryStatus,
    EventType,
    NotificationEvent,
    NotificationHistory,
    NotificationMessage,
)

logger = get_logger(MODULE_NAME)


class NotificationModule(BaseModule):
    """Workflowイベントを受け取り、通知メッセージの生成・配信・履歴記録を行う。"""

    def __init__(
        self,
        config_client: ConfigurationClient,
        channel_connectors: dict[Channel, ChannelConnector],
        history_store: NotificationHistoryStore,
    ) -> None:
        self._config_client = config_client
        self._channel_connectors = channel_connectors
        self._history_store = history_store
        self._logger = logger

    def name(self) -> str:
        """'notification' を返す(F02 BaseModule)。"""
        return MODULE_NAME

    def health_check(self) -> Result[bool]:
        """依存先(ConfigurationClient等)への疎通確認結果を返す(F02 BaseModule)。"""
        try:
            self._config_client.get(MODULE_NAME, "health_check")
        except Exception as exc:  # noqa: BLE001 - 疎通確認失敗として捕捉する
            self._logger.error("stage=health_check result=failure error_type=%s", type(exc).__name__)
            return Result(success=False, error=ExternalServiceError(str(exc)))
        return Result(success=True, value=True)

    def create_message(self, event: NotificationEvent) -> Result[NotificationMessage]:
        """3.6 create_message(): Event を受け取り、テンプレートをレンダリングして
        NotificationMessage を生成する。event自体は変更しない(4.2)。
        """
        try:
            require_not_none(event, "event")
            require_non_empty(event.workflow_id, "workflow_id")
            require_not_none(event.event_type, "event_type")
            require_not_none(event.event_result, "event_result")
            require_non_empty(event.recipient, "recipient")
            require_non_empty(event.notification_template, "notification_template")
            require_not_none(event.configuration, "configuration")
        except ValidationError as exc:
            return Result(success=False, error=exc)

        channel_result = select_channel(event)
        if not channel_result.success or channel_result.value is None:
            return Result(success=False, error=channel_result.error)

        body_result = render_message_body(event, self._config_client)
        if not body_result.success or body_result.value is None:
            return Result(success=False, error=body_result.error)

        message = NotificationMessage(
            workflow_id=event.workflow_id,
            event_type=event.event_type,
            channel=channel_result.value,
            recipient=event.recipient,
            subject=self._build_subject(event.event_type),
            body=body_result.value,
            template_id=event.notification_template,
        )

        self._logger.info(
            "workflow_id=%s event_type=%s stage=create_message_completed",
            message.workflow_id,
            message.event_type.value,
        )
        return Result(success=True, value=message)

    def send(self, message: NotificationMessage) -> Result[DeliveryResult]:
        """3.6 send(): NotificationMessage を対応するChannelConnectorへ委譲して配信する。

        送信失敗時は最大3回まで再送し(4.3)、それでも失敗した場合は
        DeliveryStatus.FAILED として結果を返す(例外は送出せずResult内に格納)。
        """
        connector = self._channel_connectors.get(message.channel)
        if connector is None:
            return Result(
                success=False,
                error=UnsupportedChannelError(f"チャネルに対応するConnectorが登録されていません: {message.channel.value!r}"),
            )

        start = time.perf_counter()
        last_error_message: str | None = None

        try:
            for attempt in range(MAX_RETRY_COUNT):
                self._logger.info(
                    "workflow_id=%s event_type=%s channel=%s retry_count=%d stage=send_attempt",
                    message.workflow_id,
                    message.event_type.value,
                    message.channel.value,
                    attempt,
                )
                send_result = connector.send(message)

                if send_result.success and send_result.value:
                    duration_ms = self._elapsed_ms(start)
                    self._log_send_completed(message, DeliveryStatus.SUCCESS, attempt, duration_ms)
                    return Result(
                        success=True,
                        value=DeliveryResult(
                            message_id=message.id,
                            workflow_id=message.workflow_id,
                            event_type=message.event_type,
                            channel=message.channel,
                            status=DeliveryStatus.SUCCESS,
                            retry_count=attempt,
                            duration_ms=duration_ms,
                            error_message=None,
                        ),
                    )

                last_error_message = self._extract_error_message(send_result.error)
                if attempt < MAX_RETRY_COUNT - 1:
                    self._logger.warning(
                        "workflow_id=%s event_type=%s channel=%s retry_count=%d stage=send_retry",
                        message.workflow_id,
                        message.event_type.value,
                        message.channel.value,
                        attempt + 1,
                    )
        except Exception as exc:  # noqa: BLE001 - Connector呼び出し中の予期しない例外
            self._logger.error(
                "workflow_id=%s event_type=%s channel=%s stage=send_exception error_type=%s",
                message.workflow_id,
                message.event_type.value,
                message.channel.value,
                type(exc).__name__,
            )
            return Result(success=False, error=ExternalServiceError(str(exc)))

        duration_ms = self._elapsed_ms(start)
        self._log_send_completed(message, DeliveryStatus.FAILED, MAX_RETRY_COUNT, duration_ms)
        return Result(
            success=True,
            value=DeliveryResult(
                message_id=message.id,
                workflow_id=message.workflow_id,
                event_type=message.event_type,
                channel=message.channel,
                status=DeliveryStatus.FAILED,
                retry_count=MAX_RETRY_COUNT,
                duration_ms=duration_ms,
                error_message=last_error_message,
            ),
        )

    def publish(self, delivery_result: DeliveryResult) -> Result[NotificationHistory]:
        """3.6 publish(): DeliveryResult を NotificationHistory へ変換し、
        NotificationHistoryStoreへ記録した上で返す。
        """
        try:
            require_not_none(delivery_result, "delivery_result")
        except ValidationError as exc:
            return Result(success=False, error=exc)

        history = NotificationHistory(
            workflow_id=delivery_result.workflow_id,
            event_type=delivery_result.event_type,
            channel=delivery_result.channel,
            delivery_status=delivery_result.status,
            retry_count=delivery_result.retry_count,
            duration_ms=delivery_result.duration_ms,
        )

        append_result = self._history_store.append(history)
        if not append_result.success:
            return Result(
                success=False,
                error=ExternalServiceError("notification historyの記録に失敗しました"),
            )

        self._logger.info(
            "workflow_id=%s event_type=%s channel=%s delivery_result=%s retry_count=%d "
            "duration=%.2fms stage=publish_completed",
            history.workflow_id,
            history.event_type.value,
            history.channel.value,
            history.delivery_status.value,
            history.retry_count,
            history.duration_ms,
        )
        return Result(success=True, value=history)

    @staticmethod
    def _build_subject(event_type: EventType) -> str:
        return event_type.value.replace("_", " ").title()

    @staticmethod
    def _elapsed_ms(start: float) -> float:
        return (time.perf_counter() - start) * 1000

    @staticmethod
    def _extract_error_message(error: object) -> str | None:
        if error is None:
            return None
        message = getattr(error, "message", None)
        if message:
            return str(message)
        return str(error)

    def _log_send_completed(
        self,
        message: NotificationMessage,
        status: DeliveryStatus,
        retry_count: int,
        duration_ms: float,
    ) -> None:
        level = logging.INFO if status is DeliveryStatus.SUCCESS else logging.ERROR
        self._logger.log(
            level,
            "workflow_id=%s event_type=%s channel=%s delivery_result=%s retry_count=%d "
            "duration=%.2fms stage=send_completed",
            message.workflow_id,
            message.event_type.value,
            message.channel.value,
            status.value,
            retry_count,
            duration_ms,
        )
