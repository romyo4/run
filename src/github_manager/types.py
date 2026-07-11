"""GitHub Manager固有のdataclass定義(IS20仕様書3.2節)。

Foundation(F01)のDomain Model一覧に追加された `foundation.types.Repository` /
`foundation.types.PullRequest` の利用方針(IS20仕様書3.1節)に基づく:

- `PullRequestMetadata` は `foundation.types.PullRequest`(F01)を継承し、
  設計書3.2節記載のモジュール固有属性(PR Number, Status, Changed Files)のみを追加する。
- `RepositoryMetadata` / `BranchMetadata` / `CommitMetadata` / `FileContent` / `Diff` /
  `RepositoryContext` は、設計書3.2節・3.3節が個別に列挙する属性のみを保持する
  値オブジェクトとして定義する(IS20仕様書3.2節のdataclass定義に基づく)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from foundation.types import PullRequest


@dataclass
class CommitMetadata:
    """設計書3.2節「Commit」"""

    commit_id: str
    author: str
    timestamp: datetime
    message: str


@dataclass
class RepositoryMetadata:
    """設計書3.2節「Repository」"""

    repository_name: str
    default_branch: str
    current_branch: str


@dataclass
class BranchMetadata:
    """設計書3.2節「Branch」"""

    branch_name: str
    latest_commit: CommitMetadata


@dataclass
class PullRequestMetadata(PullRequest):
    """設計書3.2節「Pull Request」。foundation.types.PullRequest(F01)を継承する。"""

    pr_number: int = 0
    status: str = ""
    changed_files: list[str] = field(default_factory=list)


@dataclass
class FileContent:
    """設計書3.2節「File」"""

    file_path: str
    file_content: str
    last_modified: datetime


@dataclass
class Diff:
    """設計書3.2節「Diff」"""

    changed_files: list[str]
    added_lines: int
    deleted_lines: int


@dataclass
class RepositoryContext:
    """設計書3.3節「Repository Context」。Context Manager へ提供する最小情報。
    Repository全体は含まない(設計書3.3節・4.4節)。"""

    repository_name: str
    current_branch: str
    target_files: list[str]
    changed_files: list[str]
    related_directories: list[str]
