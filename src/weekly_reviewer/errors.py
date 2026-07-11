"""Weekly Reviewer固有例外(Foundationエラー階層を継承、IS13 5節)。"""

from __future__ import annotations

from foundation.errors import ConfigurationError, ExternalServiceError, ValidationError

__all__ = [
    "WeeklyReviewerValidationError",
    "WeeklyReviewerConfigurationError",
    "PullRequestCollectionError",
    "FableEvaluationError",
]


class WeeklyReviewerValidationError(ValidationError):
    """collect/analyze/evaluate/publishへの入力(Project/PullRequestリスト/
    WeeklyAnalysis/WeeklyReview)がNoneまたは不正な場合に送出。"""


class WeeklyReviewerConfigurationError(ConfigurationError):
    """ConfigurationClient.get("weekly_reviewer", key)によるreview_period_days/
    business_goal取得の失敗、または必須設定値欠落時に送出。"""


class PullRequestCollectionError(ExternalServiceError):
    """Merge済みPull Requestの収集元(GitHub Manager等)への問い合わせが
    失敗した場合に送出。"""


class FableEvaluationError(ExternalServiceError):
    """Fableレビューエンジン呼び出し(business/mvp/technical debt/priority評価)が
    失敗した場合に送出。"""
