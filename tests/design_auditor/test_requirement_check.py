import unittest

from design_auditor.requirement_check import check_requirements
from design_auditor.types import AuditCategory
from foundation.types import Design


class CheckRequirementsTest(unittest.TestCase):
    def test_check_requirements_returns_empty_when_design_covers_all_requirements(
        self,
    ) -> None:
        design = Design(
            metadata={
                "requirements": ["要件A", "要件B"],
                "requirements_covered": ["要件A", "要件B"],
            }
        )

        findings = check_requirements(design)

        self.assertEqual(findings, [])

    def test_check_requirements_returns_finding_when_requirement_missing(self) -> None:
        design = Design(
            metadata={
                "requirements": ["要件A", "要件B"],
                "requirements_covered": ["要件A"],
            }
        )

        findings = check_requirements(design)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, AuditCategory.REQUIREMENT_FULFILLMENT)
        self.assertIn("要件B", findings[0].message)


if __name__ == "__main__":
    unittest.main()
