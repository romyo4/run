"""GitHub REST APIとの通信のみを担当するAdapter層(IS20仕様書4.1節, F00 Adapter Pattern)。

HTTP呼び出し・認証ヘッダー付与・レスポンスJSONの生成のみを行い、業務判断は行わない。
`github_manager.py` からのみ利用される。

実際のHTTP通信は`HttpTransport` Protocolの背後に隠蔽する。テスト実行時は実際の
ネットワーク通信を行わず、`HttpTransport`を満たすフェイク実装を注入することで
`GitHubClient`自体のURL構築・エラー整形ロジックのみを検証できるようにする
(pr_creator.github_client と同様のAdapter/Protocol構成)。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from foundation.errors import ConfigurationError, NotFoundError
from foundation.interfaces import ConfigurationClient
from github_manager.constants import DEFAULT_TIMEOUT_SECONDS, GITHUB_API_BASE_URL
from github_manager.errors import (
    BranchNotFoundError,
    GitHubApiError,
    GitHubFileNotFoundError,
    PullRequestNotFoundError,
    RepositoryNotFoundError,
)

__all__ = [
    "HttpResponse",
    "HttpTransport",
    "UrllibHttpTransport",
    "GitHubClient",
]

_MODULE_NAME = "github_manager"


@dataclass(frozen=True)
class HttpResponse:
    """HttpTransport呼び出しの結果。"""

    status_code: int
    json_body: Any


class HttpTransport(Protocol):
    """GitHubClientが利用する低レベルHTTP通信のProtocol。

    テストではこのProtocolを満たすフェイク実装を注入し、実際のネットワーク通信は行わない。
    """

    def request(self, method: str, url: str, headers: dict[str, str], timeout: float) -> HttpResponse: ...


class UrllibHttpTransport:
    """標準ライブラリ`urllib`のみを用いた既定のHTTP Transport実装。"""

    def request(self, method: str, url: str, headers: dict[str, str], timeout: float) -> HttpResponse:
        request = urllib.request.Request(url, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
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


class GitHubClient:
    """GitHub REST APIとの通信のみを担当するAdapter(IS20仕様書4.1節)。業務判断は行わない。"""

    def __init__(
        self,
        configuration_client: ConfigurationClient,
        transport: HttpTransport | None = None,
    ) -> None:
        """configuration_client経由でaccess_tokenを取得する。トークン自体は
        インスタンス変数として保持するのみで、ログには出力しない。

        `transport` はテスト時に `HttpTransport` のフェイク実装を注入するための任意引数
        (IS20仕様書4.1節「使用するHTTPクライアントライブラリ等は本書の実装判断とする」)。
        省略時は標準ライブラリ`urllib`のみを用いた既定実装を使用する。
        """
        token_result = configuration_client.get(_MODULE_NAME, "github_access_token")
        if not token_result.success or not token_result.value:
            raise ConfigurationError("github_access_tokenをConfigurationClientから取得できませんでした。")
        self._access_token = str(token_result.value)  # ログ・例外メッセージに含めない
        self._transport = transport or UrllibHttpTransport()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/vnd.github+json",
        }

    def _get(
        self,
        url: str,
        not_found_error: type[NotFoundError] | None,
        not_found_message: str,
    ) -> Any:
        try:
            response = self._transport.request("GET", url, self._headers(), DEFAULT_TIMEOUT_SECONDS)
        except Exception as exc:  # noqa: BLE001 - ネットワークエラー・タイムアウト等を一元的にラップする
            raise GitHubApiError(f"GitHub APIへの通信に失敗しました: {exc}") from exc
        if response.status_code == 404 and not_found_error is not None:
            raise not_found_error(not_found_message)
        if response.status_code >= 400:
            raise GitHubApiError(f"GitHub APIがエラーを返しました(status={response.status_code})")
        return response.json_body

    def get_repository(self, repository: str) -> dict[str, Any]:
        """GET /repos/{repository} の生JSONを返す。"""
        url = f"{GITHUB_API_BASE_URL}/repos/{repository}"
        return self._get(url, RepositoryNotFoundError, f"repository '{repository}' not found")

    def get_branch(self, repository: str, branch: str) -> dict[str, Any]:
        """GET /repos/{repository}/branches/{branch} の生JSONを返す。"""
        url = f"{GITHUB_API_BASE_URL}/repos/{repository}/branches/{branch}"
        return self._get(url, BranchNotFoundError, f"branch '{branch}' not found in '{repository}'")

    def get_commit(self, repository: str, commit_sha: str) -> dict[str, Any]:
        """GET /repos/{repository}/commits/{commit_sha} の生JSONを返す。"""
        url = f"{GITHUB_API_BASE_URL}/repos/{repository}/commits/{commit_sha}"
        # IS20仕様書5章にCommit専用のNotFound例外は定義されていないため、
        # 404も含め呼び出し失敗全般としてGitHubApiErrorを送出する。
        return self._get(url, None, "")

    def get_pull_request(self, repository: str, pull_request_number: int) -> dict[str, Any]:
        """GET /repos/{repository}/pulls/{pull_request_number} の生JSONを返す。"""
        url = f"{GITHUB_API_BASE_URL}/repos/{repository}/pulls/{pull_request_number}"
        return self._get(
            url,
            PullRequestNotFoundError,
            f"pull request #{pull_request_number} not found in '{repository}'",
        )

    def get_file_content(self, repository: str, file_path: str, ref: str | None = None) -> dict[str, Any]:
        """GET /repos/{repository}/contents/{file_path}(refは任意のbranch/commit指定)の
        生JSONを返す。"""
        url = f"{GITHUB_API_BASE_URL}/repos/{repository}/contents/{file_path}"
        if ref is not None:
            url = f"{url}?ref={ref}"
        return self._get(url, GitHubFileNotFoundError, f"file '{file_path}' not found in '{repository}'")

    def get_commit_diff(self, repository: str, commit_sha: str) -> dict[str, Any]:
        """GET /repos/{repository}/commits/{commit_sha}(diff情報含む)の生JSONを返す。"""
        url = f"{GITHUB_API_BASE_URL}/repos/{repository}/commits/{commit_sha}"
        return self._get(url, None, "")

    def get_pull_request_diff(self, repository: str, pull_request_number: int) -> list[dict[str, Any]]:
        """GET /repos/{repository}/pulls/{pull_request_number}/files の生JSONを返す。

        GitHub REST APIの実際のレスポンスはJSON配列であるため、返り値の型は
        実際のレスポンス形状に忠実な `list[dict[str, Any]]` とする。
        """
        url = f"{GITHUB_API_BASE_URL}/repos/{repository}/pulls/{pull_request_number}/files"
        result = self._get(
            url,
            PullRequestNotFoundError,
            f"pull request #{pull_request_number} not found in '{repository}'",
        )
        return result if isinstance(result, list) else []
