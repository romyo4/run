"""publish()の実処理: WeeklyReview → WeeklyReport整形(IS13 4.6節)。"""

from __future__ import annotations

from foundation.result import Result
from foundation.utils import generate_id, utc_now
from weekly_reviewer.errors import WeeklyReviewerValidationError
from weekly_reviewer.logging_utils import sanitize_for_log
from weekly_reviewer.models import WeeklyReport, WeeklyReview

__all__ = ["render_weekly_report", "render_summary_text"]


def render_weekly_report(weekly_review: WeeklyReview) -> Result[WeeklyReport]:
    """設計書3.4節の9項目(Review Period/Merged Pull Requests/Business Evaluation/
    MVP Evaluation/Technical Debt/Achievements/Risks/Recommendations/
    Top Priority Next Week)をWeeklyReviewから転記し、Project Owner向けの
    summary_textを整形して付与する。"""
    if weekly_review is None:
        return Result(
            success=False,
            error=WeeklyReviewerValidationError("weekly_review must not be None"),
        )
    if (
        weekly_review.review_period is None
        or weekly_review.business_evaluation is None
        or weekly_review.mvp_evaluation is None
        or weekly_review.technical_debt is None
    ):
        return Result(
            success=False,
            error=WeeklyReviewerValidationError("weekly_review is missing one or more designated evaluation sections"),
        )

    summary_text = render_summary_text(weekly_review)
    report = WeeklyReport(
        id=generate_id(),
        project_id=weekly_review.project_id,
        review_period=weekly_review.review_period,
        merged_pull_requests=list(weekly_review.merged_pull_requests),
        business_evaluation=weekly_review.business_evaluation,
        mvp_evaluation=weekly_review.mvp_evaluation,
        technical_debt=weekly_review.technical_debt,
        achievements=list(weekly_review.achievements),
        risks=list(weekly_review.risks),
        recommendations=list(weekly_review.recommendations),
        top_priority_next_week=list(weekly_review.top_priority_next_week),
        summary_text=summary_text,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    return Result(success=True, value=report)


def render_summary_text(weekly_review: WeeklyReview) -> str:
    """WeeklyReviewの内容を人間可読なテキスト(Markdown想定)に整形する。

    Pull Requestの本文・Secret・Access Token・Credentialを生の形で含めないよう、
    各項目は`sanitize_for_log()`を通してから出力する(設計書4.5節)。
    """
    lines: list[str] = ["# Weekly Review", f"Project: {weekly_review.project_id}"]

    if weekly_review.review_period is not None:
        lines.append(
            "Review Period: "
            f"{weekly_review.review_period.start_date.isoformat()}"
            f"/{weekly_review.review_period.end_date.isoformat()}"
        )

    lines.append(f"Merged Pull Requests: {len(weekly_review.merged_pull_requests)}")

    if weekly_review.business_evaluation is not None:
        lines.append("## Business Evaluation")
        lines.append(f"- alignment_status: {weekly_review.business_evaluation.alignment_status.value}")
        lines.extend(f"- {sanitize_for_log(finding)}" for finding in weekly_review.business_evaluation.findings)

    if weekly_review.mvp_evaluation is not None:
        lines.append("## MVP Evaluation")
        lines.extend(
            f"- unnecessary_feature: {sanitize_for_log(item)}" for item in weekly_review.mvp_evaluation.unnecessary_features
        )
        lines.extend(
            f"- over_engineering: {sanitize_for_log(item)}" for item in weekly_review.mvp_evaluation.over_engineering
        )
        lines.extend(
            f"- priority_inversion: {sanitize_for_log(item)}" for item in weekly_review.mvp_evaluation.priority_inversions
        )

    if weekly_review.technical_debt is not None:
        lines.append("## Technical Debt")
        lines.extend(f"- duplicated_code: {sanitize_for_log(item)}" for item in weekly_review.technical_debt.duplicated_code)
        lines.extend(
            f"- maintainability: {sanitize_for_log(item)}" for item in weekly_review.technical_debt.maintainability_concerns
        )
        lines.extend(
            f"- responsibility: {sanitize_for_log(item)}" for item in weekly_review.technical_debt.responsibility_violations
        )
        lines.extend(f"- naming: {sanitize_for_log(item)}" for item in weekly_review.technical_debt.naming_issues)
        lines.extend(
            f"- documentation_gap: {sanitize_for_log(item)}" for item in weekly_review.technical_debt.documentation_gaps
        )

    lines.append("## Achievements")
    lines.extend(f"- {sanitize_for_log(item)}" for item in weekly_review.achievements)

    lines.append("## Risks")
    lines.extend(f"- {sanitize_for_log(item)}" for item in weekly_review.risks)

    lines.append("## Recommendations")
    lines.extend(f"- {sanitize_for_log(item)}" for item in weekly_review.recommendations)

    lines.append("## Top Priority Next Week")
    lines.extend(f"- {sanitize_for_log(item)}" for item in weekly_review.top_priority_next_week)

    return "\n".join(lines)
