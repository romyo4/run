import dataclasses
import unittest
from datetime import UTC, datetime

from foundation.types import PullRequest
from github_manager.types import (
    BranchMetadata,
    CommitMetadata,
    Diff,
    FileContent,
    PullRequestMetadata,
    RepositoryContext,
    RepositoryMetadata,
)


class TypesTestCase(unittest.TestCase):
    def test_repository_metadata_holds_expected_fields(self) -> None:
        metadata = RepositoryMetadata(
            repository_name="octo/repo",
            default_branch="main",
            current_branch="main",
        )
        self.assertEqual(metadata.repository_name, "octo/repo")
        self.assertEqual(metadata.default_branch, "main")
        self.assertEqual(metadata.current_branch, "main")

    def test_commit_metadata_holds_expected_fields(self) -> None:
        timestamp = datetime(2026, 1, 1, tzinfo=UTC)
        commit = CommitMetadata(
            commit_id="abc123",
            author="octocat",
            timestamp=timestamp,
            message="Fix bug",
        )
        self.assertEqual(commit.commit_id, "abc123")
        self.assertEqual(commit.author, "octocat")
        self.assertEqual(commit.timestamp, timestamp)
        self.assertEqual(commit.message, "Fix bug")

    def test_branch_metadata_holds_latest_commit_metadata(self) -> None:
        commit = CommitMetadata(
            commit_id="abc123",
            author="octocat",
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            message="Fix bug",
        )
        branch = BranchMetadata(branch_name="main", latest_commit=commit)
        self.assertEqual(branch.branch_name, "main")
        self.assertIs(branch.latest_commit, commit)
        self.assertIsInstance(branch.latest_commit, CommitMetadata)

    def test_pull_request_metadata_extends_foundation_pull_request(self) -> None:
        self.assertTrue(issubclass(PullRequestMetadata, PullRequest))
        pr = PullRequestMetadata(pr_number=42, status="open", changed_files=["a.py"])
        self.assertIsInstance(pr, PullRequest)

    def test_pull_request_metadata_inherits_common_attributes(self) -> None:
        pr = PullRequestMetadata(pr_number=42, status="open", changed_files=["a.py"])
        base_fields = {f.name for f in dataclasses.fields(PullRequest)}
        self.assertTrue({"id", "created_at", "updated_at", "metadata"}.issubset(base_fields))
        self.assertTrue(pr.id)
        self.assertIsNotNone(pr.created_at)
        self.assertIsNotNone(pr.updated_at)
        self.assertEqual(pr.metadata, {})
        self.assertEqual(pr.pr_number, 42)
        self.assertEqual(pr.status, "open")
        self.assertEqual(pr.changed_files, ["a.py"])

    def test_file_content_holds_expected_fields(self) -> None:
        timestamp = datetime(2026, 1, 1, tzinfo=UTC)
        file_content = FileContent(file_path="src/app.py", file_content="print('hi')", last_modified=timestamp)
        self.assertEqual(file_content.file_path, "src/app.py")
        self.assertEqual(file_content.file_content, "print('hi')")
        self.assertEqual(file_content.last_modified, timestamp)

    def test_diff_holds_expected_fields(self) -> None:
        diff = Diff(changed_files=["a.py", "b.py"], added_lines=10, deleted_lines=2)
        self.assertEqual(diff.changed_files, ["a.py", "b.py"])
        self.assertEqual(diff.added_lines, 10)
        self.assertEqual(diff.deleted_lines, 2)

    def test_repository_context_holds_expected_fields(self) -> None:
        context = RepositoryContext(
            repository_name="octo/repo",
            current_branch="main",
            target_files=["a.py"],
            changed_files=["b.py"],
            related_directories=["src/"],
        )
        self.assertEqual(context.repository_name, "octo/repo")
        self.assertEqual(context.current_branch, "main")
        self.assertEqual(context.target_files, ["a.py"])
        self.assertEqual(context.changed_files, ["b.py"])
        self.assertEqual(context.related_directories, ["src/"])


if __name__ == "__main__":
    unittest.main()
