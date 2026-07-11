import unittest

from reviewer.domain import (
    BusinessEvaluation,
    IssueCategory,
    MVPAssessment,
    ReviewDecision,
    ReviewIssue,
    ReviewReport,
    Severity,
    TechnicalDebtItem,
)


class ReviewDecisionTest(unittest.TestCase):
    def test_review_decision_enum_has_four_values(self) -> None:
        self.assertEqual(
            {member.value for member in ReviewDecision},
            {"APPROVED", "APPROVED_WITH_COMMENT", "CHANGES_REQUESTED", "REJECTED"},
        )


class ReviewReportTest(unittest.TestCase):
    def test_review_report_default_result_is_changes_requested(self) -> None:
        report = ReviewReport()
        self.assertEqual(report.result, ReviewDecision.CHANGES_REQUESTED)

    def test_review_report_inherits_review_common_attributes(self) -> None:
        report = ReviewReport()
        self.assertTrue(hasattr(report, "id"))
        self.assertTrue(hasattr(report, "created_at"))
        self.assertTrue(hasattr(report, "updated_at"))
        self.assertTrue(hasattr(report, "metadata"))
        self.assertIsInstance(report.metadata, dict)


class ReviewIssueTest(unittest.TestCase):
    def test_review_issue_creation_with_category_and_severity(self) -> None:
        issue = ReviewIssue(
            category=IssueCategory.REQUIREMENT,
            description="requirement X is not implemented",
            severity=Severity.BLOCKER,
        )
        self.assertEqual(issue.category, IssueCategory.REQUIREMENT)
        self.assertEqual(issue.severity, Severity.BLOCKER)
        self.assertEqual(issue.description, "requirement X is not implemented")


class TechnicalDebtItemTest(unittest.TestCase):
    def test_technical_debt_item_creation(self) -> None:
        item = TechnicalDebtItem(
            description="duplicated logic",
            location="src/module/foo.py",
            severity=Severity.MINOR,
        )
        self.assertEqual(item.description, "duplicated logic")
        self.assertEqual(item.location, "src/module/foo.py")
        self.assertEqual(item.severity, Severity.MINOR)


class BusinessEvaluationTest(unittest.TestCase):
    def test_business_evaluation_creation(self) -> None:
        evaluation = BusinessEvaluation(
            aligned_with_business_goal=True,
            business_score=0.8,
            notes=["matches business goal"],
        )
        self.assertTrue(evaluation.aligned_with_business_goal)
        self.assertEqual(evaluation.business_score, 0.8)
        self.assertEqual(evaluation.notes, ["matches business goal"])


class MVPAssessmentTest(unittest.TestCase):
    def test_mvp_assessment_default_lists_are_independent_instances(self) -> None:
        first = MVPAssessment(is_mvp_compliant=True)
        second = MVPAssessment(is_mvp_compliant=True)
        first.unnecessary_abstractions.append("factory pattern")
        self.assertEqual(first.unnecessary_abstractions, ["factory pattern"])
        self.assertEqual(second.unnecessary_abstractions, [])
        self.assertIsNot(first.unnecessary_abstractions, second.unnecessary_abstractions)


if __name__ == "__main__":
    unittest.main()
