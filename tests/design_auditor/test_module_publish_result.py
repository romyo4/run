import unittest
from datetime import UTC, datetime
from typing import Any

from design_auditor.module import DesignAuditor
from design_auditor.types import (
    ApprovedDesign,
    AuditCategory,
    AuditIssue,
    AuditReport,
    AuditResultStatus,
    ReworkRequest,
)
from foundation.interfaces import ConfigurationClient
from foundation.result import Result


class FakeConfigurationClient(ConfigurationClient):
    @staticmethod
    def get(module_name: str, key: str) -> Result[Any]:
        return Result(success=True, value=True)


def _make_report(
    result: AuditResultStatus,
    *,
    warnings: list[AuditIssue] | None = None,
    violations: list[AuditIssue] | None = None,
    recommendations: list[str] | None = None,
) -> AuditReport:
    now = datetime.now(UTC)
    return AuditReport(
        id="audit-1",
        created_at=now,
        updated_at=now,
        metadata={},
        workflow_id="wf-001",
        design_id="design-1",
        result=result,
        warnings=warnings or [],
        violations=violations or [],
        recommendations=recommendations or [],
    )


class PublishResultPassTest(unittest.TestCase):
    def test_publish_result_returns_approved_design_when_result_is_pass(self) -> None:
        auditor = DesignAuditor(FakeConfigurationClient())
        report = _make_report(AuditResultStatus.PASS)

        result = auditor.publish_result(report)

        self.assertTrue(result.success)
        self.assertIsInstance(result.value, ApprovedDesign)
        self.assertEqual(result.value.comments, [])


class PublishResultPassWithCommentTest(unittest.TestCase):
    def test_publish_result_returns_approved_design_with_comments_when_pass_with_comment(
        self,
    ) -> None:
        auditor = DesignAuditor(FakeConfigurationClient())
        warnings = [AuditIssue(category=AuditCategory.REUSABILITY, message="再利用性が低い")]
        report = _make_report(AuditResultStatus.PASS_WITH_COMMENT, warnings=warnings)

        result = auditor.publish_result(report)

        self.assertTrue(result.success)
        self.assertIsInstance(result.value, ApprovedDesign)
        self.assertEqual(result.value.comments, ["再利用性が低い"])


class PublishResultReworkRequiredTest(unittest.TestCase):
    def test_publish_result_returns_rework_request_when_rework_required(self) -> None:
        auditor = DesignAuditor(FakeConfigurationClient())
        violations = [AuditIssue(category=AuditCategory.MODULE_BOUNDARY, message="境界違反")]
        report = _make_report(AuditResultStatus.REWORK_REQUIRED, violations=violations)

        result = auditor.publish_result(report)

        self.assertTrue(result.success)
        self.assertIsInstance(result.value, ReworkRequest)
        self.assertEqual(result.value.reasons, ["境界違反"])


class PublishResultRejectTest(unittest.TestCase):
    def test_publish_result_returns_rework_request_when_reject(self) -> None:
        auditor = DesignAuditor(FakeConfigurationClient())
        violations = [
            AuditIssue(
                category=AuditCategory.MVP_FITNESS,
                message="MVP対象外機能 'AI設計生成' が検出された",
            )
        ]
        report = _make_report(AuditResultStatus.REJECT, violations=violations)

        result = auditor.publish_result(report)

        self.assertTrue(result.success)
        self.assertIsInstance(result.value, ReworkRequest)


class PublishResultReturnedToTest(unittest.TestCase):
    def test_publish_result_rework_request_returned_to_is_architect(self) -> None:
        auditor = DesignAuditor(FakeConfigurationClient())
        report = _make_report(AuditResultStatus.REWORK_REQUIRED)

        result = auditor.publish_result(report)

        self.assertTrue(result.success)
        self.assertEqual(result.value.returned_to, "architect")


if __name__ == "__main__":
    unittest.main()
