import unittest

from design_auditor.aggregation import aggregate_result
from design_auditor.types import AuditCategory, AuditIssue, AuditResultStatus


class AggregateResultTest(unittest.TestCase):
    def test_aggregate_result_returns_pass_when_no_findings(self) -> None:
        result = aggregate_result(findings=[], warnings=[], violations=[])

        self.assertEqual(result, AuditResultStatus.PASS)

    def test_aggregate_result_returns_pass_with_comment_when_only_warnings(self) -> None:
        warnings = [AuditIssue(category=AuditCategory.REUSABILITY, message="再利用性が低い")]

        result = aggregate_result(findings=[], warnings=warnings, violations=[])

        self.assertEqual(result, AuditResultStatus.PASS_WITH_COMMENT)

    def test_aggregate_result_returns_rework_required_when_violation_present(self) -> None:
        violations = [AuditIssue(category=AuditCategory.MODULE_BOUNDARY, message="モジュール境界違反")]

        result = aggregate_result(findings=[], warnings=[], violations=violations)

        self.assertEqual(result, AuditResultStatus.REWORK_REQUIRED)

    def test_aggregate_result_returns_reject_when_mvp_excluded_feature_violation_present(
        self,
    ) -> None:
        violations = [
            AuditIssue(
                category=AuditCategory.MVP_FITNESS,
                message="MVP対象外機能 'AI設計生成' が検出された",
            )
        ]

        result = aggregate_result(findings=[], warnings=[], violations=violations)

        self.assertEqual(result, AuditResultStatus.REJECT)


if __name__ == "__main__":
    unittest.main()
