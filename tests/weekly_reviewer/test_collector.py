import unittest
from datetime import date, timedelta

from foundation.types import PullRequest
from weekly_reviewer.collector import collect_merged_pull_requests, resolve_review_period
from weekly_reviewer.errors import PullRequestCollectionError
from weekly_reviewer.models import Project, ReviewPeriod


def _merged_pr(days_ago: int) -> PullRequest:
    return PullRequest(metadata={"merged": True, "merged_at": date.today() - timedelta(days=days_ago)})


def _unmerged_pr() -> PullRequest:
    return PullRequest(metadata={"merged": False})


class CollectMergedPullRequestsTest(unittest.TestCase):
    def test_collect_merged_pull_requests_filters_by_review_period(self) -> None:
        review_period = ReviewPeriod(start_date=date.today() - timedelta(days=7), end_date=date.today())
        in_range = _merged_pr(days_ago=3)
        out_of_range = _merged_pr(days_ago=30)
        project = Project(
            project_id="proj-1",
            project_context={"pull_requests": [in_range, out_of_range]},
        )

        result = collect_merged_pull_requests(project, review_period)

        self.assertTrue(result.success)
        self.assertEqual(result.value, [in_range])

    def test_collect_merged_pull_requests_excludes_unmerged_pull_requests(self) -> None:
        review_period = ReviewPeriod(start_date=date.today() - timedelta(days=7), end_date=date.today())
        merged = _merged_pr(days_ago=1)
        unmerged = _unmerged_pr()
        project = Project(
            project_id="proj-1",
            project_context={"pull_requests": [merged, unmerged]},
        )

        result = collect_merged_pull_requests(project, review_period)

        self.assertTrue(result.success)
        self.assertEqual(result.value, [merged])

    def test_collect_merged_pull_requests_returns_failure_result_on_source_unavailable(
        self,
    ) -> None:
        review_period = ReviewPeriod(start_date=date.today() - timedelta(days=7), end_date=date.today())
        project = Project(project_id="proj-1", project_context={})

        result = collect_merged_pull_requests(project, review_period)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, PullRequestCollectionError)


class ResolveReviewPeriodTest(unittest.TestCase):
    def test_resolve_review_period_returns_seven_day_window_by_default(self) -> None:
        today = date.today()
        review_period = resolve_review_period(7, today)
        self.assertEqual(review_period.end_date, today)
        self.assertEqual((review_period.end_date - review_period.start_date).days, 7)

    def test_resolve_review_period_uses_configured_review_period_days(self) -> None:
        today = date.today()
        review_period = resolve_review_period(14, today)
        self.assertEqual(review_period.end_date, today)
        self.assertEqual((review_period.end_date - review_period.start_date).days, 14)


if __name__ == "__main__":
    unittest.main()
