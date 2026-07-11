import unittest
from datetime import date

from weekly_reviewer.models import (
    BusinessAlignmentStatus,
    BusinessEvaluation,
    MvpEvaluation,
    ReviewPeriod,
    TechnicalDebtFinding,
    WeeklyReview,
)
from weekly_reviewer.reporter import render_summary_text, render_weekly_report


def _full_weekly_review() -> WeeklyReview:
    return WeeklyReview(
        project_id="proj-1",
        review_period=ReviewPeriod(start_date=date(2026, 7, 5), end_date=date(2026, 7, 11)),
        merged_pull_requests=[],
        business_evaluation=BusinessEvaluation(
            business_goal="LINE登録数最大化",
            alignment_status=BusinessAlignmentStatus.ALIGNED,
            findings=["登録導線に寄与するPRが中心"],
        ),
        mvp_evaluation=MvpEvaluation(unnecessary_features=["管理画面のCSVエクスポート"]),
        technical_debt=TechnicalDebtFinding(naming_issues=["変数名が曖昧"]),
        achievements=["達成1", "達成2"],
        risks=["リスク1"],
        recommendations=["改善案1"],
        top_priority_next_week=["最優先1", "最優先2", "最優先3"],
    )


class RenderWeeklyReportTest(unittest.TestCase):
    def test_render_weekly_report_includes_all_nine_designated_sections(self) -> None:
        weekly_review = _full_weekly_review()
        result = render_weekly_report(weekly_review)

        self.assertTrue(result.success)
        report = result.value
        self.assertEqual(report.review_period, weekly_review.review_period)
        self.assertEqual(report.merged_pull_requests, weekly_review.merged_pull_requests)
        self.assertEqual(report.business_evaluation, weekly_review.business_evaluation)
        self.assertEqual(report.mvp_evaluation, weekly_review.mvp_evaluation)
        self.assertEqual(report.technical_debt, weekly_review.technical_debt)
        self.assertEqual(report.achievements, weekly_review.achievements)
        self.assertEqual(report.risks, weekly_review.risks)
        self.assertEqual(report.recommendations, weekly_review.recommendations)
        self.assertEqual(report.top_priority_next_week, weekly_review.top_priority_next_week)

    def test_render_weekly_report_preserves_top_priority_next_week_order(self) -> None:
        weekly_review = _full_weekly_review()
        result = render_weekly_report(weekly_review)
        self.assertTrue(result.success)
        self.assertEqual(result.value.top_priority_next_week, ["最優先1", "最優先2", "最優先3"])

    def test_render_weekly_report_returns_failure_result_when_weekly_review_missing_business_evaluation(
        self,
    ) -> None:
        weekly_review = _full_weekly_review()
        weekly_review.business_evaluation = None

        result = render_weekly_report(weekly_review)

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)


class RenderSummaryTextTest(unittest.TestCase):
    def test_render_summary_text_excludes_secrets_and_credentials(self) -> None:
        weekly_review = _full_weekly_review()
        weekly_review.risks = [
            "token=abcdefghijklmnopqrstuvwxyz123456",
            "password: hunter2hunter2hunter2",
        ]

        summary_text = render_summary_text(weekly_review)

        self.assertNotIn("abcdefghijklmnopqrstuvwxyz123456", summary_text)
        self.assertNotIn("hunter2hunter2hunter2", summary_text)
        self.assertIn("REDACTED", summary_text)

    def test_render_summary_text_is_non_empty_string(self) -> None:
        weekly_review = _full_weekly_review()
        summary_text = render_summary_text(weekly_review)
        self.assertIsInstance(summary_text, str)
        self.assertTrue(len(summary_text) > 0)


if __name__ == "__main__":
    unittest.main()
