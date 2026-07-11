import unittest

from foundation.errors import ExternalServiceError, NotFoundError, ValidationError
from github_manager.errors import (
    BranchNotFoundError,
    GitHubApiError,
    GitHubFileNotFoundError,
    InvalidDiffTargetError,
    PullRequestNotFoundError,
    RepositoryNotFoundError,
)


class ErrorsTestCase(unittest.TestCase):
    def test_github_api_error_is_external_service_error_subclass(self) -> None:
        self.assertTrue(issubclass(GitHubApiError, ExternalServiceError))

    def test_repository_not_found_error_is_not_found_error_subclass(self) -> None:
        self.assertTrue(issubclass(RepositoryNotFoundError, NotFoundError))

    def test_branch_not_found_error_is_not_found_error_subclass(self) -> None:
        self.assertTrue(issubclass(BranchNotFoundError, NotFoundError))

    def test_pull_request_not_found_error_is_not_found_error_subclass(self) -> None:
        self.assertTrue(issubclass(PullRequestNotFoundError, NotFoundError))

    def test_github_file_not_found_error_is_not_found_error_subclass(self) -> None:
        self.assertTrue(issubclass(GitHubFileNotFoundError, NotFoundError))

    def test_invalid_diff_target_error_is_validation_error_subclass(self) -> None:
        self.assertTrue(issubclass(InvalidDiffTargetError, ValidationError))


if __name__ == "__main__":
    unittest.main()
