import unittest
from datetime import date

from foundation.result import Result
from weekly_reviewer.fable_client import FableClient
from weekly_reviewer.models import (
    BusinessAlignmentStatus,
    BusinessEvaluation,
    MvpEvaluation,
    ReviewPeriod,
    TechnicalDebtFinding,
    WeeklyAnalysis,
)


def _weekly_analysis() -> WeeklyAnalysis:
    return WeeklyAnalysis(
        project_id="proj-1",
        review_period=ReviewPeriod(start_date=date(2026, 7, 5), end_date=date(2026, 7, 11)),
        merged_pull_requests=[],
        pull_request_summaries=[],
    )


class FakeFableClient(FableClient):
    def review_business_alignment(self, business_goal: str, weekly_analysis: WeeklyAnalysis) -> Result[BusinessEvaluation]:
        return Result(
            success=True,
            value=BusinessEvaluation(
                business_goal=business_goal,
                alignment_status=BusinessAlignmentStatus.ALIGNED,
            ),
        )

    def review_mvp_fitness(self, weekly_analysis: WeeklyAnalysis) -> Result[MvpEvaluation]:
        return Result(success=True, value=MvpEvaluation())

    def review_technical_debt(
        self, weekly_analysis: WeeklyAnalysis, review_reports, technical_debt_reports
    ) -> Result[TechnicalDebtFinding]:
        return Result(success=True, value=TechnicalDebtFinding())

    def recommend_priorities(self, weekly_analysis, business_evaluation, mvp_evaluation, technical_debt):
        return Result(success=True, value=([], [], [], []))


class FableClientAbstractTest(unittest.TestCase):
    def test_fable_client_cannot_be_instantiated_directly(self) -> None:
        with self.assertRaises(TypeError):
            FableClient()  # type: ignore[abstract]


class FableClientMethodsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = FakeFableClient()
        self.weekly_analysis = _weekly_analysis()

    def test_review_business_alignment_returns_business_evaluation_result(self) -> None:
        result = self.client.review_business_alignment("LINE登録数最大化", self.weekly_analysis)
        self.assertTrue(result.success)
        self.assertIsInstance(result.value, BusinessEvaluation)

    def test_review_mvp_fitness_returns_mvp_evaluation_result(self) -> None:
        result = self.client.review_mvp_fitness(self.weekly_analysis)
        self.assertTrue(result.success)
        self.assertIsInstance(result.value, MvpEvaluation)

    def test_review_technical_debt_returns_technical_debt_finding_result(self) -> None:
        result = self.client.review_technical_debt(self.weekly_analysis, [], [])
        self.assertTrue(result.success)
        self.assertIsInstance(result.value, TechnicalDebtFinding)

    def test_recommend_priorities_returns_four_element_tuple_result(self) -> None:
        business_evaluation = BusinessEvaluation(
            business_goal="LINE登録数最大化", alignment_status=BusinessAlignmentStatus.ALIGNED
        )
        result = self.client.recommend_priorities(
            self.weekly_analysis, business_evaluation, MvpEvaluation(), TechnicalDebtFinding()
        )
        self.assertTrue(result.success)
        self.assertEqual(len(result.value), 4)


if __name__ == "__main__":
    unittest.main()
