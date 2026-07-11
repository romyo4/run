import unittest
from typing import Any

from design_auditor.module import DesignAuditor
from design_auditor.types import MVPAssessment
from foundation.interfaces import ConfigurationClient
from foundation.result import Result
from foundation.types import Design


class FakeConfigurationClient(ConfigurationClient):
    @staticmethod
    def get(module_name: str, key: str) -> Result[Any]:
        return Result(success=True, value=True)


def _make_design(metadata: dict[str, Any] | None = None) -> Design:
    base_metadata: dict[str, Any] = {"workflow_id": "wf-001"}
    if metadata:
        base_metadata.update(metadata)
    return Design(metadata=base_metadata)


class CheckMvpCompliantTest(unittest.TestCase):
    def test_check_mvp_returns_compliant_true_when_no_excluded_feature(self) -> None:
        auditor = DesignAuditor(FakeConfigurationClient())
        design = _make_design({"features": ["要件充足確認"]})

        result = auditor.check_mvp(design)

        self.assertTrue(result.success)
        self.assertIsInstance(result.value, MVPAssessment)
        self.assertTrue(result.value.compliant)
        self.assertEqual(result.value.excluded_features_detected, [])


class CheckMvpNonCompliantTest(unittest.TestCase):
    def test_check_mvp_returns_compliant_false_and_lists_detected_features(self) -> None:
        auditor = DesignAuditor(FakeConfigurationClient())
        design = _make_design({"features": ["自動修正", "UML生成"]})

        result = auditor.check_mvp(design)

        self.assertTrue(result.success)
        self.assertFalse(result.value.compliant)
        self.assertIn("自動修正", result.value.excluded_features_detected)
        self.assertIn("UML生成", result.value.excluded_features_detected)


if __name__ == "__main__":
    unittest.main()
