import unittest

from foundation.types import Implementation, PullRequest
from reviewer.checks import (
    check_business_alignment,
    check_design_alignment,
    check_documentation,
    check_maintainability,
    check_mvp_compliance,
    check_requirements,
    check_technical_debt,
    determine_decision,
)
from reviewer.domain import (
    BusinessEvaluation,
    IssueCategory,
    MVPAssessment,
    ReviewDecision,
    ReviewIssue,
    Severity,
)


class CheckRequirementsTest(unittest.TestCase):
    def test_check_requirements_returns_issue_when_requirement_unmet(self) -> None:
        test_report = {"unmet_requirements": ["ユーザー登録APIが未実装"]}
        issues = check_requirements(design_document={}, implementation_result=Implementation(), test_report=test_report)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].category, IssueCategory.REQUIREMENT)
        self.assertEqual(issues[0].severity, Severity.BLOCKER)

    def test_check_requirements_returns_empty_list_when_satisfied(self) -> None:
        test_report = {"unmet_requirements": []}
        issues = check_requirements(design_document={}, implementation_result=Implementation(), test_report=test_report)
        self.assertEqual(issues, [])


class CheckDesignAlignmentTest(unittest.TestCase):
    def test_check_design_alignment_returns_issue_when_design_deviation_detected(self) -> None:
        implementation_result = Implementation(metadata={"design_deviations": ["APIレスポンス形式がDesignと異なる"]})
        issues = check_design_alignment(design_document={}, implementation_result=implementation_result)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].category, IssueCategory.DESIGN)
        self.assertEqual(issues[0].severity, Severity.MAJOR)


class CheckMvpComplianceTest(unittest.TestCase):
    def test_check_mvp_compliance_flags_unnecessary_abstraction(self) -> None:
        implementation_result = Implementation(metadata={"unnecessary_abstractions": ["AbstractFactory"]})
        assessment = check_mvp_compliance(implementation_result)
        self.assertFalse(assessment.is_mvp_compliant)
        self.assertEqual(assessment.unnecessary_abstractions, ["AbstractFactory"])

    def test_check_mvp_compliance_flags_unnecessary_feature(self) -> None:
        implementation_result = Implementation(metadata={"unnecessary_features": ["未使用のダッシュボード機能"]})
        assessment = check_mvp_compliance(implementation_result)
        self.assertFalse(assessment.is_mvp_compliant)
        self.assertEqual(assessment.unnecessary_features, ["未使用のダッシュボード機能"])

    def test_check_mvp_compliance_flags_over_engineering(self) -> None:
        implementation_result = Implementation(metadata={"over_engineering_flags": ["プラグイン機構を先取りで実装"]})
        assessment = check_mvp_compliance(implementation_result)
        self.assertFalse(assessment.is_mvp_compliant)
        self.assertEqual(assessment.over_engineering_flags, ["プラグイン機構を先取りで実装"])

    def test_check_mvp_compliance_is_compliant_when_no_violation(self) -> None:
        implementation_result = Implementation(metadata={})
        assessment = check_mvp_compliance(implementation_result)
        self.assertTrue(assessment.is_mvp_compliant)
        self.assertEqual(assessment.unnecessary_abstractions, [])
        self.assertEqual(assessment.unnecessary_features, [])
        self.assertEqual(assessment.over_engineering_flags, [])


class CheckBusinessAlignmentTest(unittest.TestCase):
    def test_check_business_alignment_computes_business_score(self) -> None:
        pull_request = PullRequest(metadata={"summary": "課金プランのアップグレード機能を追加"})
        business_goal = {"required_keywords": ["課金", "アップグレード"]}
        evaluation = check_business_alignment(pull_request, business_goal)
        self.assertEqual(evaluation.business_score, 1.0)
        self.assertTrue(evaluation.aligned_with_business_goal)

    def test_check_business_alignment_marks_not_aligned_when_goal_mismatch(self) -> None:
        pull_request = PullRequest(metadata={"summary": "社内ツールのログ表示を修正"})
        business_goal = {"required_keywords": ["課金", "アップグレード"]}
        evaluation = check_business_alignment(pull_request, business_goal)
        self.assertEqual(evaluation.business_score, 0.0)
        self.assertFalse(evaluation.aligned_with_business_goal)


