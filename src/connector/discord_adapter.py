"""Discord Gateway/REST APIとの入出力を担当するAdapter(IS21 4.3)。

Discord固有の受信イベント解析・送信APIを実装する。実際のネットワークI/Oは
`connector.http_client.HttpClient`へ委譲し、本クラス自身はurllib等を直接扱わない。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from connector.adapter import MessageAdapter
from connector.exceptions import DiscordApiError, EventParseError
from connector.http_client import HttpClient, HttpResponse, UrllibHttpClient
from connector.types import (
    Attachment,
    DeliveryResult,
    EventType,
    MessageContentType,
    NormalizedMessage,
    OutboundMessage,
    Platform,
)
from foundation.interfaces import ConfigurationClient
from foundation.result import Result

_API_BASE_URL = "https://discord.com/api/v10"
_CHECK_CONNECTION_URL = f"{_API_BASE_URL}/users/@me"


class DiscordAdapter(MessageAdapter):
    """Discord Gateway/REST APIとの入出力を担当するAdapter。"""

    def __init__(
        self,
        config_client: ConfigurationClient,
        http_client: HttpClient | None = None,
    ) -> None:
        token_result = config_client.get("connector", "discord_bot_token")
        self._token: str = token_result.value if token_result.success and token_result.value else ""

        bot_user_id_result = config_client.get("connector", "discord_bot_user_id")
        self._bot_user_id: str = bot_user_id_result.value if bot_user_id_result.success and bot_user_id_result.value else ""
        self._http_client: HttpClient = http_client or UrllibHttpClient()

    @property
    def platform(self) -> Platform:
        return Platform.DISCORD

    def parse_event(self, raw_payload: dict[str, Any]) -> Result[NormalizedMessage]:
        """DiscordのMESSAGE_CREATE等のイベントペイロードをNormalizedMessageへ変換する
        (設計書3.3: Message/Mention/File Upload)。解析できない形式はEventParseError。
        """
        try:
            normalized = self._parse_message_create(raw_payload)
        except EventParseError as exc:
            return Result(success=False, error=exc)
        except Exception as exc:  # noqa: BLE001 - 未知の形式を一律EventParseErrorへ変換する
            return Result(success=False, error=EventParseError(str(exc)))
        return Result(success=True, value=normalized)

    def deliver(self, message: OutboundMessage) -> Result[DeliveryResult]:
        """content_typeに応じてDiscord REST APIを呼び分ける(設計書3.4)。
        TEXT/MARKDOWN: メッセージ送信、FILE/IMAGE: 添付ファイル付きメッセージ送信。
        API呼び出し失敗はDiscordApiErrorとしてResult.errorに格納する。
        """
        url = f"{_API_BASE_URL}/channels/{message.channel_id}/messages"
        json_body: dict[str, Any] = {"content": message.text or ""}
        if message.content_type in (MessageContentType.FILE, MessageContentType.IMAGE):
            json_body["attachments"] = [
                {"filename": attachment.filename, "content_type": attachment.content_type}
                for attachment in message.attachments
            ]

        try:
            response = self._http_client.request(
                method="POST",
                url=url,
                headers=self._auth_headers(),
                json_body=json_body,
            )
        except Exception as exc:  # noqa: BLE001 - 外部API呼び出し失敗を一律DiscordApiErrorへ変換する
            return Result(success=False, error=DiscordApiError(self._mask_token(str(exc))))

        if not self._is_success(response):
            return Result(
                success=False,
                error=DiscordApiError(self._mask_token(self._error_summary(response))),
            )

        return Result(
            success=True,
            value=DeliveryResult(
                platform=Platform.DISCORD,
                channel_id=message.channel_id,
                delivered=True,
                message_id=response.json_body.get("id"),
            ),
        )

    def check_connection(self) -> Result[bool]:
        """Bot接続状態(Gateway/REST到達性)を確認する。"""
        try:
            response = self._http_client.request(
                method="GET",
                url=_CHECK_CONNECTION_URL,
                headers=self._auth_headers(),
            )
        except Exception:  # noqa: BLE001 - 到達不可を接続不可判定として扱う
            return Result(success=True, value=False)
        return Result(success=True, value=self._is_success(response))

    # --- 内部ヘルパー ---

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bot {self._token}", "Content-Type": "application/json"}

    @staticmethod
    def _is_success(response: HttpResponse) -> bool:
        return 200 <= response.status_code < 300

    @staticmethod
    def _error_summary(response: HttpResponse) -> str:
        error_code = response.json_body.get("code", "unknown_error")
        return f"discord api call failed: status={response.status_code} error={error_code}"

    def _mask_token(self, text: str) -> str:
        if self._token:
            return text.replace(self._token, "***")
        return text

    def _parse_message_create(self, raw_payload: dict[str, Any]) -> NormalizedMessage:
        if raw_payload.get("type") != "MESSAGE_CREATE":
            raise EventParseError(f"unrecognized discord payload type: {raw_payload.get('type')!r}")

        channel_id = raw_payload.get("channel_id")
        author = raw_payload.get("author")
        content = raw_payload.get("content")
        timestamp_raw = raw_payload.get("timestamp")
        if not channel_id or not isinstance(author, dict) or not author.get("id") or content is None or not timestamp_raw:
            raise EventParseError("discord MESSAGE_CREATE payload is missing required fields")

        attachments_raw = raw_payload.get("attachments") or []
        attachments = [
            Attachment(
                filename=attachment.get("filename", ""),
                content_type=attachment.get("content_type", ""),
                url=attachment.get("url"),
            )
            for attachment in attachments_raw
        ]

        mentions = raw_payload.get("mentions") or []
        is_mention = bool(self._bot_user_id) and any(
            isinstance(mention, dict) and mention.get("id") == self._bot_user_id for mention in mentions
        )

        if is_mention:
            event_type = EventType.MENTION
        elif attachments:
            event_type = EventType.FILE_UPLOAD
        else:
            event_type = EventType.MESSAGE

        return NormalizedMessage(
            platform=Platform.DISCORD,
            user_id=author["id"],
            channel_id=channel_id,
            message=content,
            attachments=attachments,
            timestamp=self._parse_discord_timestamp(timestamp_raw),
            event_type=event_type,
        )

    @staticmethod
    def _parse_discord_timestamp(timestamp_raw: str) -> datetime:
        try:
            return datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise EventParseError(f"invalid discord timestamp: {timestamp_raw!r}") from exc
