import unittest
from typing import Any

from design_auditor.module import DesignAuditor
from design_auditor.types import AuditReport, AuditResultStatus
from foundation.errors import NotFoundError, ValidationError
from foundation.interfaces import ConfigurationClient
from foundation.result import Result
from foundation.types import Design


class FakeConfigurationClient(ConfigurationClient):
    @staticmethod
    def get(module_name: str, key: str) -> Result[Any]:
        return Result(success=True, value=True)


class _LockedDesign(Design):
    """audit()がDesign Documentを一切変更しないことを検証するための変異検知Spy。"""

    def __setattr__(self, name: str, value: Any) -> None:
        if name != "_locked" and object.__getattribute__(self, "__dict__").get("_locked"):
            raise AssertionError(f"DesignAuditor.audit() must not mutate Design.{name}")
        object.__setattr__(self, name, value)


def _lock(instance: Any) -> Any:
    object.__setattr__(instance, "_locked", True)
    return instance


def _make_design(metadata: dict[str, Any] | None = None) -> Design:
    base_metadata: dict[str, Any] = {"workflow_id": "wf-001"}
    if metadata:
        base_metadata.update(metadata)
    return Design(metadata=base_metadata)


class AuditCleanDesignTest(unittest.TestCase):
    def test_audit_returns_pass_for_clean_design_document(self) -> None:
        auditor = DesignAuditor(FakeConfigurationClient())
        design = _make_design()

        result = auditor.audit(design)

        self.assertTrue(result.success)
        self.assertIsInstance(result.value, AuditReport)
        self.assertEqual(result.value.result, AuditResultStatus.PASS)


class AuditReworkRequiredTest(unittest.TestCase):
    def test_audit_returns_rework_required_when_architecture_violation_found(self) -> None:
        auditor = DesignAuditor(FakeConfigurationClient())
        design = _make_design(
            {
                "architecture_notes": {
                    "module_boundary": ["他モジュールの内部実装に直接依存している"],
                }
            }
        )

        result = auditor.audit(design)

        self.assertTrue(result.success)
        self.assertEqual(result.value.result, AuditResultStatus.REWORK_REQUIRED)


class AuditRejectTest(unittest.TestCase):
    def test_audit_returns_reject_when_mvp_excluded_feature_found(self) -> None:
        auditor = DesignAuditor(FakeConfigurationClient())
        design = _make_design({"features": ["AI設計生成"]})

        result = auditor.audit(design)

        self.assertTrue(result.success)
        self.assertEqual(result.value.result, AuditResultStatus.REJECT)


class AuditReportIdsTest(unittest.TestCase):
    def test_audit_report_contains_workflow_id_and_design_id(self) -> None:
        auditor = DesignAuditor(FakeConfigurationClient())
        design = _make_design()

        result = auditor.audit(design)

        self.assertTrue(result.success)
        self.assertEqual(result.value.workflow_id, "wf-001")
        self.assertEqual(result.value.design_id, design.id)


class AuditInputValidationTest(unittest.TestCase):
    def test_audit_returns_validation_error_when_design_document_is_none(self) -> None:
        auditor = DesignAuditor(FakeConfigurationClient())

        result = auditor.audit(None)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, ValidationError)

    def test_audit_returns_not_found_error_when_workflow_id_missing_in_metadata(
        self,
    ) -> None:
        auditor = DesignAuditor(FakeConfigurationClient())
        design = Design(metadata={})

        result = auditor.audit(design)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, NotFoundError)


class AuditDoesNotMutateTest(unittest.TestCase):
    def test_audit_does_not_mutate_design_document(self) -> None:
        auditor = DesignAuditor(FakeConfigurationClient())
        design = _LockedDesign(metadata={"workflow_id": "wf-001"})
        _lock(design)

        result = auditor.audit(design)

        self.assertTrue(result.success)

    def test_audit_does_not_generate_or_modify_design_content(self) -> None:
        """4.1/4.2: Auditorは設計・修正を行わない。戻り値はAuditReportのみであり、
        design_documentの属性を変更しない。"""
        auditor = DesignAuditor(FakeConfigurationClient())
        design = _LockedDesign(metadata={"workflow_id": "wf-001", "features": ["要件充足確認"]})
        original_metadata = dict(design.metadata)
        _lock(design)

        result = auditor.audit(design)

        self.assertTrue(result.success)
        self.assertIsInstance(result.value, AuditReport)
        self.assertEqual(design.metadata, original_metadata)


class AuditLoggingTest(unittest.TestCase):
    def test_audit_logs_expected_fields_on_success(self) -> None:
        auditor = DesignAuditor(FakeConfigurationClient())
        design = _make_design()

        with self.assertLogs("design_auditor", level="INFO") as captured:
            result = auditor.audit(design)

        self.assertTrue(result.success)
        joined = " ".join(captured.output)
        self.assertIn("workflow_id=wf-001", joined)
        self.assertIn(f"design_id={design.id}", joined)
        self.assertIn("audit_result=PASS", joined)
        self.assertIn("finding_count=0", joined)
        self.assertIn("warning_count=0", joined)
        self.assertIn("result=success", joined)


if __name__ == "__main__":
    unittest.main()
