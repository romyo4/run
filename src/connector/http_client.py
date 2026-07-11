"""SlackAdapter/DiscordAdapterが外部API呼び出しに用いるHTTPクライアント抽象。

IS21は「実際のSlack/Discord API呼び出しは行わず、HTTPクライアント抽象を介する
(テストではフェイク実装を注入する)」という実装方針を前提とする。本ファイルは
Foundation F00(Adapter Pattern)に倣い、Slack/Discordの実際のネットワークI/Oを
Adapter本体のロジックから切り離すための最小限のインターフェースを追加するのみで、
Connectorの責務(送受信のみ)・公開インターフェース(3関数)を変更しない。
"""

from __future__ import annotations

import json as _json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class HttpResponse:
    """HTTPレスポンスの最小表現。"""

    status_code: int
    json_body: dict[str, Any] = field(default_factory=dict)


class HttpClient(Protocol):
    """Slack Web API / Discord REST APIへのHTTP呼び出しを抽象化する共通インターフェース。

    実装は例外を送出してよい。呼び出し元(SlackAdapter/DiscordAdapter)が
    SlackApiError/DiscordApiErrorへラップする。
    """

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> HttpResponse: ...


class UrllibHttpClient:
    """標準ライブラリ(urllib)のみを用いたデフォルトの実HTTP実装。

    本番相当の通信を行うための最小実装だが、ユニットテストでは必ずフェイク実装
    (`HttpClient`準拠オブジェクト)を注入し、本クラスは経由しない。
    multipart(files)の実送信はMVP範囲外の詳細実装であり、json_bodyのみを送信する。
    """

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> HttpResponse:
        data: bytes | None = None
        if json_body is not None:
            data = _json.dumps(json_body).encode("utf-8")

        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
                body = response.read()
                status_code = response.status
        except urllib.error.HTTPError as exc:
            body = exc.read()
            status_code = exc.code

        try:
            parsed_body = _json.loads(body) if body else {}
        except (ValueError, TypeError):
            parsed_body = {}

        return HttpResponse(status_code=status_code, json_body=parsed_body)
