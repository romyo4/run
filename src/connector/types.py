"""Slack / Discord Connector(M21) データ構造定義(IS21 3節)。

設計書3.2(出力構造)・3.4(送信イベント)・3.5(成果物)に対応するdataclass/Enumのみを
定義する。バリデーション・変換ロジックは含まない(データ構造の定義に限定する)。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from foundation.types import CommunicationMessage, Notification
from foundation.utils import utc_now


class Platform(str, Enum):
    """Connectorが対応するプラットフォーム(設計書「適用対象」)。"""

    SLACK = "slack"
    DISCORD = "discord"


class EventType(str, Enum):
    """受信イベント種別(設計書3.3)。Slack/Discord双方で共通に扱う。"""

    MESSAGE = "message"
    MENTION = "mention"
    SLASH_COMMAND = "slash_command"  # Slackのみ(設計書3.3)
    FILE_UPLOAD = "file_upload"


class MessageContentType(str, Enum):
    """送信イベント種別(設計書3.4)。"""

    TEXT = "text"
    MARKDOWN = "markdown"
    FILE = "file"
    IMAGE = "image"


@dataclass
class Attachment:
    """添付ファイル(設計書2.1「添付ファイル受信」、3.2「attachments」)。"""

    filename: str
    content_type: str
    url: str | None = None  # 受信時: プラットフォームがホストするURL
    data: bytes | None = None  # 送信時: 直接渡すバイナリ本体


@dataclass
class PlatformEvent:
    """receive()の入力(設計書3.6「Platform Event」)。

    どちらのプラットフォームからのイベントかを明示するためplatformを持つ。
    raw_payloadは各プラットフォームAPIが渡す生イベントをそのまま保持する。
    """

    platform: Platform
    raw_payload: dict[str, Any]
    received_at: datetime = field(default_factory=utc_now)


@dataclass
class NormalizedMessage:
    """receive()の出力(設計書3.2「Normalized Message」)。

    platform/user_id/channel_id/message/attachments/timestampは設計書3.2に明記された
    構造そのもの。event_typeは設計書4.5のログ項目(event_type)を記録するために必要な
    情報であり、本書で補完した追加フィールドである(受信イベントの種別を保持しないと
    ログ要件を満たせないため)。communication_messageはFoundation(F01)
    `CommunicationMessage` Domainの共通属性(id/created_at/updated_at/metadata)を保持する。
    """

    platform: Platform
    user_id: str
    channel_id: str
    message: str
    attachments: list[Attachment]
    timestamp: datetime
    event_type: EventType
    communication_message: CommunicationMessage = field(default_factory=CommunicationMessage)


@dataclass
class OutboundMessage:
    """send()の入力(設計書3.6「Notification Message」)。IS21 3節補足を参照。"""

    platform: Platform
    channel_id: str
    content_type: MessageContentType
    text: str | None = None
    attachments: list[Attachment] = field(default_factory=list)
    user_id: str | None = None
    notification: Notification = field(default_factory=Notification)


@dataclass
class DeliveryResult:
    """send()の出力(設計書3.5「Delivery Result」)。"""

    platform: Platform
    channel_id: str
    delivered: bool
    message_id: str | None = None  # プラットフォームAPIが返す送信先メッセージID
    error_message: str | None = None
    delivered_at: datetime = field(default_factory=utc_now)


@dataclass
class ConnectionStatus:
    """health()の出力(設計書3.5「Connection Status」)。

    Connectorは1インスタンスでSlack/Discord両方を扱うため(設計書2.1)、
    両プラットフォームの接続可否を1つの成果物にまとめて返す。
    """

    slack_connected: bool
    discord_connected: bool
    checked_at: datetime = field(default_factory=utc_now)
    detail: dict[str, str] = field(default_factory=dict)  # platform名 -> 補足メッセージ(任意)
