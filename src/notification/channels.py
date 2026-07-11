"""ChannelConnectorインターフェース定義 + チャネル選択ロジック(IS15 4.1)。

Slack/Discord/Email への実配信を行う外部Connector(M21等)を表す抽象境界。
Notificationはこのインターフェースを介して配信を依頼するのみで、HTTP/SMTP等の
実通信ロジックは本モジュールに実装しない(8. MVP範囲の明記)。
"""

from __future__ import annotations

from typing import Protocol

from foundation.result import Result
from notification.constants import SUPPORTED_CHANNELS
from notification.errors import UnsupportedChannelError
from notification.types import Channel, NotificationEvent, NotificationMessage


class ChannelConnector(Protocol):
    """Slack/Discord/Email への実配信を行う外部Connector(例: M21)を表す抽象境界。

    Notificationはこのインターフェースを介して配信を依頼するのみで、
    HTTP/SMTP等の実通信ロジックは本モジュールに実装しない。
    """

    def send(self, message: NotificationMessage) -> Result[bool]:
        """1回分の送信試行を行い、成否を返す。再送制御はNotification側(service.py)が行う。

        設計書3.6の公開インターフェース名(M21 Slack/Discord Connector等、実配信を担う
        外部Connectorが実装する`send()`)に合わせた名称(IS15 4.1の`dispatch()`から改称)。
        """
        ...


def select_channel(event: NotificationEvent) -> Result[Channel]:
    """3.3 通知チャネル選択。event.configuration からMVP対応チャネルを決定する。

    対応外チャネルが指定された場合は Result(success=False, error=UnsupportedChannelError) を返す。
    """
    channel_value = event.configuration.get("channel")

    if channel_value is None:
        return Result(
            success=False,
            error=UnsupportedChannelError("event.configuration に channel が指定されていません"),
        )

    if isinstance(channel_value, Channel):
        candidate = channel_value
    else:
        try:
            candidate = Channel(str(channel_value))
        except ValueError:
            return Result(
                success=False,
                error=UnsupportedChannelError(f"未対応のチャネルです: {channel_value!r}"),
            )

    if candidate not in SUPPORTED_CHANNELS:
        return Result(
            success=False,
            error=UnsupportedChannelError(f"未対応のチャネルです: {candidate.value!r}"),
        )

    return Result(success=True, value=candidate)
