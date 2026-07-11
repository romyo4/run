"""Notification (M15) パッケージの公開API(IS15 2. ファイル構成)。

新規ロジックは持たず、`NotificationModule`・`types.py` の公開dataclass/Enum・
`errors.py` の例外クラス・`channels.py`/`history.py` の公開シンボルをre-exportする
のみとする。
"""

from notification.channels import ChannelConnector, select_channel
from notification.constants import MAX_RETRY_COUNT, MODULE_NAME, SUPPORTED_CHANNELS
from notification.errors import (
    DeliveryFailedError,
    NotificationError,
    TemplateNotFoundError,
    UnsupportedChannelError,
)
from notification.history import NotificationHistoryStore
from notification.service import NotificationModule
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

__all__ = [
    "Channel",
    "ChannelConnector",
    "DeliveryFailedError",
    "DeliveryResult",
    "DeliveryStatus",
    "EventType",
    "MAX_RETRY_COUNT",
    "MODULE_NAME",
    "NotificationError",
    "NotificationEvent",
    "NotificationHistory",
    "NotificationHistoryStore",
    "NotificationMessage",
    "NotificationModule",
    "SUPPORTED_CHANNELS",
    "TemplateNotFoundError",
    "UnsupportedChannelError",
    "render_message_body",
    "select_channel",
]
