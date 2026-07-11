import logging
import unittest
from datetime import date, timedelta

from foundation.result import Result
from foundation.types import PullRequest
from weekly_reviewer.errors import (
    FableEvaluationError,
    WeeklyReviewerConfigurationError,
    WeeklyReviewerValidationError,
)
from weekly_reviewer.fable_client import FableClient
from weekly_reviewer.models import (
    BusinessAlignmentStatus,
    BusinessEvaluation,
    MvpEvaluation,
    Project,
    TechnicalDebtFinding,
    WeeklyAnalysis,
    WeeklyReport,
    WeeklyReview,
    WeeklyReviewContext,
    WeeklyReviewerConfig,
)
from weekly_reviewer.weekly_reviewer import WeeklyReviewer

_TEST_LOGGER = logging.getLogger("weekly_reviewer.tests")
_TEST_LOGGER.addHandler(logging.NullHandler())


def _merged_pr(days_ago: int, summary: str = "課金プラン変更機能を追加") -> PullRequest:
    return PullRequest(
        metadata={
            "merged": True,
            "merged_at": date.today() - timedelta(days=days_ago),
            "summary": summary,
        }
    )


class RecordingFableClient(FableClient):
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
        return Result(success=True, value=TechnicalDebtFinding(naming_issues=["命名が不明瞭"]))

    def recommend_priorities(self, weekly_analysis, business_evaluation, mvp_evaluation, technical_debt):
        self.call_order.append("priorities")
        return Result(
            success=True,
            value=(["達成1"], ["リスク1"], ["改善案1"], ["最優先1"]),
        )


class FailingFableClient(FableClient):
    def review_business_alignment(self, business_goal, weekly_analysis):
        return Result(success=False, error=FableEvaluationError("business alignment failed"))

    def review_mvp_fitness(self, weekly_analysis):
        return Result(success=True, value=MvpEvaluation())

    def review_technical_debt(self, weekly_analysis, review_reports, technical_debt_reports):
        return Result(success=True, value=TechnicalDebtFinding())

    def recommend_priorities(self, weekly_analysis, business_evaluation, mvp_evaluation, technical_debt):
        return Result(success=True, value=([], [], [], []))


def _make_reviewer(
    review_period_days: int = 7,
    business_goal: str | None = "LINE登録数最大化",
    fable_client: FableClient | None = None,
) -> WeeklyReviewer:
    config = WeeklyReviewerConfig(review_period_days=review_period_days, business_goal=business_goal)
    return WeeklyReviewer(config=config, logger=_TEST_LOGGER, fable_client=fable_client or RecordingFableClient())


class WeeklyReviewerNameTest(unittest.TestCase):
    def test_name_returns_weekly_reviewer(self) -> None:
        reviewer = _make_reviewer()
        self.assertEqual(reviewer.name(), "weekly_reviewer")


class WeeklyReviewerHealthCheckTest(unittest.TestCase):
    def test_health_check_returns_success_result(self) -> None:
        reviewer = _make_reviewer()
        result = reviewer.health_check()
        self.assertTrue(result.success)
        self.assertTrue(result.value)


class WeeklyReviewerCollectTest(unittest.TestCase):
    def test_collect_returns_pull_request_list_for_review_period(self) -> None:
        reviewer = _make_reviewer()
        merged = _merged_pr(days_ago=2)
        project = Project(project_id="proj-1", project_context={"pull_requests": [merged]})

        result = reviewer.collect(project)

        self.assertTrue(result.success)
        self.assertEqual(result.value, [merged])

    def test_collect_returns_empty_list_when_no_merged_pull_requests_in_period(self) -> None:
        reviewer = _make_reviewer()
        project = Project(project_id="proj-1", project_context={"pull_requests": []})

        result = reviewer.collect(project)

        self.assertTrue(result.success)
        self.assertEqual(result.value, [])

    def test_collect_returns_failure_result_when_project_is_none(self) -> None:
        reviewer = _make_reviewer()
        result = reviewer.collect(None)
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, WeeklyReviewerValidationError)

    def test_collect_resolves_review_period_from_configuration(self) -> None:
        long_window_pr = _merged_pr(days_ago=10)

        short_window_reviewer = _make_reviewer(review_period_days=7)
        long_window_reviewer = _make_reviewer(review_period_days=14)
        project = Project(project_id="proj-1", project_context={"pull_requests": [long_window_pr]})

        short_result = short_window_reviewer.collect(project)
        long_result = long_window_reviewer.collect(project)

        self.assertTrue(short_result.success)
        self.assertTrue(long_result.success)
        self.assertEqual(short_result.value, [])
        self.assertEqual(long_result.value, [long_window_pr])

    def test_collect_returns_failure_result_when_pull_request_collection_fails(self) -> None:
        reviewer = _make_reviewer()
        project = Project(project_id="proj-1", project_context={})

        result = reviewer.collect(project)

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)