class CheckTechnicalDebtTest(unittest.TestCase):
    def test_check_technical_debt_returns_items_with_severity(self) -> None:
        audit_report = {
            "technical_debt_items": [
                {
                    "description": "テストが不足している",
                    "location": "src/module/bar.py",
                    "severity": "major",
                }
            ]
        }
        items = check_technical_debt(implementation_result=Implementation(), audit_report=audit_report)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].severity, Severity.MAJOR)
        self.assertEqual(items[0].location, "src/module/bar.py")


class CheckMaintainabilityTest(unittest.TestCase):
    def test_check_maintainability_returns_issue_when_maintainability_reduced(self) -> None:
        implementation_result = Implementation(
            metadata={"maintainability_reduced": True, "maintainability_notes": "巨大な関数"}
        )
        issues = check_maintainability(implementation_result)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].category, IssueCategory.MAINTAINABILITY)


class CheckDocumentationTest(unittest.TestCase):
    def test_check_documentation_returns_issue_when_docs_not_updated(self) -> None:
        pull_request = PullRequest(metadata={"documentation_updated": False})
        issues = check_documentation(pull_request)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].category, IssueCategory.DOCUMENTATION)
        self.assertEqual(issues[0].severity, Severity.MINOR)


class DetermineDecisionTest(unittest.TestCase):
    def test_determine_decision_returns_approved_when_no_issues_and_mvp_compliant(self) -> None:
        decision = determine_decision(
            issues=[],
            mvp_assessment=MVPAssessment(is_mvp_compliant=True),
            business_evaluation=BusinessEvaluation(aligned_with_business_goal=True, business_score=1.0),
            technical_debt=[],
        )
        self.assertEqual(decision, ReviewDecision.APPROVED)

    def test_determine_decision_returns_approved_with_comment_for_minor_issue_only(self) -> None:
        decision = determine_decision(
            issues=[
                ReviewIssue(
                    category=IssueCategory.DOCUMENTATION,
                    description="README未更新",
                    severity=Severity.MINOR,
                )
            ],
            mvp_assessment=MVPAssessment(is_mvp_compliant=True),
            business_evaluation=BusinessEvaluation(aligned_with_business_goal=True, business_score=1.0),
            technical_debt=[],
        )
        self.assertEqual(decision, ReviewDecision.APPROVED_WITH_COMMENT)

    def test_determine_decision_returns_changes_requested_when_mvp_not_compliant(self) -> None:
        decision = determine_decision(
            issues=[],
            mvp_assessment=MVPAssessment(is_mvp_compliant=False, unnecessary_abstractions=["Factory"]),
            business_evaluation=BusinessEvaluation(aligned_with_business_goal=True, business_score=1.0),
            technical_debt=[],
        )
        self.assertEqual(decision, ReviewDecision.CHANGES_REQUESTED)

    def test_determine_decision_returns_rejected_when_blocker_issue_present(self) -> None:
        decision = determine_decision(
            issues=[
                ReviewIssue(
                    category=IssueCategory.REQUIREMENT,
                    description="必須要件が未実装",
                    severity=Severity.BLOCKER,
                )
            ],
            mvp_assessment=MVPAssessment(is_mvp_compliant=True),
            business_evaluation=BusinessEvaluation(aligned_with_business_goal=True, business_score=1.0),
            technical_debt=[],
        )
        self.assertEqual(decision, ReviewDecision.REJECTED)

    def test_determine_decision_prioritizes_business_goal_over_style_preference(self) -> None:
        decision = determine_decision(
            issues=[
                ReviewIssue(
                    category=IssueCategory.MAINTAINABILITY,
                    description="命名規則の個人的な好みの違い",
                    severity=Severity.MINOR,
                )
            ],
            mvp_assessment=MVPAssessment(is_mvp_compliant=True),
            business_evaluation=BusinessEvaluation(aligned_with_business_goal=False, business_score=0.1),
            technical_debt=[],
        )
        # 軽微なスタイル上の指摘のみであればAPPROVED_WITH_COMMENTとなるはずだが、
        # Business Goalとの不整合はスタイルの好みより優先されるためCHANGES_REQUESTEDとなる。
        self.assertEqual(decision, ReviewDecision.CHANGES_REQUESTED)


if __name__ == "__main__":
    unittest.main()
