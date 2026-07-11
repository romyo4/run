import unittest

from design_auditor.architecture_check import check_architecture
from design_auditor.types import AuditCategory
from foundation.types import Design


class CheckArchitectureTest(unittest.TestCase):
    def test_check_architecture_passes_when_responsibility_separated(self) -> None:
        design = Design(metadata={"architecture_notes": {}})

        result = check_architecture(design)

        self.assertTrue(result.valid)
        self.assertEqual(result.violations, [])

    def test_check_architecture_detects_responsibility_separation_violation(self) -> None:
        design = Design(
            metadata={
                "architecture_notes": {
                    "responsibility_separation": ["Executorの責務が混在している"],
                }
            }
        )

        result = check_architecture(design)

        self.assertFalse(result.valid)
        self.assertEqual(len(result.violations), 1)
        self.assertEqual(result.violations[0].category, AuditCategory.RESPONSIBILITY_SEPARATION)

    def test_check_architecture_detects_module_boundary_violation(self) -> None:
        design = Design(
            metadata={
                "architecture_notes": {
                    "module_boundary": ["他モジュールの内部実装に直接依存している"],
                }
            }
        )

        result = check_architecture(design)

        self.assertFalse(result.valid)
        self.assertEqual(len(result.violations), 1)
        self.assertEqual(result.violations[0].category, AuditCategory.MODULE_BOUNDARY)

    def test_check_architecture_detects_interface_inconsistency(self) -> None:
        design = Design(
            metadata={
                "architecture_notes": {
                    "interface_consistency": ["Result[T]を使用していない"],
                }
            }
        )

        result = check_architecture(design)

        self.assertFalse(result.valid)
        self.assertEqual(len(result.violations), 1)
        self.assertEqual(result.violations[0].category, AuditCategory.INTERFACE_CONSISTENCY)

    def test_check_architecture_detects_domain_inconsistency(self) -> None:
        design = Design(
            metadata={
                "architecture_notes": {
                    "domain_consistency": ["独自のDomainモデルを新規定義している"],
                }
            }
        )

        result = check_architecture(design)

        self.assertFalse(result.valid)
        self.assertEqual(len(result.violations), 1)
        self.assertEqual(result.violations[0].category, AuditCategory.DOMAIN_CONSISTENCY)

    def test_check_architecture_detects_configuration_inconsistency(self) -> None:
        design = Design(
            metadata={
                "architecture_notes": {
                    "configuration_consistency": ["F03を経由せず設定値を直接参照している"],
                }
            }
        )

        result = check_architecture(design)

        self.assertFalse(result.valid)
        self.assertEqual(len(result.violations), 1)
        self.assertEqual(result.violations[0].category, AuditCategory.CONFIGURATION_CONSISTENCY)


if __name__ == "__main__":
    unittest.main()
