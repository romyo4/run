import unittest

from design_auditor.mvp_check import check_mvp_fitness
from foundation.types import Design


class CheckMvpFitnessTest(unittest.TestCase):
    def test_check_mvp_fitness_compliant_when_no_excluded_feature_present(self) -> None:
        design = Design(
            metadata={
                "features": ["要件充足確認", "Architecture整合性確認"],
                "content": "設計書は要件充足とArchitecture整合性を確認する。",
            }
        )

        assessment = check_mvp_fitness(design)

        self.assertTrue(assessment.compliant)
        self.assertEqual(assessment.excluded_features_detected, [])

    def test_check_mvp_fitness_detects_ai_design_generation_feature(self) -> None:
        design = Design(metadata={"features": ["AI設計生成"]})

        assessment = check_mvp_fitness(design)

        self.assertFalse(assessment.compliant)
        self.assertIn("AI設計生成", assessment.excluded_features_detected)

    def test_check_mvp_fitness_detects_auto_fix_feature(self) -> None:
        design = Design(metadata={"features": ["自動修正"]})

        assessment = check_mvp_fitness(design)

        self.assertFalse(assessment.compliant)
        self.assertIn("自動修正", assessment.excluded_features_detected)

    def test_check_mvp_fitness_detects_uml_generation_feature(self) -> None:
        design = Design(metadata={"features": ["UML生成"]})

        assessment = check_mvp_fitness(design)

        self.assertFalse(assessment.compliant)
        self.assertIn("UML生成", assessment.excluded_features_detected)

    def test_check_mvp_fitness_detects_cost_optimization_feature(self) -> None:
        design = Design(metadata={"features": ["コスト最適化"]})

        assessment = check_mvp_fitness(design)

        self.assertFalse(assessment.compliant)
        self.assertIn("コスト最適化", assessment.excluded_features_detected)

    def test_check_mvp_fitness_detects_performance_analysis_feature(self) -> None:
        design = Design(metadata={"features": ["パフォーマンス解析"]})

        assessment = check_mvp_fitness(design)

        self.assertFalse(assessment.compliant)
        self.assertIn("パフォーマンス解析", assessment.excluded_features_detected)

    def test_check_mvp_fitness_detects_security_auto_fix_feature(self) -> None:
        design = Design(metadata={"features": ["セキュリティ自動修正"]})

        assessment = check_mvp_fitness(design)

        self.assertFalse(assessment.compliant)
        self.assertIn("セキュリティ自動修正", assessment.excluded_features_detected)

    def test_check_mvp_fitness_detects_enterprise_design_governance_feature(self) -> None:
        design = Design(metadata={"content": "Enterprise Design Governanceを提供する"})

        assessment = check_mvp_fitness(design)

        self.assertFalse(assessment.compliant)
        self.assertIn("Enterprise Design Governance", assessment.excluded_features_detected)


if __name__ == "__main__":
    unittest.main()
