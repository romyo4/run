"""Adapter Pattern共通インターフェース(IS21 4.1)。

設計書4.2「Slack と Discord の違いは Connector 内で吸収する」・Foundation F00
(Adapter Pattern)に対応する層。Slack/Discordそれぞれの実装は本ABCを継承し、
`connector.py`(`SlackDiscordConnector`)はこのインターフェースにのみ依存する。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from connector.types import DeliveryResult, NormalizedMessage, OutboundMessage, Platform
from foundation.result import Result


class MessageAdapter(ABC):
    """Slack/Discordの差異を吸収する共通インターフェース(設計書4.2, Foundation F00)。"""

    @property
    @abstractmethod
    def platform(self) -> Platform:
        """このAdapterが担当するプラットフォームを返す。"""

    @abstractmethod
    def parse_event(self, raw_payload: dict[str, Any]) -> Result[NormalizedMessage]:
        """プラットフォーム固有のPlatform Event(raw_payload)をNormalized Messageへ変換する。"""

    @abstractmethod
    def deliver(self, message: OutboundMessage) -> Result[DeliveryResult]:
        """OutboundMessageをプラットフォームAPI経由で送信する。"""

    @abstractmethod
    def check_connection(self) -> Result[bool]:
        """プラットフォームAPIへの接続可否を確認する。"""