class WeeklyReviewerAnalyzeTest(unittest.TestCase):
    def test_analyze_returns_weekly_analysis_with_pull_request_summaries(self) -> None:
        reviewer = _make_reviewer()
        merged = [_merged_pr(days_ago=1, summary="ログイン画面改善")]

        result = reviewer.analyze(merged)

        self.assertTrue(result.success)
        self.assertIsInstance(result.value, WeeklyAnalysis)
        self.assertEqual(result.value.pull_request_summaries, ["ログイン画面改善"])

    def test_analyze_returns_failure_result_when_merged_pull_requests_is_none(self) -> None:
        reviewer = _make_reviewer()
        result = reviewer.analyze(None)
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, WeeklyReviewerValidationError)

    def test_analyze_handles_empty_pull_request_list(self) -> None:
        reviewer = _make_reviewer()
        result = reviewer.analyze([])
        self.assertTrue(result.success)
        self.assertEqual(result.value.merged_pull_requests, [])
        self.assertEqual(result.value.pull_request_summaries, [])


class WeeklyReviewerEvaluateTest(unittest.TestCase):
    def _weekly_analysis(self) -> WeeklyAnalysis:
        reviewer = _make_reviewer()
        return reviewer.analyze([_merged_pr(days_ago=1)]).value

    def test_evaluate_returns_weekly_review_with_all_evaluation_sections(self) -> None:
        reviewer = _make_reviewer()
        result = reviewer.evaluate(self._weekly_analysis())

        self.assertTrue(result.success)
        review = result.value
        self.assertIsInstance(review, WeeklyReview)
        self.assertIsNotNone(review.business_evaluation)
        self.assertIsNotNone(review.mvp_evaluation)
        self.assertIsNotNone(review.technical_debt)
        self.assertEqual(review.achievements, ["達成1"])
        self.assertEqual(review.recommendations, ["改善案1"])

    def test_evaluate_uses_business_goal_from_configuration_when_not_supplied(self) -> None:
        client = RecordingFableClient()
        reviewer = _make_reviewer(business_goal="LINE登録数最大化", fable_client=client)

        result = reviewer.evaluate(self._weekly_analysis(), context=None)

        self.assertTrue(result.success)
        self.assertEqual(result.value.business_evaluation.business_goal, "LINE登録数最大化")

    def test_evaluate_returns_failure_result_when_business_goal_unavailable(self) -> None:
        reviewer = _make_reviewer(business_goal=None)

        result = reviewer.evaluate(self._weekly_analysis())

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, WeeklyReviewerConfigurationError)

    def test_evaluate_evaluates_business_before_mvp_before_technical_debt(self) -> None:
        client = RecordingFableClient()
        reviewer = _make_reviewer(fable_client=client)

        result = reviewer.evaluate(self._weekly_analysis())

        self.assertTrue(result.success)
        self.assertEqual(client.call_order, ["business", "mvp", "technical_debt", "priorities"])

    def test_evaluate_returns_failure_result_when_fable_evaluation_fails(self) -> None:
        reviewer = _make_reviewer(fable_client=FailingFableClient())

        result = reviewer.evaluate(self._weekly_analysis())

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)


class WeeklyReviewerPublishTest(unittest.TestCase):
    def _weekly_review(self) -> WeeklyReview:
        reviewer = _make_reviewer()
        analysis = reviewer.analyze([_merged_pr(days_ago=1)]).value
        return reviewer.evaluate(analysis).value

    def test_publish_returns_weekly_report_matching_nine_designated_fields(self) -> None:
        reviewer = _make_reviewer()
        result = reviewer.publish(self._weekly_review())

        self.assertTrue(result.success)
        report = result.value
        self.assertIsInstance(report, WeeklyReport)
        for field_name in (
            "review_period",
            "merged_pull_requests",
            "business_evaluation",
            "mvp_evaluation",
            "technical_debt",
            "achievements",
            "risks",
            "recommendations",
            "top_priority_next_week",
        ):
            self.assertTrue(hasattr(report, field_name))

    def test_publish_returns_failure_result_when_weekly_review_is_none(self) -> None:
        reviewer = _make_reviewer()
        result = reviewer.publish(None)
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, WeeklyReviewerValidationError)


class WeeklyReviewerPipelineEndToEndTest(unittest.TestCase):
    def test_pipeline_end_to_end_from_collect_to_publish(self) -> None:
        reviewer = _make_reviewer()
        merged = _merged_pr(days_ago=2)
        project = Project(
            project_id="proj-1",
            business_goal="LINE登録数最大化",
            project_context={"pull_requests": [merged]},
        )

        collect_result = reviewer.collect(project)
        self.assertTrue(collect_result.success)

        context = WeeklyReviewContext(project_context={"project_id": "proj-1", "business_goal": "LINE登録数最大化"})
        analyze_result = reviewer.analyze(collect_result.value, context=context)
        self.assertTrue(analyze_result.success)

        evaluate_result = reviewer.evaluate(analyze_result.value, context=context)
        self.assertTrue(evaluate_result.success)

        publish_result = reviewer.publish(evaluate_result.value)
        self.assertTrue(publish_result.success)
        self.assertIsInstance(publish_result.value, WeeklyReport)
        self.assertEqual(publish_result.value.project_id, "proj-1")


if __name__ == "__main__":
    unittest.main()
