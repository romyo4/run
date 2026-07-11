import dataclasses
import unittest
from datetime import date

from weekly_reviewer.models import (
    MvpEvaluation,
    Project,
    ReviewPeriod,
    TechnicalDebtFinding,
    WeeklyReport,
    WeeklyReview,
)


class ProjectFrozenTest(unittest.TestCase):
    def test_project_is_frozen_value_object(self) -> None:
        project = Project(project_id="proj-1")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            project.project_id = "proj-2"  # type: ignore[misc]


class ReviewPeriodFrozenTest(unittest.TestCase):
    def test_review_period_is_frozen_value_object(self) -> None:
        review_period = ReviewPeriod(start_date=date(2026, 7, 1), end_date=date(2026, 7, 7))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            review_period.start_date = date(2026, 7, 2)  # type: ignore[misc]


class MvpEvaluationHasIssueTest(unittest.TestCase):
    def test_mvp_evaluation_has_issue_true_when_any_list_non_empty(self) -> None:
        evaluation = MvpEvaluation(unnecessary_features=["未使用のダッシュボード"])
        self.assertTrue(evaluation.has_issue)

    def test_mvp_evaluation_has_issue_false_when_all_lists_empty(self) -> None:
        evaluation = MvpEvaluation()
        self.assertFalse(evaluation.has_issue)


class TechnicalDebtFindingCountTest(unittest.TestCase):
    def test_technical_debt_finding_count_sums_all_categories(self) -> None:
        finding = TechnicalDebtFinding(
            duplicated_code=["a"],
            maintainability_concerns=["b", "c"],
            responsibility_violations=[],
            naming_issues=["d"],
            documentation_gaps=["e", "f", "g"],
        )
        self.assertEqual(finding.count, 7)


class WeeklyReviewTest(unittest.TestCase):
    def test_weekly_review_inherits_review_common_fields(self) -> None:
        review = WeeklyReview(project_id="proj-1")
        self.assertTrue(hasattr(review, "id"))
        self.assertTrue(hasattr(review, "created_at"))
        self.assertTrue(hasattr(review, "updated_at"))
        self.assertTrue(hasattr(review, "metadata"))

    def test_weekly_review_default_fields_are_generated(self) -> None:
        review_a = WeeklyReview()
        review_b = WeeklyReview()
        self.assertNotEqual(review_a.id, review_b.id)
        self.assertEqual(review_a.project_id, "")
        self.assertEqual(review_a.merged_pull_requests, [])
        self.assertEqual(review_a.achievements, [])


class WeeklyReportTest(unittest.TestCase):
    def test_weekly_report_fields_match_designated_nine_items(self) -> None:
        review_period = ReviewPeriod(start_date=date(2026, 7, 1), end_date=date(2026, 7, 7))
        report = WeeklyReport(
            id="report-1",
            project_id="proj-1",
            review_period=review_period,
            merged_pull_requests=[],
            business_evaluation=None,
            mvp_evaluation=None,
            technical_debt=None,
            achievements=["achieved-1"],
            risks=["risk-1"],
            recommendations=["recommendation-1"],
            top_priority_next_week=["priority-1"],
            summary_text="summary",
            created_at=None,
            updated_at=None,
        )
        designated_nine_items = (
            "review_period",
            "merged_pull_requests",
            "business_evaluation",
            "mvp_evaluation",
            "technical_debt",
            "achievements",
            "risks",
            "recommendations",
            "top_priority_next_week",
        )
        for field_name in designated_nine_items:
            self.assertTrue(hasattr(report, field_name))


if __name__ == "__main__":
    unittest.main()
