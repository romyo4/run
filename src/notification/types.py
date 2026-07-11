"""Notification (M15) データクラス定義(IS15 3. データクラス定義)。

Foundationの `foundation.types.Notification`(F01 Domain Model、共通属性
`id` / `created_at` / `updated_at` / `metadata` を持つ)を継承・利用する。
`Event` / `Delivery Result` はFoundation共通Domainに存在しないため、本モジュール
固有のdataclassとして定義する。

備考:
    `NotificationDomain` の共通属性はすべて `default_factory` を持つため、
    サブクラス側で追加する非デフォルトフィールドは `@dataclass(kw_only=True)` を
    付与することで、dataclassのフィールド順序制約(非デフォルト引数がデフォルト
    引数より前に来る必要がある)に抵触せず継承できる。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from foundation.types import Notification as NotificationDomain


class EventType(str, Enum):
    """3.2 通知対象に対応"""

    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    PULL_REQUEST_CREATED = "pull_request_created"
    REVIEW_COMPLETED = "review_completed"
    WEEKLY_REVIEW_COMPLETED = "weekly_review_completed"
    SYSTEM_ERROR = "system_error"


class Channel(str, Enum):
    """3.3 通知チャネル(MVP対象のみ。LINE/Teams/SMS/Pushは対象外)"""

    SLACK = "slack"
    DISCORD = "discord"
    EMAIL = "email"


class DeliveryStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


@dataclass(frozen=True)
class NotificationEvent:
    """3.1 入力 / create_message()の入力。受領後、いかなる値も変更しない(4.2)。"""

    workflow_id: str
    event_type: EventType
    event_result: dict[str, Any]
    recipient: str
    notification_template: str
    configuration: dict[str, Any]


@dataclass(kw_only=True)
class NotificationMessage(NotificationDomain):
    """3.5 成果物: Notification Message。F01 Notification Domainを継承。"""

    workflow_id: str
    event_type: EventType
    channel: Channel
    recipient: str
    subject: str
    body: str
    template_id: str


@dataclass
class DeliveryResult:
    """3.5 成果物: Delivery Result。send()の戻り値。"""

    message_id: str
    workflow_id: str
    event_type: EventType
    channel: Channel
    status: DeliveryStatus
    retry_count: int
    duration_ms: float
    error_message: str | None = None


@dataclass(kw_only=True)
class NotificationHistory(NotificationDomain):
    """3.5 成果物: Notification History。publish()の戻り値。4.5ログ項目に対応。

    Notificationドメイン共通属性の created_at を 4.5 の timestamp として扱う。
    """

    workflow_id: str
    event_type: EventType
    channel: Channel
    delivery_status: DeliveryStatus
    retry_count: int
    duration_ms: float
