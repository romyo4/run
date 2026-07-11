import unittest
from types import SimpleNamespace

from pr_creator.errors import QualityGateNotPassedError
from pr_creator.quality_gate import ensure_passed, is_passed


def _test_report(status: str | None) -> SimpleNamespace:
    """`tester.models.TestReport`のダックタイピング用フェイク(`.quality_gate_result.status`のみ保持)。

    PR Creatorの`quality_gate.py`はTesterの内部型に直接依存しないため、テストでも
    Testerの実際のdataclassを構築せず、必要な属性のみを持つ最小限のフェイクを用いる。
    """
    quality_gate_result = SimpleNamespace(status=status) if status is not None else None
    return SimpleNamespace(quality_gate_result=quality_gate_result)


class QualityGateTestCase(unittest.TestCase):
    def test_is_passed_returns_true_when_status_is_pass(self) -> None:
        self.assertTrue(is_passed(_test_report("PASS")))

    def test_is_passed_returns_false_when_status_is_fail(self) -> None:
        self.assertFalse(is_passed(_test_report("FAIL")))

    def test_is_passed_returns_false_when_quality_gate_result_is_missing(self) -> None:
        report = SimpleNamespace()
        self.assertFalse(is_passed(report))

    def test_is_passed_returns_false_when_quality_gate_result_is_none(self) -> None:
        self.assertFalse(is_passed(_test_report(None)))

    def test_is_passed_does_not_recompute_individual_check_items(self) -> None:
        """PR CreatorはTesterが既に行った6項目判定を再計算しない(Testerとの責務分離)。

        `quality_gate_result.status`以外の属性(build_report等)が無くても判定できる
        ことを確認する。
        """
        report = SimpleNamespace(quality_gate_result=SimpleNamespace(status="PASS"))
        self.assertFalse(hasattr(report.quality_gate_result, "build_report"))
        self.assertTrue(is_passed(report))

    def test_ensure_passed_raises_quality_gate_not_passed_error_when_failed(self) -> None:
        with self.assertRaises(QualityGateNotPassedError):
            ensure_passed(_test_report("FAIL"))

    def test_ensure_passed_does_not_raise_when_status_is_pass(self) -> None:
        try:
            ensure_passed(_test_report("PASS"))
        except QualityGateNotPassedError:
            self.fail("ensure_passed raised QualityGateNotPassedError unexpectedly")


if __name__ == "__main__":
    unittest.main()
