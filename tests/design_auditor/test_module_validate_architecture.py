import unittest
from typing import Any

from design_auditor.module import DesignAuditor
from design_auditor.types import AuditCategory, ValidationResult
from foundation.interfaces import ConfigurationClient
from foundation.result import Result
from foundation.types import Design

_ARCHITECTURE_CATEGORIES = {
    AuditCategory.RESPONSIBILITY_SEPARATION,
    AuditCategory.MODULE_BOUNDARY,
    AuditCategory.INTERFACE_CONSISTENCY,
    AuditCategory.DOMAIN_CONSISTENCY,
    AuditCategory.CONFIGURATION_CONSISTENCY,
}


class FakeConfigurationClient(ConfigurationClient):
    @staticmethod
    def get(module_name: str, key: str) -> Result[Any]:
        return Result(success=True, value=True)


def _make_design(metadata: dict[str, Any] | None = None) -> Design:
    base_metadata: dict[str, Any] = {"workflow_id": "wf-001"}
    if metadata:
        base_metadata.update(metadata)
    return Design(metadata=base_metadata)


class ValidateArchitectureNoViolationsTest(unittest.TestCase):
    def test_validate_architecture_returns_valid_true_when_no_violations(self) -> None:
        auditor = DesignAuditor(FakeConfigurationClient())
        design = _make_design()

        result = auditor.validate_architecture(design)

        self.assertTrue(result.success)
        self.assertIsInstance(result.value, ValidationResult)
        self.assertTrue(result.value.valid)
        self.assertEqual(result.value.violations, [])


class ValidateArchitectureViolationsTest(unittest.TestCase):
    def test_validate_architecture_returns_valid_false_when_violations_present(
        self,
    ) -> None:
        auditor = DesignAuditor(FakeConfigurationClient())
        design = _make_design(
            {
                "architecture_notes": {
                    "interface_consistency": ["Result[T]を使用していない"],
                }
            }
        )

        result = auditor.validate_architecture(design)

        self.assertTrue(result.success)
        self.assertFalse(result.value.valid)
        self.assertEqual(len(result.value.violations), 1)


class ValidateArchitectureCategoryScopeTest(unittest.TestCase):
    def test_validate_architecture_only_covers_architecture_categories(self) -> None:
        auditor = DesignAuditor(FakeConfigurationClient())
        design = _make_design(
            {
                "architecture_notes": {
                    "responsibility_separation": ["責務混在"],
                    "module_boundary": ["境界違反"],
                    "interface_consistency": ["Interface不整合"],
                    "domain_consistency": ["Domain不整合"],
                    "configuration_consistency": ["Configuration不整合"],
                },
                # MVP適合性/品質観点はvalidate_architecture()の対象外であるべき
                "features": ["AI設計生成"],
                "quality_notes": {"over_engineering": ["過剰設計"]},
            }
        )

        result = auditor.validate_architecture(design)

        self.assertTrue(result.success)
        categories = {issue.category for issue in result.value.violations}
        self.assertTrue(categories.issubset(_ARCHITECTURE_CATEGORIES))
        self.assertEqual(len(result.value.violations), 5)


if __name__ == "__main__":
    unittest.main()
