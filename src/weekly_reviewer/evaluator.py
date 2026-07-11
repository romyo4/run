"""evaluate()の実処理: Business/MVP/技術的負債/優先順位評価 → WeeklyReview構築(IS13 4.5節)。"""

from __future__ import annotations

from foundation.result import Result
from weekly_reviewer.fable_client import FableClient
from weekly_reviewer.models import (
    BusinessEvaluation,
    MvpEvaluation,
    TechnicalDebtFinding,
    WeeklyAnalysis,
    WeeklyReview,
    WeeklyReviewContext,
)

__all__ = ["evaluate_weekly_analysis", "build_weekly_review"]


def evaluate_weekly_analysis(
    weekly_analysis: WeeklyAnalysis,
    business_goal: str,
    context: WeeklyReviewContext,
    fable_client: FableClient,
) -> Result[WeeklyReview]:
    """設計書4.3節の優先順位(Business Goal > MVP > Architecture > Coding Style)に従い、
    Business Goal評価 → MVP評価 → Technical Debt評価 → 優先順位提案の順でfable_clientへ
    委譲し、WeeklyReviewを構築する。いずれかの評価呼び出しが失敗した場合は
    Result[WeeklyReview](success=False)を返し、後続評価は実行しない。
    """
    business_result = fable_client.review_business_alignment(business_goal, weekly_analysis)
    if not business_result.success:
        return Result(success=False, error=business_result.error)

    mvp_result = fable_client.review_mvp_fitness(weekly_analysis)
    if not mvp_result.success:
        return Result(success=False, error=mvp_result.error)

    technical_debt_result = fable_client.review_technical_debt(
        weekly_analysis, context.review_reports, context.technical_debt_reports
    )
    if not technical_debt_result.success:
        return Result(success=False, error=technical_debt_result.error)

    priorities_result = fable_client.recommend_priorities(
        weekly_analysis,
        business_result.value,
        mvp_result.value,
        technical_debt_result.value,
    )
    if not priorities_result.success:
        return Result(success=False, error=priorities_result.error)

    achievements, risks, recommendations, top_priority_next_week = priorities_result.value

    weekly_review = build_weekly_review(
        weekly_analysis,
        business_result.value,
        mvp_result.value,
        technical_debt_result.value,
        achievements,
        risks,
        recommendations,
        top_priority_next_week,
    )
    return Result(success=True, value=weekly_review)


def build_weekly_review(
    weekly_analysis: WeeklyAnalysis,
    business_evaluation: BusinessEvaluation,
    mvp_evaluation: MvpEvaluation,
    technical_debt: TechnicalDebtFinding,
    achievements: list[str],
    risks: list[str],
    recommendations: list[str],
    top_priority_next_week: list[str],
) -> WeeklyReview:
    """各評価結果からWeeklyReviewインスタンスを組み立てる(id/created_at/updated_atは
    foundation.utilsの既定生成を利用)。"""
    return WeeklyReview(
        project_id=weekly_analysis.project_id,
        review_period=weekly_analysis.review_period,
        merged_pull_requests=list(weekly_analysis.merged_pull_requests),
        business_evaluation=business_evaluation,
        mvp_evaluation=mvp_evaluation,
        technical_debt=technical_debt,
        achievements=list(achievements),
        risks=list(risks),
        recommendations=list(recommendations),
        top_priority_next_week=list(top_priority_next_week),
    )
