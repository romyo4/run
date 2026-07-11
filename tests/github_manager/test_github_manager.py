import inspect
import unittest

from github_manager.client import GitHubClient, HttpResponse
from github_manager.github_manager import GitHubManager
from github_manager.types import (
    BranchMetadata,
    Diff,
    FileContent,
    PullRequestMetadata,
    RepositoryContext,
    RepositoryMetadata,
)
from tests.github_manager.fakes import FakeConfigurationClient, FakeHttpTransport

REPO_JSON = {"full_name": "octo/repo", "default_branch": "main"}
BRANCH_JSON = {
    "name": "main",
    "commit": {
        "sha": "abc123",
        "commit": {
            "author": {"name": "octocat", "date": "2026-01-01T00:00:00Z"},
            "message": "Initial commit",
        },
    },
}
PR_JSON = {"number": 42, "state": "open", "title": "Add feature"}
MERGED_PR_JSON = {
    "number": 43,
    "state": "closed",
    "title": "Add feature",
    "merged": True,
    "merged_at": "2026-07-01T00:00:00Z",
}
PR_FILES_JSON = [{"filename": "a.py", "additions": 3, "deletions": 1}]
FILE_JSON = {"path": "a.py", "content": "cHJpbnQoMSk=", "encoding": "base64"}
COMMIT_DIFF_JSON = {
    "sha": "abc123",
    "files": [{"filename": "a.py", "additions": 5, "deletions": 2}],
}


def make_manager(responses: list[HttpResponse]) -> GitHubManager:
    transport = FakeHttpTransport(responses)
    client = GitHubClient(FakeConfigurationClient(), transport=transport)
    return GitHubManager(client)


