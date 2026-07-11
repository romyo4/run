"""GitHub Managerテスト共通フェイク実装。実際のネットワーク通信・設定管理は行わない。"""

from __future__ import annotations

from typing import Any

from foundation.errors import ConfigurationError
from foundation.interfaces import ConfigurationClient
from foundation.result import Result
from github_manager.client import HttpResponse

DEFAULT_TOKEN = "test-access-token-value"


class FakeConfigurationClient(ConfigurationClient):
    """常に固定のaccess_tokenを返すConfigurationClientのフェイク実装。"""

    def __init__(self, token: str = DEFAULT_TOKEN) -> None:
        self._token = token

    def get(self, module_name: str, key: str) -> Result[Any]:  # type: ignore[override]
        if key == "github_access_token":
            return Result(success=True, value=self._token)
        return Result(success=False, error=ConfigurationError(f"unknown key: {key}"))


class FailingConfigurationClient(ConfigurationClient):
    """access_token取得に失敗するConfigurationClientのフェイク実装。"""

    @staticmethod
    def get(module_name: str, key: str) -> Result[Any]:
        return Result(success=False, error=ConfigurationError("configuration unavailable"))


class FakeHttpTransport:
    """HttpTransport Protocolのフェイク実装。実際のネットワーク通信は行わない。"""

    def __init__(self, responses: list[HttpResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str, dict[str, str], float]] = []

    def request(self, method: str, url: str, headers: dict[str, str], timeout: float) -> HttpResponse:
        self.calls.append((method, url, dict(headers), timeout))
        return self._responses.pop(0)


class RaisingHttpTransport:
    """呼び出し時に例外を送出するHttpTransportのフェイク実装(ネットワークエラー再現用)。"""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def request(self, method: str, url: str, headers: dict[str, str], timeout: float) -> HttpResponse:
        raise self._exc
