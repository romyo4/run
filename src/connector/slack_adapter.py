"""Slack Events API / Web APIとの入出力を担当するAdapter(IS21 4.2)。

Slack固有の受信イベント解析・送信APIを実装する。実際のネットワークI/Oは
`connector.http_client.HttpClient`へ委譲し、本クラス自身はurllib等を直接扱わない。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from connector.adapter import MessageAdapter
from connector.exceptions import EventParseError, SlackApiError
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
from foundation.utils import utc_now

_AUTH_TEST_URL = "https://slack.com/api/auth.test"
_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"
_FILES_UPLOAD_URL = "https://slack.com/api/files.upload"


class SlackAdapter(MessageAdapter):
    """Slack Events API / Web APIとの入出力を担当するAdapter。"""

    def __init__(
        self,
        config_client: ConfigurationClient,
        http_client: HttpClient | None = None,
    ) -> None:
        token_result = config_client.get("connector", "slack_bot_token")
        self._token: str = token_result.value if token_result.success and token_result.value else ""
        self._http_client: HttpClient = http_client or UrllibHttpClient()

    @property
    def platform(self) -> Platform:
        return Platform.SLACK

    def parse_event(self, raw_payload: dict[str, Any]) -> Result[NormalizedMessage]:
        """Slack Events APIペイロード(message/app_mention/slash command/file_shared)を
        NormalizedMessageへ変換する(設計書3.3)。event_typeはペイロードのtype・
        command有無・files有無から判定する。解析できない形式はEventParseError。
        """
        try:
            if "command" in raw_payload:
                normalized = self._parse_slash_command(raw_payload)
            else:
                normalized = self._parse_event_callback(raw_payload)
        except EventParseError as exc:
            return Result(success=False, error=exc)
        except Exception as exc:  # noqa: BLE001 - 未知の形式を一律EventParseErrorへ変換する
            return Result(success=False, error=EventParseError(str(exc)))
        return Result(success=True, value=normalized)

    def deliver(self, message: OutboundMessage) -> Result[DeliveryResult]:
        """content_typeに応じてSlack Web APIを呼び分ける(設計書3.4)。
        TEXT/MARKDOWN: chat.postMessage相当、FILE/IMAGE: files.upload相当。
        API呼び出し失敗はSlackApiErrorとしてResult.errorに格納する。
        """
        if message.content_type in (MessageContentType.TEXT, MessageContentType.MARKDOWN):
            url = _POST_MESSAGE_URL
            json_body: dict[str, Any] = {"channel": message.channel_id, "text": message.text or ""}
            if message.content_type is MessageContentType.MARKDOWN:
                json_body["mrkdwn"] = True
        else:
            url = _FILES_UPLOAD_URL
            json_body = {
                "channels": message.channel_id,
                "title": message.text or "",
                "filename": message.attachments[0].filename if message.attachments else None,
            }

        try:
            response = self._http_client.request(
                method="POST",
                url=url,
                headers=self._auth_headers(),
                json_body=json_body,
            )
        except Exception as exc:  # noqa: BLE001 - 外部API呼び出し失敗を一律SlackApiErrorへ変換する
            return Result(success=False, error=SlackApiError(self._mask_token(str(exc))))

        if not self._is_success(response):
            return Result(
                success=False,
                error=SlackApiError(self._mask_token(self._error_summary(response))),
            )

        message_id = self._extract_message_id(response, message.content_type)
        return Result(
            success=True,
            value=DeliveryResult(
                platform=Platform.SLACK,
                channel_id=message.channel_id,
                delivered=True,
                message_id=message_id,
            ),
        )

    def check_connection(self) -> Result[bool]:
        """auth.test相当のAPI呼び出しで接続可否を確認する。"""
        try:
            response = self._http_client.request(
                method="POST",
                url=_AUTH_TEST_URL,
                headers=self._auth_headers(),
                json_body={},
            )
        except Exception:  # noqa: BLE001 - 到達不可を接続不可判定として扱う
            return Result(success=True, value=False)
        return Result(success=True, value=self._is_success(response))

    # --- 内部ヘルパー ---

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    @staticmethod
    def _is_success(response: HttpResponse) -> bool:
        return response.status_code == 200 and bool(response.json_body.get("ok"))

    @staticmethod
    def _error_summary(response: HttpResponse) -> str:
        error_code = response.json_body.get("error", "unknown_error")
        return f"slack api call failed: status={response.status_code} error={error_code}"

    @staticmethod
    def _extract_message_id(response: HttpResponse, content_type: MessageContentType) -> str | None:
        if content_type in (MessageContentType.FILE, MessageContentType.IMAGE):
            file_info = response.json_body.get("file") or {}
            return file_info.get("id")
        return response.json_body.get("ts")

    def _mask_token(self, text: str) -> str:
        if self._token:
            return text.replace(self._token, "***")
        return text

    def _parse_slash_command(self, raw_payload: dict[str, Any]) -> NormalizedMessage:
        command = raw_payload.get("command")
        channel_id = raw_payload.get("channel_id")
        user_id = raw_payload.get("user_id")
        if not command or not channel_id or not user_id:
            raise EventParseError("slash command payload is missing required fields")

        text = raw_payload.get("text", "")
        message_text = f"{command} {text}".strip()
        return NormalizedMessage(
            platform=Platform.SLACK,
            user_id=user_id,
            channel_id=channel_id,
            message=message_text,
            attachments=[],
            timestamp=utc_now(),
            event_type=EventType.SLASH_COMMAND,
        )

    def _parse_event_callback(self, raw_payload: dict[str, Any]) -> NormalizedMessage:
        event = raw_payload.get("event")
        if not isinstance(event, dict):
            raise EventParseError("unrecognized slack payload: missing 'event'")

        event_type_raw = event.get("type")
        channel_id = event.get("channel")
        user_id = event.get("user")
        ts = event.get("ts")
        if event_type_raw not in ("message", "app_mention") or not channel_id or not user_id or not ts:
            raise EventParseError(f"unrecognized slack event: {event_type_raw!r}")

        files = event.get("files") or []
        if event_type_raw == "app_mention":
            event_type = EventType.MENTION
        elif files:
            event_type = EventType.FILE_UPLOAD
        else:
            event_type = EventType.MESSAGE

        attachments = [
            Attachment(
                filename=file_.get("name", ""),
                content_type=file_.get("mimetype", ""),
                url=file_.get("url_private"),
            )
            for file_ in files
        ]

        return NormalizedMessage(
            platform=Platform.SLACK,
            user_id=user_id,
            channel_id=channel_id,
            message=event.get("text", ""),
            attachments=attachments,
            timestamp=self._parse_slack_ts(ts),
            event_type=event_type,
        )

    @staticmethod
    def _parse_slack_ts(ts: str) -> datetime:
        try:
            return datetime.fromtimestamp(float(ts), tz=UTC)
        except (TypeError, ValueError) as exc:
            raise EventParseError(f"invalid slack ts: {ts!r}") from exc
