import unittest

from github_manager.client import GitHubClient, HttpResponse
from github_manager.errors import (
    BranchNotFoundError,
    GitHubApiError,
    GitHubFileNotFoundError,
    PullRequestNotFoundError,
    RepositoryNotFoundError,
)
from tests.github_manager.fakes import (
    DEFAULT_TOKEN,
    FakeConfigurationClient,
    FakeHttpTransport,
    RaisingHttpTransport,
)


class ClientTestCase(unittest.TestCase):
    def test_client_attaches_authorization_header_from_configuration_client(self) -> None:
        transport = FakeHttpTransport([HttpResponse(status_code=200, json_body={"name": "repo"})])
        client = GitHubClient(FakeConfigurationClient(token="secret-abc"), transport=transport)

        client.get_repository("octo/repo")

        method, url, headers, timeout = transport.calls[0]
        self.assertEqual(headers["Authorization"], "Bearer secret-abc")

    def test_client_get_repository_returns_parsed_json(self) -> None:
        transport = FakeHttpTransport(
            [HttpResponse(status_code=200, json_body={"full_name": "octo/repo", "default_branch": "main"})]
        )
        client = GitHubClient(FakeConfigurationClient(), transport=transport)

        result = client.get_repository("octo/repo")

        self.assertEqual(result, {"full_name": "octo/repo", "default_branch": "main"})
        method, url, headers, timeout = transport.calls[0]
        self.assertEqual(method, "GET")
        self.assertTrue(url.endswith("/repos/octo/repo"))

    def test_client_get_branch_returns_parsed_json(self) -> None:
        transport = FakeHttpTransport([HttpResponse(status_code=200, json_body={"name": "main"})])
        client = GitHubClient(FakeConfigurationClient(), transport=transport)

        result = client.get_branch("octo/repo", "main")

        self.assertEqual(result, {"name": "main"})
        method, url, headers, timeout = transport.calls[0]
        self.assertTrue(url.endswith("/repos/octo/repo/branches/main"))

    def test_client_get_commit_returns_parsed_json(self) -> None:
        transport = FakeHttpTransport([HttpResponse(status_code=200, json_body={"sha": "abc123"})])
        client = GitHubClient(FakeConfigurationClient(), transport=transport)

        result = client.get_commit("octo/repo", "abc123")

        self.assertEqual(result, {"sha": "abc123"})
        method, url, headers, timeout = transport.calls[0]
        self.assertTrue(url.endswith("/repos/octo/repo/commits/abc123"))

    def test_client_get_pull_request_returns_parsed_json(self) -> None:
        transport = FakeHttpTransport([HttpResponse(status_code=200, json_body={"number": 42})])
        client = GitHubClient(FakeConfigurationClient(), transport=transport)

        result = client.get_pull_request("octo/repo", 42)

        self.assertEqual(result, {"number": 42})
        method, url, headers, timeout = transport.calls[0]
        self.assertTrue(url.endswith("/repos/octo/repo/pulls/42"))

    def test_client_get_file_content_returns_parsed_json(self) -> None:
        transport = FakeHttpTransport(
            [
                HttpResponse(
                    status_code=200,
                    json_body={"path": "a.py", "content": "cHJpbnQoMSk=", "encoding": "base64"},
                )
            ]
        )
        client = GitHubClient(FakeConfigurationClient(), transport=transport)

        result = client.get_file_content("octo/repo", "a.py", ref="feature")

        self.assertEqual(result["path"], "a.py")
        method, url, headers, timeout = transport.calls[0]
        self.assertTrue(url.endswith("/repos/octo/repo/contents/a.py?ref=feature"))

    def test_client_get_commit_diff_returns_parsed_json(self) -> None:
        transport = FakeHttpTransport(
            [HttpResponse(status_code=200, json_body={"sha": "abc123", "files": [{"filename": "a.py"}]})]
        )
        client = GitHubClient(FakeConfigurationClient(), transport=transport)

        result = client.get_commit_diff("octo/repo", "abc123")

        self.assertEqual(result["files"], [{"filename": "a.py"}])

    def test_client_get_pull_request_diff_returns_parsed_json(self) -> None:
        transport = FakeHttpTransport(
            [
                HttpResponse(
                    status_code=200,
                    json_body=[{"filename": "a.py", "additions": 3, "deletions": 1}],
                )
            ]
        )
        client = GitHubClient(FakeConfigurationClient(), transport=transport)

        result = client.get_pull_request_diff("octo/repo", 42)

        self.assertEqual(result, [{"filename": "a.py", "additions": 3, "deletions": 1}])
        method, url, headers, timeout = transport.calls[0]
        self.assertTrue(url.endswith("/repos/octo/repo/pulls/42/files"))

    def test_client_raises_not_found_error_variants_on_404_response(self) -> None:
        transport = FakeHttpTransport([HttpResponse(status_code=404, json_body={"message": "Not Found"})])
        client = GitHubClient(FakeConfigurationClient(), transport=transport)
        with self.assertRaises(RepositoryNotFoundError):
            client.get_repository("octo/repo")

        transport = FakeHttpTransport([HttpResponse(status_code=404, json_body={"message": "Not Found"})])
        client = GitHubClient(FakeConfigurationClient(), transport=transport)
        with self.assertRaises(BranchNotFoundError):
            client.get_branch("octo/repo", "missing")

        transport = FakeHttpTransport([HttpResponse(status_code=404, json_body={"message": "Not Found"})])
        client = GitHubClient(FakeConfigurationClient(), transport=transport)
        with self.assertRaises(PullRequestNotFoundError):
            client.get_pull_request("octo/repo", 999)

        transport = FakeHttpTransport([HttpResponse(status_code=404, json_body={"message": "Not Found"})])
        client = GitHubClient(FakeConfigurationClient(), transport=transport)
        with self.assertRaises(GitHubFileNotFoundError):
            client.get_file_content("octo/repo", "missing.py")

    def test_client_raises_github_api_error_on_5xx_response(self) -> None:
        transport = FakeHttpTransport([HttpResponse(status_code=503, json_body={"message": "unavailable"})])
        client = GitHubClient(FakeConfigurationClient(), transport=transport)

        with self.assertRaises(GitHubApiError):
            client.get_repository("octo/repo")

    def test_client_raises_github_api_error_on_network_timeout(self) -> None:
        transport = RaisingHttpTransport(TimeoutError("timed out"))
        client = GitHubClient(FakeConfigurationClient(), transport=transport)

        with self.assertRaises(GitHubApiError):
            client.get_repository("octo/repo")

    def test_client_does_not_log_access_token(self) -> None:
        # client.py performs no logging of its own (IS20仕様書6章: ロギングはgithub_manager.py
        # の責務); ここでは少なくともエラーメッセージ・例外にAccess Tokenが含まれないことを検証する。
        transport = FakeHttpTransport([HttpResponse(status_code=503, json_body={"message": "unavailable"})])
        client = GitHubClient(FakeConfigurationClient(token=DEFAULT_TOKEN), transport=transport)
        with self.assertRaises(GitHubApiError) as ctx:
            client.get_repository("octo/repo")
        self.assertNotIn(DEFAULT_TOKEN, str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
