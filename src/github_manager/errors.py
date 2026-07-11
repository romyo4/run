"""GitHub Manager固有の例外階層(IS20仕様書5章)。

Foundationのエラー階層(`foundation.errors`)を継承したモジュール固有例外のみを定義する。
新しい基底例外(`FoundationError`の兄弟)は追加しない(`M00 Foundation.txt` 3.6節)。
"""

from __future__ import annotations

from foundation.errors import ExternalServiceError, NotFoundError, ValidationError

__all__ = [
    "GitHubApiError",
    "RepositoryNotFoundError",
    "BranchNotFoundError",
    "PullRequestNotFoundError",
    "GitHubFileNotFoundError",
    "InvalidDiffTargetError",
]


class GitHubApiError(ExternalServiceError):
    """GitHub API呼び出し失敗(ネットワークエラー・タイムアウト・5xx・認証失敗等)。"""


class RepositoryNotFoundError(NotFoundError):
    """指定Repositoryが存在しない、またはアクセス権がない場合。"""


class BranchNotFoundError(NotFoundError):
    """指定Branchが存在しない場合。"""


class PullRequestNotFoundError(NotFoundError):
    """指定Pull Requestが存在しない場合。"""


class GitHubFileNotFoundError(NotFoundError):
    """指定File Pathが存在しない場合。"""


class InvalidDiffTargetError(ValidationError):
    """get_diff()にcommitとpull_request_numberの両方、またはいずれも指定されなかった場合。"""
