import unittest

from foundation.errors import ExternalServiceError, NotFoundError
from pr_creator.github_client import GitHubPullRequestClient, HttpResponse
from pr_creator.models import BranchInformation, RepositoryInformation


class FakeHttpTransport:
    """HttpTransport Protocolのフェイク実装。実際のネットワーク通信は行わない。"""

    def __init__(self, responses: list[HttpResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str, dict[str, str], dict[str, object] | None]] = []

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        json_body: dict[str, object] | None = None,
    ) -> HttpResponse:
        self.calls.append((method, url, headers, json_body))
        return self._responses.pop(0)


class GitHubPullRequestClientTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = RepositoryInformation(owner="octo", name="repo", default_branch="main")
        self.branch = BranchInformation(base_branch="main", head_branch="feature/login")

    def test_create_pull_request_returns_number_and_url_on_success(self) -> None:
        transport = FakeHttpTransport(
            [
                HttpResponse(
                    status_code=201,
                    json_body={"number": 42, "html_url": "https://github.com/octo/repo/pull/42"},
                )
            ]
        )
        client = GitHubPullRequestClient("secret-token-value", transport=transport)

        result = client.create_pull_request(self.repository, self.branch, "Add login", "body")

        self.assertTrue(result.success)
        assert result.value is not None
        self.assertEqual(result.value["number"], 42)
        self.assertEqual(result.value["html_url"], "https://github.com/octo/repo/pull/42")
        method, url, headers, payload = transport.calls[0]
        self.assertEqual(method, "POST")
        self.assertIn("octo/repo/pulls", url)
        assert payload is not None
        self.assertEqual(payload["base"], "main")
        self.assertEqual(payload["head"], "feature/login")

    def test_create_pull_request_returns_external_service_error_on_http_failure(self) -> None:
        transport = FakeHttpTransport([HttpResponse(status_code=500, json_body={"message": "internal error"})])
        client = GitHubPullRequestClient("secret-token-value", transport=transport)

        result = client.create_pull_request(self.repository, self.branch, "Add login", "body")

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, ExternalServiceError)

    def test_update_pull_request_returns_updated_payload_on_success(self) -> None:
        transport = FakeHttpTransport([HttpResponse(status_code=200, json_body={"number": 42, "title": "Updated title"})])
        client = GitHubPullRequestClient("secret-token-value", transport=transport)

        result = client.update_pull_request(self.repository, 42, title="Updated title")

        self.assertTrue(result.success)
        assert result.value is not None
        self.assertEqual(result.value["title"], "Updated title")

    def test_request_reviewers_returns_success_result(self) -> None:
        transport = FakeHttpTransport(
            [HttpResponse(status_code=201, json_body={"requested_reviewers": [{"login": "alice"}]})]
        )
        client = GitHubPullRequestClient("secret-token-value", transport=transport)

        result = client.request_reviewers(self.repository, 42, ["alice"], ["core-team"])

        self.assertTrue(result.success)
        method, url, headers, payload = transport.calls[0]
        assert payload is not None
        self.assertEqual(payload["reviewers"], ["alice"])
        self.assertEqual(payload["team_reviewers"], ["core-team"])

    def test_get_pull_request_returns_not_found_when_missing(self) -> None:
        transport = FakeHttpTransport([HttpResponse(status_code=404, json_body={"message": "Not Found"})])
        client = GitHubPullRequestClient("secret-token-value", transport=transport)

        result = client.get_pull_request(self.repository, 999)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, NotFoundError)

    def test_access_token_is_not_present_in_error_message(self) -> None:
        token = "super-secret-token-xyz"
        transport = FakeHttpTransport([HttpResponse(status_code=500, json_body={"message": "internal error"})])
        client = GitHubPullRequestClient(token, transport=transport)

        result = client.create_pull_request(self.repository, self.branch, "Add login", "body")

        self.assertFalse(result.success)
        assert result.error is not None
        self.assertNotIn(token, str(result.error))


if __name__ == "__main__":
    unittest.main()
