"""Connectorテスト用の共有フェイク(unittestテストコードそのものではない)。

実際のSlack/Discord API呼び出しは行わない。`connector.http_client.HttpClient`
プロトコルを満たす決定的なフェイク実装、および`ConfigurationClient`のフェイク実装を提供する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from connector.adapter import MessageAdapter
from connector.http_client import HttpResponse
from connector.types import DeliveryResult, NormalizedMessage, OutboundMessage, Platform
from foundation.interfaces import ConfigurationClient
from foundation.result import Result


class FakeConfigurationClient(ConfigurationClient):
    """設定値取得を模擬するテスト用Fake。インスタンスごとに値を設定できる。"""

    def __init__(self, values: dict[str, Any] | None = None) -> None:
        self.values: dict[str, Any] = dict(values or {})

    def get(self, module_name: str, key: str) -> Result[Any]:  # type: ignore[override]
        if key not in self.values:
            return Result(success=True, value=None)
        return Result(success=True, value=self.values[key])


@dataclass
class FakeHttpClient:
    """`connector.http_client.HttpClient`を満たすフェイク実装。

    `responses`に設定した`HttpResponse`をリクエスト順に返す。`exception`が設定されて
    いる場合は、実際のAPI呼び出し失敗(ネットワーク到達不可等)を模擬して送出する。
    """

    responses: list[HttpResponse] = field(default_factory=list)
    exception: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> HttpResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "json_body": json_body,
                "files": files,
            }
        )
        if self.exception is not None:
            raise self.exception
        if not self.responses:
            raise AssertionError("FakeHttpClient: no response configured for this call")
        return self.responses.pop(0)


class FakeMessageAdapter(MessageAdapter):
    """`connector.connector.SlackDiscordConnector`のテスト用フェイクAdapter。

    `SlackDiscordConnector`が実際のSlack/Discord API呼び出しを行うAdapter実装に
    依存せず、委譲・例外ラップ・ログ出力の振る舞いのみを検証できるようにする。
    """

    def __init__(
        self,
        platform: Platform,
        parse_result: Result[NormalizedMessage] | None = None,
        deliver_result: Result[DeliveryResult] | None = None,
        connection_result: Result[bool] | None = None,
        raise_on_parse: Exception | None = None,
        raise_on_deliver: Exception | None = None,
        raise_on_check: Exception | None = None,
    ) -> None:
        self._platform = platform
        self.parse_result = parse_result
        self.deliver_result = deliver_result
        self.connection_result = connection_result if connection_result is not None else Result(success=True, value=True)
        self.raise_on_parse = raise_on_parse
        self.raise_on_deliver = raise_on_deliver
        self.raise_on_check = raise_on_check
        self.parse_calls: list[Any] = []
        self.deliver_calls: list[OutboundMessage] = []
        self.check_connection_calls = 0

    @property
    def platform(self) -> Platform:
        return self._platform

    def parse_event(self, raw_payload: dict[str, Any]) -> Result[NormalizedMessage]:
        self.parse_calls.append(raw_payload)
        if self.raise_on_parse is not None:
            raise self.raise_on_parse
        assert self.parse_result is not None
        return self.parse_result

    def deliver(self, message: OutboundMessage) -> Result[DeliveryResult]:
        self.deliver_calls.append(message)
        if self.raise_on_deliver is not None:
            raise self.raise_on_deliver
        assert self.deliver_result is not None
        return self.deliver_result

    def check_connection(self) -> Result[bool]:
        self.check_connection_calls += 1
        if self.raise_on_check is not None:
            raise self.raise_on_check
        return self.connection_result
