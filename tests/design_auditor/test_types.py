import dataclasses
import unittest
from datetime import UTC, datetime

from design_auditor.types import (
    ApprovedDesign,
    AuditCategory,
    AuditIssue,
    AuditReport,
    AuditResultStatus,
    PublishOutcome,
    ReworkRequest,
)


class AuditIssueImmutabilityTest(unittest.TestCase):
    def test_audit_issue_is_immutable(self) -> None:
        issue = AuditIssue(
            category=AuditCategory.REQUIREMENT_FULFILLMENT,
            message="要件が未充足",
        )
        with self.assertRaises(dataclasses.FrozenInstanceError):
            issue.message = "変更後"  # type: ignore[misc]


class AuditReportDefaultListsTest(unittest.TestCase):
    def test_audit_report_default_lists_are_independent_instances(self) -> None:
        now = datetime.now(UTC)
        report_a = AuditReport(
            id="audit-a",
            created_at=now,
            updated_at=now,
            metadata={},
            workflow_id="wf-1",
            design_id="design-1",
            result=AuditResultStatus.PASS,
        )
        report_b = AuditReport(
            id="audit-b",
            created_at=now,
            updated_at=now,
            metadata={},
            workflow_id="wf-2",
            design_id="design-2",
            result=AuditResultStatus.PASS,
        )

        report_a.findings.append(AuditIssue(category=AuditCategory.REQUIREMENT_FULFILLMENT, message="x"))
        report_a.warnings.append(AuditIssue(category=AuditCategory.REUSABILITY, message="y"))
        report_a.violations.append(AuditIssue(category=AuditCategory.MODULE_BOUNDARY, message="z"))
        report_a.recommendations.append("推奨事項")

        self.assertEqual(report_b.findings, [])
        self.assertEqual(report_b.warnings, [])
        self.assertEqual(report_b.violations, [])
        self.assertEqual(report_b.recommendations, [])


class PublishOutcomeTypeTest(unittest.TestCase):
    def test_publish_outcome_accepts_approved_design(self) -> None:
        approved = ApprovedDesign(
            design_id="design-1",
            audit_id="audit-1",
            approved_at=datetime.now(UTC),
        )
        self.assertIsInstance(approved, PublishOutcome)

    def test_publish_outcome_accepts_rework_request(self) -> None:
        rework = ReworkRequest(design_id="design-1", audit_id="audit-1")
        self.assertIsInstance(rework, PublishOutcome)


if __name__ == "__main__":
    unittest.main()
