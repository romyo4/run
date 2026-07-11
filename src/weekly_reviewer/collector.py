"""collect()の実処理: 対象期間のMerge済みPull Request収集(IS13 4.2節)。

Review Report/Test Report/Design Audit/Technical Debtの収集(設計書3.2節)は
本モジュールの責務外とし、`WeeklyReviewContext`経由で別途受け渡す(models.py参照)。

Foundationの`PullRequest`はid/created_at/updated_at/metadataのみを保証する
(M00 3.3節)ため、Merge済み判定に必要な情報(`merged` / `merged_at`)は
`PullRequest.metadata`に格納されている前提とする(Reviewer(M12)と同様の規約)。
収集元となるPull Request候補一覧は`Project.project_context["pull_requests"]`に
外部(GitHub Manager等)から事前に格納されている前提とし、当該キーが存在しない場合を
「収集元への問い合わせが失敗した場合」とみなす。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from foundation.result import Result
from foundation.types import PullRequest
from weekly_reviewer.errors import PullRequestCollectionError
from weekly_reviewer.models import Project, ReviewPeriod

__all__ = ["collect_merged_pull_requests", "resolve_review_period"]

_PULL_REQUESTS_KEY = "pull_requests"


def collect_merged_pull_requests(
    project: Project,
    review_period: ReviewPeriod,
) -> Result[list[PullRequest]]:
    """設計書3.2節。対象期間内にMergeされたPull Requestのみを収集する。"""
    if project is None:
        return Result(
            success=False,
            error=PullRequestCollectionError("project is unavailable"),
        )
    if _PULL_REQUESTS_KEY not in project.project_context:
        return Result(
            success=False,
            error=PullRequestCollectionError("pull request source is unavailable in project.project_context"),
        )

    candidates = project.project_context[_PULL_REQUESTS_KEY] or []
    merged: list[PullRequest] = []
    for pull_request in candidates:
        metadata = pull_request.metadata or {}
        if not metadata.get("merged"):
            continue
        merged_date = _to_date(metadata.get("merged_at"))
        if merged_date is None:
            continue
        if review_period.start_date <= merged_date <= review_period.end_date:
            merged.append(pull_request)
    return Result(success=True, value=merged)


def resolve_review_period(review_period_days: int, today: date) -> ReviewPeriod:
    """review_period_days(既定7日)から対象期間(start_date/end_date)を算出する。

    end_dateはtoday、start_dateはtodayからreview_period_days日遡った日付とする。
    """
    start_date = today - timedelta(days=review_period_days)
    return ReviewPeriod(start_date=start_date, end_date=today)


def _to_date(value: object) -> date | None:
    """metadataに格納されたmerge日時(date/datetime/ISO文字列)をdateへ正規化する。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            return None
    return None
