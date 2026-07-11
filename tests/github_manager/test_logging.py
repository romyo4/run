import unittest

from github_manager.client import GitHubClient, HttpResponse
from github_manager.github_manager import GitHubManager
from tests.github_manager.fakes import DEFAULT_TOKEN, FakeConfigurationClient, FakeHttpTransport

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
PR_FILES_JSON = [{"filename": "a.py", "additions": 3, "deletions": 1}]
FILE_JSON = {"path": "a.py", "content": "cHJpbnQoMSk=", "encoding": "base64"}


def make_manager(responses: list[HttpResponse], token: str = DEFAULT_TOKEN) -> GitHubManager:
    transport = FakeHttpTransport(responses)
    client = GitHubClient(FakeConfigurationClient(token=token), transport=transport)
    return GitHubManager(client)


class LoggingTestCase(unittest.TestCase):
    def test_get_repository_logs_operation_repository_result_duration(self) -> None:
        manager = make_manager([HttpResponse(status_code=200, json_body=REPO_JSON)])

        with self.assertLogs("github_manager", level="INFO") as captured:
            manager.get_repository("octo/repo")

        message = captured.output[0]
        self.assertIn("operation=get_repository", message)
        self.assertIn("repository=octo/repo", message)
        self.assertIn("result=success", message)
        self.assertIn("duration=", message)

    def test_get_branch_logs_branch_field(self) -> None:
        manager = make_manager([HttpResponse(status_code=200, json_body=BRANCH_JSON)])

        with self.assertLogs("github_manager", level="INFO") as captured:
            manager.get_branch("octo/repo", "main")

        message = captured.output[0]
        self.assertIn("operation=get_branch", message)
        self.assertIn("branch=main", message)

    def test_get_pull_request_logs_pull_request_field(self) -> None:
        manager = make_manager(
            [
                HttpResponse(status_code=200, json_body=PR_JSON),
                HttpResponse(status_code=200, json_body=PR_FILES_JSON),
            ]
        )

        with self.assertLogs("github_manager", level="INFO") as captured:
            manager.get_pull_request("octo/repo", 42)

        message = captured.output[0]
        self.assertIn("operation=get_pull_request", message)
        self.assertIn("pull_request=42", message)

    def test_logging_does_not_include_access_token_or_secret(self) -> None:
        token = "super-secret-token-value"
        manager = make_manager([HttpResponse(status_code=200, json_body=REPO_JSON)], token=token)

        with self.assertLogs("github_manager", level="INFO") as captured:
            manager.get_repository("octo/repo")

        for message in captured.output:
            self.assertNotIn(token, message)
            self.assertNotIn("Authorization", message)

    def test_logging_does_not_include_file_content_or_diff_body(self) -> None:
        manager = make_manager([HttpResponse(status_code=200, json_body=FILE_JSON)])

        with self.assertLogs("github_manager", level="INFO") as captured:
            manager.get_file("octo/repo", "a.py")

        for message in captured.output:
            self.assertNotIn("print(1)", message)
            self.assertNotIn("cHJpbnQoMSk=", message)

    def test_logging_records_failure_result_on_error(self) -> None:
        manager = make_manager([HttpResponse(status_code=404, json_body={"message": "Not Found"})])

        with self.assertLogs("github_manager", level="INFO") as captured:
            manager.get_repository("octo/missing")

        message = captured.output[0]
        self.assertIn("result=failure", message)


if __name__ == "__main__":
    unittest.main()
