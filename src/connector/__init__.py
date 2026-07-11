"""Slack / Discord Connector(M21)パッケージ公開API。

`SlackDiscordConnector`・Adapter・データクラス・固有例外を再エクスポートする。
"""

from __future__ import annotations

from connector.adapter import MessageAdapter
from connector.connector import SlackDiscordConnector
from connector.discord_adapter import DiscordAdapter
from connector.exceptions import (
    DiscordApiError,
    EventParseError,
    SlackApiError,
    UnsupportedPlatformError,
)
from connector.http_client import HttpClient, HttpResponse, UrllibHttpClient
from connector.slack_adapter import SlackAdapter
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

__all__ = [
    "SlackDiscordConnector",
    "MessageAdapter",
    "SlackAdapter",
    "DiscordAdapter",
    "HttpClient",
    "HttpResponse",
    "UrllibHttpClient",
    "Platform",
    "EventType",
    "MessageContentType",
    "Attachment",
    "PlatformEvent",
    "NormalizedMessage",
    "OutboundMessage",
    "DeliveryResult",
    "ConnectionStatus",
    "SlackApiError",
    "DiscordApiError",
    "UnsupportedPlatformError",
    "EventParseError",
]
