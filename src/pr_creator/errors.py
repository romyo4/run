"""PR Creator (M11) 固有の例外定義(IS11 5章)。

Foundationの例外階層(FoundationError基底)をそのまま利用し、本モジュール固有の例外は
以下のみ追加する。いずれの例外もstr(exception)にAccess Token・Secret・Credentialの
値を含めてはならない。
"""

from __future__ import annotations

from foundation.errors import ExternalServiceError, NotFoundError, ValidationError

__all__ = [
    "QualityGateNotPassedError",
    "GitHubPullRequestError",
    "PullRequestNotFoundError",
]


class QualityGateNotPassedError(ValidationError):
    """Quality GateがPASSしていない実装成果物に対してcreate_pr()が呼び出された場合に送出する(IS11 4.2)。

    入力(test_report)が作成前提条件を満たさないという意味でValidationErrorを継承する。
    """


class GitHubPullRequestError(ExternalServiceError):
    """GitHub API呼び出し(作成・更新・Reviewer設定)が失敗した場合に送出する。"""


class PullRequestNotFoundError(NotFoundError):
    """update_pr() / assign_reviewers() / publish()の対象Pull RequestがGitHub上に存在しない場合に送出する。"""
