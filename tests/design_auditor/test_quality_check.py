import unittest

from design_auditor.quality_check import check_quality
from design_auditor.types import AuditCategory
from foundation.types import Design


class CheckQualityTest(unittest.TestCase):
    def test_check_quality_passes_when_reusable_and_not_over_engineered(self) -> None:
        design = Design(metadata={"quality_notes": {}})

        issues = check_quality(design)

        self.assertEqual(issues, [])

    def test_check_quality_detects_low_reusability(self) -> None:
        design = Design(
            metadata={
                "quality_notes": {
                    "reusability": ["共通ロジックが重複実装されている"],
                }
            }
        )

        issues = check_quality(design)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].category, AuditCategory.REUSABILITY)

    def test_check_quality_detects_over_engineering(self) -> None:
        design = Design(
            metadata={
                "quality_notes": {
                    "over_engineering": ["MVPに不要な抽象化レイヤーが追加されている"],
                }
            }
        )

        issues = check_quality(design)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].category, AuditCategory.OVER_ENGINEERING)


if __name__ == "__main__":
    unittest.main()
