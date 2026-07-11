"""analyze()の実処理: PR群の要約 → WeeklyAnalysis構築(IS13 4.3節)。"""

from __future__ import annotations

from foundation.result import Result
from foundation.types import PullRequest
from weekly_reviewer.errors import WeeklyReviewerValidationError
from weekly_reviewer.models import Project, ReviewPeriod, WeeklyAnalysis

__all__ = ["build_weekly_analysis", "summarize_pull_request"]


def build_weekly_analysis(
    project: Project,
    review_period: ReviewPeriod,
    merged_pull_requests: list[PullRequest],
) -> Result[WeeklyAnalysis]:
    """merged_pull_requestsそれぞれの実装内容を要約し(2.1節)、WeeklyAnalysisを構築する。"""
    if project is None:
        return Result(
            success=False,
            error=WeeklyReviewerValidationError("project must not be None"),
        )
    if merged_pull_requests is None:
        return Result(
            success=False,
            error=WeeklyReviewerValidationError("merged_pull_requests must not be None"),
        )

    summaries = [summarize_pull_request(pull_request) for pull_request in merged_pull_requests]
    analysis = WeeklyAnalysis(
        project_id=project.project_id,
        review_period=review_period,
        merged_pull_requests=list(merged_pull_requests),
        pull_request_summaries=summaries,
    )
    return Result(success=True, value=analysis)


def summarize_pull_request(pull_request: PullRequest) -> str:
    """単一Pull Requestの実装内容を1行程度の要約文字列に変換する。

    Foundationの`PullRequest`はid/created_at/updated_at/metadataのみを保証するため、
    要約に使う実装内容は`metadata["summary"]`または`metadata["title"]`に格納されている
    前提とする(いずれも無い場合はPull Request idを用いた既定の要約文を返す)。
    """
    metadata = pull_request.metadata or {}
    summary = metadata.get("summary") or metadata.get("title")
    if summary:
        return str(summary)
    return f"Pull Request {pull_request.id}"
