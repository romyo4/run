import unittest
from datetime import date

from foundation.types import PullRequest
from weekly_reviewer.analyzer import build_weekly_analysis, summarize_pull_request
from weekly_reviewer.models import Project, ReviewPeriod


class BuildWeeklyAnalysisTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project = Project(project_id="proj-1")
        self.review_period = ReviewPeriod(start_date=date(2026, 7, 5), end_date=date(2026, 7, 11))

    def test_build_weekly_analysis_summarizes_each_pull_request(self) -> None:
        pull_requests = [
            PullRequest(metadata={"summary": "課金プラン変更機能を追加"}),
            PullRequest(metadata={"title": "ログイン画面のバグ修正"}),
        ]

        result = build_weekly_analysis(self.project, self.review_period, pull_requests)

        self.assertTrue(result.success)
        self.assertEqual(len(result.value.pull_request_summaries), 2)
        self.assertIn("課金プラン変更機能を追加", result.value.pull_request_summaries)
        self.assertIn("ログイン画面のバグ修正", result.value.pull_request_summaries)

    def test_build_weekly_analysis_preserves_review_period(self) -> None:
        result = build_weekly_analysis(self.project, self.review_period, [])
        self.assertTrue(result.success)
        self.assertEqual(result.value.review_period, self.review_period)

    def test_build_weekly_analysis_handles_empty_pull_request_list(self) -> None:
        result = build_weekly_analysis(self.project, self.review_period, [])
        self.assertTrue(result.success)
        self.assertEqual(result.value.merged_pull_requests, [])
        self.assertEqual(result.value.pull_request_summaries, [])


class SummarizePullRequestTest(unittest.TestCase):
    def test_summarize_pull_request_returns_non_empty_summary(self) -> None:
        pull_request = PullRequest()
        summary = summarize_pull_request(pull_request)
        self.assertIsInstance(summary, str)
        self.assertTrue(len(summary) > 0)


if __name__ == "__main__":
    unittest.main()
