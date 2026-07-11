"""Notification (M15) テスト共通フェイク実装。

ConfigurationClient(F03)の実体はConfiguration Manager(M17)が提供するため、
Foundation `ConfigurationClient` に準拠したフェイクをここに定義し、各テストから
再利用する。ChannelConnector(M21等)の実体も同様にフェイクで代替する。
"""

from __future__ import annotations

from typing import Any

from foundation.errors import ConfigurationError, ExternalServiceError
from foundation.interfaces import ConfigurationClient
from foundation.result import Result
from notification.types import NotificationMessage


def make_fake_configuration_client(
    templates: dict[str, str] | None = None,
) -> type[ConfigurationClient]:
    """テンプレート文字列を保持するフェイク`ConfigurationClient`実装クラスを生成する。

    `templates` に存在しないキーが要求された場合は
    `Result(success=False, error=ConfigurationError(...))` を返す(4.4対応の
    テンプレート未検出ケースを再現するため)。
    """
    template_map = dict(templates or {})

    class _FakeConfigurationClient(ConfigurationClient):
        calls: list[tuple[str, str]] = []

        @staticmethod
        def get(module_name: str, key: str) -> Result[Any]:
            _FakeConfigurationClient.calls.append((module_name, key))
            if key not in template_map:
                return Result(
                    success=False,
                    error=ConfigurationError(f"template not found: {key!r}"),
                )
            return Result(success=True, value=template_map[key])

    return _FakeConfigurationClient


class FakeChannelConnector:
    """`ChannelConnector`(4.1)に準拠したテスト用フェイク実装。

    `fail_count` 回連続で失敗した後に成功する。`always_fail=True` の場合は常に
    失敗する。`raise_exception` を指定した場合、`send()` 呼び出し時にその
    例外を送出する(send()側の予期しない例外捕捉パスを検証するため)。
    """

    def __init__(
        self,
        fail_count: int = 0,
        always_fail: bool = False,
        raise_exception: Exception | None = None,
    ) -> None:
        self.fail_count = fail_count
        self.always_fail = always_fail
        self.raise_exception = raise_exception
        self.send_calls: list[NotificationMessage] = []

    def send(self, message: NotificationMessage) -> Result[bool]:
        self.send_calls.append(message)
        if self.raise_exception is not None:
            raise self.raise_exception

        attempt = len(self.send_calls)
        if self.always_fail or attempt <= self.fail_count:
            return Result(success=False, error=ExternalServiceError("send failed"))
        return Result(success=True, value=True)
