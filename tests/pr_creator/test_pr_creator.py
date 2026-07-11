import unittest
from types import SimpleNamespace

from foundation.result import Result
from foundation.types import Implementation
from pr_creator.errors import QualityGateNotPassedError
from pr_creator.models import BranchInformation, CreatePullRequestInput, RepositoryInformation
from pr_creator.pr_creator import PRCreator


class FakeGitHubClient:
    """`GitHubPullRequestClientProtocol`のフェイク実装(実際のネットワーク通信は行わない)。"""

    def __init__(self) -> None:
        self.create_calls: list[tuple] = []

    def create_pull_request(self, repository, branch, title, body):
        self.create_calls.append((repository, branch, title, body))
        return Result(
            success=True,
            value={"number": 42, "html_url": "https://github.com/octo/repo/pull/42"},
        )

    def update_pull_request(self, repository, pull_request_number, title=None, body=None, labels=None):
        return Result(success=True, value={"number": pull_request_number})

    def request_reviewers(self, repository, pull_request_number, reviewers, team_reviewers=None):
        return Result(success=True, value={})

    def get_pull_request(self, repository, pull_request_number):
        return Result(
            success=True, value={"number": pull_request_number, "html_url": "https://github.com/octo/repo/pull/42"}
        )


def _passing_test_report(summary: str = "Quality Gate PASS: 6/6 item(s) passed.") -> SimpleNamespace:
    return SimpleNamespace(
        quality_gate_result=SimpleNamespace(status="PASS"),
        summary=summary,
    )


def _failing_test_report() -> SimpleNamespace:
    return SimpleNamespace(
        quality_gate_result=SimpleNamespace(status="FAIL"),
        summary="Quality Gate FAIL: 5/6 item(s) passed.",
    )


def _implementation_result(**metadata_overrides) -> SimpleNamespace:
    metadata = {"summary": "課金プラン変更機能を追加", "purpose": "アップグレードを可能にする"}
    metadata.update(metadata_overrides)
    modified_files = [SimpleNamespace(path="src/billing/upgrade.py")]
    return SimpleNamespace(
        implementation=Implementation(metadata=metadata),
        modified_files=modified_files,
        execution_report=SimpleNamespace(modified_files=modified_files),
    )


def _make_request(**overrides) -> CreatePullRequestInput:
    defaults = dict(
        workflow_id="wf-001",
        implementation_result=_implementation_result(),
        test_report=_passing_test_report(),
        repository_information=RepositoryInformation(owner="octo", name="repo", default_branch="main"),
        branch_information=BranchInformation(base_branch="main", head_branch="feature/billing"),
        project_context={
            "design_document": {"requirements": ["課金プラン変更機能"]},
            "execution_plan": {"steps": []},
            "audit_report": {"technical_debt_items": []},
            "business_goal": {"required_keywords": ["課金", "アップグレード"]},
        },
    )
    defaults.update(overrides)
    return CreatePullRequestInput(**defaults)


class PRCreatorCreatePrTestCase(unittest.TestCase):
    def test_create_pr_returns_success_when_quality_gate_passed(self) -> None:
        creator = PRCreator(github_client=FakeGitHubClient())
        result = creator.create_pr(_make_request())
        self.assertTrue(result.success)
        self.assertEqual(result.value.metadata["number"], 42)
        self.assertEqual(result.value.metadata["url"], "https://github.com/octo/repo/pull/42")

    def test_create_pr_returns_failure_when_quality_gate_not_passed(self) -> None:
        client = FakeGitHubClient()
        creator = PRCreator(github_client=client)
        result = creator.create_pr(_make_request(test_report=_failing_test_report()))
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, QualityGateNotPassedError)
        self.assertEqual(client.create_calls, [])

    def test_create_pr_populates_metadata_required_by_reviewer(self) -> None:
        """Reviewer(M12)の`_build_review_input()`が必須とするキー
        (design_document/implementation_result/test_report/business_goal)が
        PullRequest.metadataに存在することを確認する(2026-07 統合レビューの是正)。"""
        creator = PRCreator(github_client=FakeGitHubClient())
        request = _make_request()
        result = creator.create_pr(request)
        self.assertTrue(result.success)
        metadata = result.value.metadata
        self.assertEqual(metadata["design_document"], {"requirements": ["課金プラン変更機能"]})
        self.assertIs(metadata["implementation_result"], request.implementation_result)
        self.assertIs(metadata["test_report"], request.test_report)
        self.assertEqual(metadata["business_goal"], {"required_keywords": ["課金", "アップグレード"]})
        self.assertEqual(metadata["execution_plan"], {"steps": []})
        self.assertEqual(metadata["audit_report"], {"technical_debt_items": []})

    def test_create_pr_populates_summary_key_separately_from_body(self) -> None:
        """Reviewer(M12)の`check_business_alignment`は`pull_request.metadata["summary"]`を
        参照するため、Markdown全文(`body`)とは別に`summary`キーを持たせる
        (2026-07 統合レビューの是正)。"""
        creator = PRCreator(github_client=FakeGitHubClient())
        result = creator.create_pr(_make_request())
        self.assertTrue(result.success)
        metadata = result.value.metadata
        self.assertEqual(metadata["summary"], "課金プラン変更機能を追加")
        self.assertIn("# Summary", metadata["body"])

    def test_create_pr_includes_changed_files_from_modified_files_in_body(self) -> None:
        creator = PRCreator(github_client=FakeGitHubClient())
        result = creator.create_pr(_make_request())
        self.assertTrue(result.success)
        self.assertIn("src/billing/upgrade.py", result.value.metadata["body"])


if __name__ == "__main__":
    unittest.main()
