import unittest
from datetime import date

from foundation.result import Result
from weekly_reviewer.errors import FableEvaluationError
from weekly_reviewer.evaluator import build_weekly_review, evaluate_weekly_analysis
from weekly_reviewer.fable_client import FableClient
from weekly_reviewer.models import (
    BusinessAlignmentStatus,
    BusinessEvaluation,
    MvpEvaluation,
    ReviewPeriod,
    TechnicalDebtFinding,
    WeeklyAnalysis,
    WeeklyReview,
    WeeklyReviewContext,
)


def _weekly_analysis() -> WeeklyAnalysis:
    return WeeklyAnalysis(
        project_id="proj-1",
        review_period=ReviewPeriod(start_date=date(2026, 7, 5), end_date=date(2026, 7, 11)),
        merged_pull_requests=[],
        pull_request_summaries=["課金プラン変更機能を追加"],
    )


class RecordingFableClient(FableClient):
    """呼び出し順序を記録するフェイクFableClient。"""

    def __init__(self) -> None:
        self.call_order: list[str] = []

    def review_business_alignment(self, business_goal, weekly_analysis):
        self.call_order.append("business")
        return Result(
            success=True,
            value=BusinessEvaluation(
                business_goal=business_goal,
                alignment_status=BusinessAlignmentStatus.ALIGNED,
            ),
        )

    def review_mvp_fitness(self, weekly_analysis):
        self.call_order.append("mvp")
        return Result(success=True, value=MvpEvaluation())

    def review_technical_debt(self, weekly_analysis, review_reports, technical_debt_reports):
        self.call_order.append("technical_debt")
        return Result(success=True, value=TechnicalDebtFinding())

    def recommend_priorities(self, weekly_analysis, business_evaluation, mvp_evaluation, technical_debt):
        self.call_order.append("priorities")
        return Result(
            success=True,
            value=(["達成1"], ["リスク1"], ["改善案1"], ["最優先1"]),
        )


class FailingAtStageFableClient(FableClient):
    """指定した段階で失敗を返すフェイクFableClient。"""

    def __init__(self, fail_at: str) -> None:
        self._fail_at = fail_at
        self.call_order: list[str] = []

    def _result(self, stage: str, value):
        self.call_order.append(stage)
        if stage == self._fail_at:
            return Result(success=False, error=FableEvaluationError(f"{stage} failed"))
        return Result(success=True, value=value)

    def review_business_alignment(self, business_goal, weekly_analysis):
        return self._result(
            "business",
            BusinessEvaluation(business_goal=business_goal, alignment_status=BusinessAlignmentStatus.ALIGNED),
        )

    def review_mvp_fitness(self, weekly_analysis):
        return self._result("mvp", MvpEvaluation())

    def review_technical_debt(self, weekly_analysis, review_reports, technical_debt_reports):
        return self._result("technical_debt", TechnicalDebtFinding())

    def recommend_priorities(self, weekly_analysis, business_evaluation, mvp_evaluation, technical_debt):
        return self._result("priorities", ([], [], [], []))


class EvaluateWeeklyAnalysisTest(unittest.TestCase):
    def setUp(self) -> None:
        self.weekly_analysis = _weekly_analysis()
        self.context = WeeklyReviewContext()

    def test_evaluate_weekly_analysis_returns_weekly_review_when_all_stages_succeed(self) -> None:
        client = RecordingFableClient()
        result = evaluate_weekly_analysis(self.weekly_analysis, "LINE登録数最大化", self.context, client)
        self.assertTrue(result.success)
        self.assertIsInstance(result.value, WeeklyReview)
        self.assertEqual(result.value.achievements, ["達成1"])
        self.assertEqual(result.value.risks, ["リスク1"])
        self.assertEqual(result.value.recommendations, ["改善案1"])
        self.assertEqual(result.value.top_priority_next_week, ["最優先1"])
        self.assertEqual(client.call_order, ["business", "mvp", "technical_debt", "priorities"])

    def test_evaluate_weekly_analysis_stops_on_business_alignment_failure(self) -> None:
        client = FailingAtStageFableClient(fail_at="business")
        result = evaluate_weekly_analysis(self.weekly_analysis, "LINE登録数最大化", self.context, client)
        self.assertFalse(result.success)
        self.assertEqual(client.call_order, ["business"])

    def test_evaluate_weekly_analysis_stops_on_mvp_evaluation_failure(self) -> None:
        client = FailingAtStageFableClient(fail_at="mvp")
        result = evaluate_weekly_analysis(self.weekly_analysis, "LINE登録数最大化", self.context, client)
        self.assertFalse(result.success)
        self.assertEqual(client.call_order, ["business", "mvp"])

    def test_evaluate_weekly_analysis_stops_on_technical_debt_evaluation_failure(self) -> None:
        client = FailingAtStageFableClient(fail_at="technical_debt")
        result = evaluate_weekly_analysis(self.weekly_analysis, "LINE登録数最大化", self.context, client)
        self.assertFalse(result.success)
        self.assertEqual(client.call_order, ["business", "mvp", "technical_debt"])

    def test_evaluate_weekly_analysis_stops_on_priority_recommendation_failure(self) -> None:
        client = FailingAtStageFableClient(fail_at="priorities")
        result = evaluate_weekly_analysis(self.weekly_analysis, "LINE登録数最大化", self.context, client)
        self.assertFalse(result.success)
        self.assertEqual(client.call_order, ["business", "mvp", "technical_debt", "priorities"])


class BuildWeeklyReviewTest(unittest.TestCase):
    def test_build_weekly_review_sets_all_designated_sections(self) -> None:
        weekly_analysis = _weekly_analysis()
        business_evaluation = BusinessEvaluation(
            business_goal="LINE登録数最大化", alignment_status=BusinessAlignmentStatus.ALIGNED
        )
        mvp_evaluation = MvpEvaluation(unnecessary_features=["管理画面のCSVエクスポート"])
        technical_debt = TechnicalDebtFinding(naming_issues=["変数名が曖昧"])

        review = build_weekly_review(
            weekly_analysis,
            business_evaluation,
            mvp_evaluation,
            technical_debt,
            achievements=["達成1"],
            risks=["リスク1"],
            recommendations=["改善案1"],
            top_priority_next_week=["最優先1"],
        )

        self.assertEqual(review.project_id, weekly_analysis.project_id)
        self.assertEqual(review.review_period, weekly_analysis.review_period)
        self.assertEqual(review.business_evaluation, business_evaluation)
        self.assertEqual(review.mvp_evaluation, mvp_evaluation)
        self.assertEqual(review.technical_debt, technical_debt)
        self.assertEqual(review.achievements, ["達成1"])
        self.assertEqual(review.risks, ["リスク1"])
        self.assertEqual(review.recommendations, ["改善案1"])
        self.assertEqual(review.top_priority_next_week, ["最優先1"])


if __name__ == "__main__":
    unittest.main()