class GitHubManagerTestCase(unittest.TestCase):
    def test_name_returns_github_manager(self) -> None:
        manager = make_manager([])
        self.assertEqual(manager.name(), "github_manager")

    def test_health_check_returns_result_bool(self) -> None:
        manager = make_manager([])
        result = manager.health_check()
        self.assertTrue(result.success)
        self.assertTrue(result.value)

    def test_get_repository_returns_repository_metadata_on_success(self) -> None:
        manager = make_manager([HttpResponse(status_code=200, json_body=REPO_JSON)])

        result = manager.get_repository("octo/repo")

        self.assertTrue(result.success)
        assert result.value is not None
        self.assertIsInstance(result.value, RepositoryMetadata)
        self.assertEqual(result.value.repository_name, "octo/repo")
        self.assertEqual(result.value.default_branch, "main")

    def test_get_repository_returns_failure_result_when_repository_not_found(self) -> None:
        manager = make_manager([HttpResponse(status_code=404, json_body={"message": "Not Found"})])

        result = manager.get_repository("octo/missing")

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)

    def test_get_branch_returns_branch_metadata_on_success(self) -> None:
        manager = make_manager([HttpResponse(status_code=200, json_body=BRANCH_JSON)])

        result = manager.get_branch("octo/repo", "main")

        self.assertTrue(result.success)
        assert result.value is not None
        self.assertIsInstance(result.value, BranchMetadata)
        self.assertEqual(result.value.branch_name, "main")
        self.assertEqual(result.value.latest_commit.commit_id, "abc123")
        self.assertEqual(result.value.latest_commit.author, "octocat")
        self.assertEqual(result.value.latest_commit.message, "Initial commit")

    def test_get_branch_returns_failure_result_when_branch_not_found(self) -> None:
        manager = make_manager([HttpResponse(status_code=404, json_body={"message": "Not Found"})])

        result = manager.get_branch("octo/repo", "missing")

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)

    def test_get_pull_request_returns_pull_request_metadata_on_success(self) -> None:
        manager = make_manager(
            [
                HttpResponse(status_code=200, json_body=PR_JSON),
                HttpResponse(status_code=200, json_body=PR_FILES_JSON),
            ]
        )

        result = manager.get_pull_request("octo/repo", 42)

        self.assertTrue(result.success)
        assert result.value is not None
        self.assertIsInstance(result.value, PullRequestMetadata)
        self.assertEqual(result.value.pr_number, 42)
        self.assertEqual(result.value.status, "open")
        self.assertEqual(result.value.changed_files, ["a.py"])

    def test_get_pull_request_exposes_merged_and_merged_at_in_metadata(self) -> None:
        """Weekly Reviewer(M13)の`collect()`はMerge済み判定に`metadata["merged"]`/
        `["merged_at"]`を参照する(Reviewer(M12)と同一の規約)。GitHub Managerがその
        唯一の供給元となる(2026-07 統合レビューの是正)。"""
        manager = make_manager(
            [
                HttpResponse(status_code=200, json_body=MERGED_PR_JSON),
                HttpResponse(status_code=200, json_body=PR_FILES_JSON),
            ]
        )

        result = manager.get_pull_request("octo/repo", 43)

        self.assertTrue(result.success)
        assert result.value is not None
        self.assertTrue(result.value.metadata["merged"])
        self.assertEqual(result.value.metadata["merged_at"], "2026-07-01T00:00:00Z")

    def test_get_pull_request_reports_merged_false_when_not_merged(self) -> None:
        manager = make_manager(
            [
                HttpResponse(status_code=200, json_body=PR_JSON),
                HttpResponse(status_code=200, json_body=PR_FILES_JSON),
            ]
        )

        result = manager.get_pull_request("octo/repo", 42)

        self.assertTrue(result.success)
        assert result.value is not None
        self.assertFalse(result.value.metadata["merged"])
        self.assertIsNone(result.value.metadata["merged_at"])

    def test_get_pull_request_returns_failure_result_when_pull_request_not_found(self) -> None:
        manager = make_manager([HttpResponse(status_code=404, json_body={"message": "Not Found"})])

        result = manager.get_pull_request("octo/repo", 999)

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)

    def test_get_file_returns_file_content_on_success(self) -> None:
        manager = make_manager([HttpResponse(status_code=200, json_body=FILE_JSON)])

        result = manager.get_file("octo/repo", "a.py")

        self.assertTrue(result.success)
        assert result.value is not None
        self.assertIsInstance(result.value, FileContent)
        self.assertEqual(result.value.file_path, "a.py")
        self.assertEqual(result.value.file_content, "print(1)")

    def test_get_file_returns_failure_result_when_file_not_found(self) -> None:
        manager = make_manager([HttpResponse(status_code=404, json_body={"message": "Not Found"})])

        result = manager.get_file("octo/repo", "missing.py")

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)

    def test_get_file_uses_default_branch_when_ref_omitted(self) -> None:
        transport = FakeHttpTransport([HttpResponse(status_code=200, json_body=FILE_JSON)])
        client = GitHubClient(FakeConfigurationClient(), transport=transport)
        manager = GitHubManager(client)

        manager.get_file("octo/repo", "a.py")

        method, url, headers, timeout = transport.calls[0]
        self.assertNotIn("ref=", url)

    def test_get_diff_returns_diff_when_commit_specified(self) -> None:
        manager = make_manager([HttpResponse(status_code=200, json_body=COMMIT_DIFF_JSON)])

        result = manager.get_diff("octo/repo", commit="abc123")

        self.assertTrue(result.success)
        assert result.value is not None
        self.assertIsInstance(result.value, Diff)
        self.assertEqual(result.value.changed_files, ["a.py"])
        self.assertEqual(result.value.added_lines, 5)
        self.assertEqual(result.value.deleted_lines, 2)

    def test_get_diff_returns_diff_when_pull_request_specified(self) -> None:
        manager = make_manager([HttpResponse(status_code=200, json_body=PR_FILES_JSON)])

        result = manager.get_diff("octo/repo", pull_request_number=42)

        self.assertTrue(result.success)
        assert result.value is not None
        self.assertEqual(result.value.changed_files, ["a.py"])
        self.assertEqual(result.value.added_lines, 3)
        self.assertEqual(result.value.deleted_lines, 1)

    def test_get_diff_returns_failure_result_when_neither_commit_nor_pull_request_given(
        self,
    ) -> None:
        manager = make_manager([])

        result = manager.get_diff("octo/repo")

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)

    def test_get_diff_returns_failure_result_when_both_commit_and_pull_request_given(self) -> None:
        manager = make_manager([])

        result = manager.get_diff("octo/repo", commit="abc123", pull_request_number=42)

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)

    def test_build_repository_context_returns_scoped_fields_only(self) -> None:
        manager = make_manager([HttpResponse(status_code=200, json_body=REPO_JSON)])

        result = manager.build_repository_context("octo/repo", "executor")

        self.assertTrue(result.success)
        assert result.value is not None
        self.assertIsInstance(result.value, RepositoryContext)
        self.assertEqual(result.value.repository_name, "octo/repo")
        self.assertEqual(result.value.current_branch, "main")
        expected_fields = {
            "repository_name",
            "current_branch",
            "target_files",
            "changed_files",
            "related_directories",
        }
        actual_fields = set(vars(result.value).keys())
        self.assertEqual(actual_fields, expected_fields)

    def test_build_repository_context_does_not_include_full_repository_content(self) -> None:
        manager = make_manager([HttpResponse(status_code=200, json_body=REPO_JSON)])

        result = manager.build_repository_context("octo/repo", "executor")

        assert result.value is not None
        for value in vars(result.value).values():
            self.assertNotIsInstance(value, dict)

    def test_get_repository_wraps_github_api_error_into_failure_result(self) -> None:
        manager = make_manager([HttpResponse(status_code=500, json_body={"message": "boom"})])

        result = manager.get_repository("octo/repo")

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)

    def test_public_methods_do_not_mutate_repository_state(self) -> None:
        """Read Only制約: 書き込み系メソッドが存在しないことをAPIサーフェスで検証する。"""
        public_methods = {
            name for name, _ in inspect.getmembers(GitHubManager, predicate=inspect.isfunction) if not name.startswith("_")
        }
        write_like_prefixes = (
            "create",
            "update",
            "delete",
            "merge",
            "push",
            "write",
            "commit_",
            "put_",
            "post_",
        )
        offending = [name for name in public_methods if any(name.startswith(prefix) for prefix in write_like_prefixes)]
        self.assertEqual(offending, [])
        self.assertEqual(
            public_methods,
            {
                "name",
                "health_check",
                "get_repository",
                "get_branch",
                "get_pull_request",
                "get_file",
                "get_diff",
                "build_repository_context",
            },
        )


if __name__ == "__main__":
    unittest.main()
