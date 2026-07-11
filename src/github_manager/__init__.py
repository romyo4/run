"""GitHub Manager(M20)公開API(IS20仕様書2章)。

`GitHubManager`・本モジュールのdataclass群・例外クラスをre-exportする。新規ロジックは
持たない。
"""

from __future__ import annotations

from github_manager.client import GitHubClient
from github_manager.errors import (
    BranchNotFoundError,
    GitHubApiError,
    GitHubFileNotFoundError,
    InvalidDiffTargetError,
    PullRequestNotFoundError,
    RepositoryNotFoundError,
)
from github_manager.github_manager import GitHubManager
from github_manager.types import (
    BranchMetadata,
    CommitMetadata,
    Diff,
    FileContent,
    PullRequestMetadata,
    RepositoryContext,
    RepositoryMetadata,
)

__all__ = [
    "GitHubManager",
    "GitHubClient",
    "BranchMetadata",
    "CommitMetadata",
    "Diff",
    "FileContent",
    "PullRequestMetadata",
    "RepositoryContext",
    "RepositoryMetadata",
    "GitHubApiError",
    "RepositoryNotFoundError",
    "BranchNotFoundError",
    "PullRequestNotFoundError",
    "GitHubFileNotFoundError",
    "InvalidDiffTargetError",
]
