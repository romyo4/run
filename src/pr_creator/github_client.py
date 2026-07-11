"""GitHub Pull Request作成・更新・Reviewer割当を行うAdapter層(IS11 2章 github_client.py, F00 Adapter Pattern)。

GitHub REST API呼び出しの唯一の窓口。Access Tokenは呼び出し(HTTPヘッダー構築)以外の
目的で保持・ログ出力しない。

実際のHTTP通信は`HttpTransport` Protocolの背後に隠蔽する。テスト実行時は本物の
GitHub APIへ通信せず、`HttpTransport`のフェイク実装を注入することで
`GitHubPullRequestClient`自体のURL構築・エラー整形ロジックのみを検証できるようにする。
`GitHubPullRequestClientProtocol`は、`PRCreator`側が具象実装(本クラス)とテスト用の
フェイト実装のどちらにも依存できるようにするためのインターフェースである。

## GitHub Manager(M20)との役割分担(2026-07 統合レビューでの確認事項)

GitHub Manager(M20)は「GitHub操作のみ」を担当するが、`Pull Request作成`は設計書
M20 2.2節で明示的に対象外(GitHub Managerの責務外)とされており、書き込み系API
(create_pull_request/update_pull_request/request_reviewers)はGitHub Manager側に
存在しない(設計書M20 4.3「Repository更新はExecutorまたはPR Creatorが担当」)。
そのため本ファイルが書き込み系GitHub API呼び出しを独自に実装すること自体は、
設計書に忠実な役割分担であり重複ではない。

一方、本ファイルの`get_pull_request()`(作成直後のURL確認用の読み取り)は、GitHub
Manager の`get_pull_request()`と機能的に重なって見える。しかし GitHub Manager の
`PullRequestMetadata`(設計書M20 3.2「PR Number, Status, Changed Files」)は最小取得
方針(設計書M20 4.4)により Pull Request URL を含まない設計であるため、PR Creator が
作成直後に必要とするURL確認をGitHub Manager経由へ委譲することはできない
(GitHub ManagerのDomain定義を設計書の範囲を超えて拡張しない限り不可能であり、本タスクの
是正範囲では新機能追加を避けるためGitHub Manager側の拡張は行わない)。
したがって、この限定的な重複は意図的なものであり是正を要しない。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from foundation.errors import ExternalServiceError, NotFoundError
from foundation.result import Result
from pr_creator.models import BranchInformation, RepositoryInformation

__all__ = [
    "HttpResponse",
    "HttpTransport",
    "UrllibHttpTransport",
    "GitHubPullRequestClientProtocol",
    "GitHubPullRequestClient",
]

GITHUB_API_BASE_URL = "https://api.github.com"


@dataclass(frozen=True)
class HttpResponse:
    """HttpTransport呼び出しの結果。"""

    status_code: int
    json_body: dict[str, object]


class HttpTransport(Protocol):
    """GitHubPullRequestClientが利用する低レベルHTTP通信のProtocol。

    テストではこのProtocolを満たすフェイク実装を注入し、実際のネットワーク通信は行わない。
    """

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        json_body: dict[str, object] | None = None,
    ) -> HttpResponse: ...


class UrllibHttpTransport:
    """標準ライブラリ`urllib`のみを用いた既定のHTTP Transport実装。"""

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        json_body: dict[str, object] | None = None,
    ) -> HttpResponse:
        data = json.dumps(json_body).encode("utf-8") if json_body is not None else None
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request) as response:
                body = response.read().decode("utf-8")
                parsed = json.loads(body) if body else {}
                return HttpResponse(status_code=response.status, json_body=parsed)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            try:
                parsed = json.loads(body) if body else {}
            except json.JSONDecodeError:
                parsed = {"message": body}
            return HttpResponse(status_code=exc.code, json_body=parsed)


class GitHubPullRequestClientProtocol(Protocol):
    """PRCreatorが依存するGitHub Pull Request操作のインターフェース(IS11 4章)。"""

    def create_pull_request(
        self,
        repository: RepositoryInformation,
        branch: BranchInformation,
        title: str,
        body: str,
    ) -> Result[dict[str, object]]: ...

    def update_pull_request(
        self,
        repository: RepositoryInformation,
        pull_request_number: int,
        title: str | None = None,
        body: str | None = None,
        labels: list[str] | None = None,
    ) -> Result[dict[str, object]]: ...

    def request_reviewers(
        self,
        repository: RepositoryInformation,
        pull_request_number: int,
        reviewers: list[str],
        team_reviewers: list[str] | None = None,
    ) -> Result[dict[str, object]]: ...

    def get_pull_request(
        self,
        repository: RepositoryInformation,
        pull_request_number: int,
    ) -> Result[dict[str, object]]: ...


class GitHubPullRequestClient:
    """GitHub Pull Request操作の唯一の窓口(F00 Adapter Pattern)。"""

    def __init__(self, access_token: str, transport: HttpTransport | None = None) -> None:
        self._access_token = access_token  # ログ出力・例外メッセージに含めない
        self._transport = transport or UrllibHttpTransport()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        }

    def create_pull_request(
        self,
        repository: RepositoryInformation,
        branch: BranchInformation,
        title: str,
        body: str,
    ) -> Result[dict[str, object]]:
        url = f"{GITHUB_API_BASE_URL}/repos/{repository.owner}/{repository.name}/pulls"
        payload: dict[str, object] = {
            "title": title,
            "body": body,
            "base": branch.base_branch,
            "head": branch.head_branch,
        }
        response = self._transport.request("POST", url, self._headers(), payload)
        if response.status_code >= 400:
            return Result(
                success=False,
                error=ExternalServiceError(self._format_error("Pull Request作成", response)),
            )
        return Result(success=True, value=response.json_body)

    def update_pull_request(
        self,
        repository: RepositoryInformation,
        pull_request_number: int,
        title: str | None = None,
        body: str | None = None,
        labels: list[str] | None = None,
    ) -> Result[dict[str, object]]:
        url = f"{GITHUB_API_BASE_URL}/repos/{repository.owner}/{repository.name}" f"/pulls/{pull_request_number}"
        payload: dict[str, object] = {}
        if title is not None:
            payload["title"] = title
        if body is not None:
            payload["body"] = body
        response = self._transport.request("PATCH", url, self._headers(), payload)
        if response.status_code == 404:
            return Result(
                success=False,
                error=NotFoundError(self._format_error("Pull Request更新", response)),
            )
        if response.status_code >= 400:
            return Result(
                success=False,
                error=ExternalServiceError(self._format_error("Pull Request更新", response)),
            )
        result_body = dict(response.json_body)
        if labels is not None:
            labels_url = (
                f"{GITHUB_API_BASE_URL}/repos/{repository.owner}/{repository.name}" f"/issues/{pull_request_number}/labels"
            )
            labels_response = self._transport.request("PUT", labels_url, self._headers(), {"labels": labels})
            if labels_response.status_code >= 400:
                return Result(
                    success=False,
                    error=ExternalServiceError(self._format_error("Label更新", labels_response)),
                )
            result_body["labels"] = labels_response.json_body
        return Result(success=True, value=result_body)

    def request_reviewers(
        self,
        repository: RepositoryInformation,
        pull_request_number: int,
        reviewers: list[str],
        team_reviewers: list[str] | None = None,
    ) -> Result[dict[str, object]]:
        url = (
            f"{GITHUB_API_BASE_URL}/repos/{repository.owner}/{repository.name}"
            f"/pulls/{pull_request_number}/requested_reviewers"
        )
        payload: dict[str, object] = {
            "reviewers": reviewers,
            "team_reviewers": team_reviewers or [],
        }
        response = self._transport.request("POST", url, self._headers(), payload)
        if response.status_code >= 400:
            return Result(
                success=False,
                error=ExternalServiceError(self._format_error("Reviewer設定", response)),
            )
        return Result(success=True, value=response.json_body)

    def get_pull_request(
        self,
        repository: RepositoryInformation,
        pull_request_number: int,
    ) -> Result[dict[str, object]]:
        url = f"{GITHUB_API_BASE_URL}/repos/{repository.owner}/{repository.name}" f"/pulls/{pull_request_number}"
        response = self._transport.request("GET", url, self._headers(), None)
        if response.status_code == 404:
            return Result(
                success=False,
                error=NotFoundError(self._format_error("Pull Request取得", response)),
            )
        if response.status_code >= 400:
            return Result(
                success=False,
                error=ExternalServiceError(self._format_error("Pull Request取得", response)),
            )
        return Result(success=True, value=response.json_body)

    @staticmethod
    def _format_error(operation: str, response: HttpResponse) -> str:
        message = "unknown error"
        if isinstance(response.json_body, dict):
            message = str(response.json_body.get("message", "unknown error"))
        return f"{operation}に失敗しました(status={response.status_code}): {message}"
