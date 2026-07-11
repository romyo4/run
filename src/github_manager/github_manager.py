"""GitHubManager公開インターフェース実装(IS20仕様書4.2節)。

GitHub APIの生データをdataclassへ変換し、`Result[T]`でラップし、ロギングを行う。
Business判断・Repository解析は行わない(設計書2.2, 4.2節)。MVPではRead Only
(設計書4.3節)であり、Repositoryへの書き込み・更新操作は一切実装しない。
"""

from __future__ import annotations

import base64
import logging
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any, TypeVar

from foundation.base_module import BaseModule
from foundation.errors import FoundationError
from foundation.logger import get_logger
from foundation.result import Result
from foundation.utils import utc_now
from github_manager.client import GitHubClient
from github_manager.errors import InvalidDiffTargetError
from github_manager.logging_utils import log_operation
from github_manager.types import (
    BranchMetadata,
    CommitMetadata,
    Diff,
    FileContent,
    PullRequestMetadata,
    RepositoryContext,
    RepositoryMetadata,
)

__all__ = ["GitHubManager"]

_MODULE_NAME = "github_manager"

T = TypeVar("T")


def _parse_datetime(value: Any) -> datetime:
    """ISO8601文字列をdatetimeへ変換する。取得できない場合はutc_now()を返す。"""
    if not value or not isinstance(value, str):
        return utc_now()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return utc_now()


def _decode_file_content(encoded: Any, encoding: Any) -> str:
    """GitHub Contents APIのbase64エンコード済みFile Contentをデコードする。"""
    if encoding == "base64" and isinstance(encoded, str):
        try:
            return base64.b64decode(encoded).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return ""
    return str(encoded) if encoded is not None else ""


class GitHubManager(BaseModule):
    """AI Development PipelineのGitHub Repositoryアクセスモジュール(M20)。

    Context Manager・PR Creator・Weekly Reviewerは本モジュールを介してのみGitHubの
    Repository情報にアクセスする(引継ぎドキュメント5章)。
    """

    def __init__(self, client: GitHubClient) -> None:
        """clientはgithub_manager.client.GitHubClientのインスタンスを受け取る
        (テスト時はフェイク実装を注入できる)。"""
        self._client = client
        self._logger = get_logger(_MODULE_NAME)

    # --- BaseModule (F02) ---
    def name(self) -> str:
        return _MODULE_NAME

    def health_check(self) -> Result[bool]:
        """GitHub APIへの疎通確認結果をResult[bool]として返す。

        本モジュールはRepository単位でのみGitHub APIを呼び出せる構成であり(IS20仕様書
        4.2節)、health_check()自体には対象Repositoryの入力がない。そのため、依存する
        GitHubClientが正しく構築されていること(Access Token取得済み)をもって疎通可否と
        判定する(実際のネットワーク呼び出しは行わない。IS20仕様書8章: 重厚壮大化回避)。
        """
        return Result(success=True, value=self._client is not None)

    def _execute(
        self,
        operation: str,
        repository: str,
        func: Callable[[], T],
        branch: str = "-",
        pull_request: str = "-",
    ) -> Result[T]:
        """公開メソッド共通の実行ラッパー。時間計測・例外捕捉・ログ出力を一元化する
        (IS20仕様書5.1節: 例外は呼び出し元へ伝播させずResultへ変換する)。"""
        start = time.monotonic()
        try:
            value = func()
        except FoundationError as exc:
            duration = time.monotonic() - start
            log_operation(
                self._logger,
                logging.ERROR,
                operation=operation,
                repository=repository,
                branch=branch,
                pull_request=pull_request,
                result="failure",
                duration=duration,
            )
            return Result(success=False, error=exc)
        duration = time.monotonic() - start
        log_operation(
            self._logger,
            logging.INFO,
            operation=operation,
            repository=repository,
            branch=branch,
            pull_request=pull_request,
            result="success",
            duration=duration,
        )
        return Result(success=True, value=value)

    # --- 公開インターフェース(IS20仕様書3.5節) ---
    def get_repository(self, repository: str) -> Result[RepositoryMetadata]:
        """Repository Metadataを取得する。"""

        def _build() -> RepositoryMetadata:
            raw = self._client.get_repository(repository)
            default_branch = str(raw.get("default_branch", ""))
            return RepositoryMetadata(
                repository_name=str(raw.get("full_name", repository)),
                default_branch=default_branch,
                current_branch=default_branch,
            )

        return self._execute("get_repository", repository, _build)

    def get_branch(self, repository: str, branch: str) -> Result[BranchMetadata]:
        """Branch Metadataを取得する。"""

        def _build() -> BranchMetadata:
            raw = self._client.get_branch(repository, branch)
            commit_raw: dict[str, Any] = raw.get("commit") or {}
            commit_detail: dict[str, Any] = commit_raw.get("commit") or {}
            author_raw: dict[str, Any] = commit_detail.get("author") or {}
            commit_metadata = CommitMetadata(
                commit_id=str(commit_raw.get("sha", "")),
                author=str(author_raw.get("name", "")),
                timestamp=_parse_datetime(author_raw.get("date")),
                message=str(commit_detail.get("message", "")),
            )
            return BranchMetadata(branch_name=str(raw.get("name", branch)), latest_commit=commit_metadata)

        return self._execute("get_branch", repository, _build, branch=branch)

    def get_pull_request(self, repository: str, pull_request_number: int) -> Result[PullRequestMetadata]:
        """Pull Request Metadataを取得する。

        GitHub REST APIのPull Requestレスポンスに含まれる`merged`/`merged_at`は、
        `PullRequestMetadata.metadata`(Foundation `PullRequest`由来の共通属性)へ格納する。
        Weekly Reviewer(M13)の`collect()`はMerge済みPull Requestの判定に
        `pull_request.metadata["merged"]`/`["merged_at"]`を参照する規約であり
        (`weekly_reviewer.collector`、Reviewer(M12)と同一の規約)、GitHub Manager が
        その唯一の供給元となる(設計書M20 3.6: GitHub Manager → Weekly Reviewer)。
        追加のGitHub API呼び出しは発生させず、既に取得済みのPull Request生データから
        値を取り出すのみである(2026-07 統合レビューの是正)。
        """

        def _build() -> PullRequestMetadata:
            raw = self._client.get_pull_request(repository, pull_request_number)
            files = self._client.get_pull_request_diff(repository, pull_request_number)
            changed_files = [str(item.get("filename", "")) for item in files]
            return PullRequestMetadata(
                pr_number=int(raw.get("number", pull_request_number)),
                status=str(raw.get("state", "")),
                changed_files=changed_files,
                metadata={
                    "merged": bool(raw.get("merged", False)),
                    "merged_at": raw.get("merged_at"),
                },
            )

        return self._execute(
            "get_pull_request",
            repository,
            _build,
            pull_request=str(pull_request_number),
        )

    def get_file(self, repository: str, file_path: str, ref: str | None = None) -> Result[FileContent]:
        """File Contentを取得する。refを省略した場合はDefault Branchの最新内容を取得する。"""

        def _build() -> FileContent:
            raw = self._client.get_file_content(repository, file_path, ref)
            content = _decode_file_content(raw.get("content"), raw.get("encoding"))
            # GitHub Contents APIのレスポンスにはFileの最終更新日時が含まれないため、
            # IS20仕様書に取得手段の明記が無い(要確認事項)。取得できない場合は
            # utc_now()を用いる。
            return FileContent(
                file_path=str(raw.get("path", file_path)),
                file_content=content,
                last_modified=_parse_datetime(raw.get("last_modified")),
            )

        return self._execute("get_file", repository, _build)

    def get_diff(
        self,
        repository: str,
        commit: str | None = None,
        pull_request_number: int | None = None,
    ) -> Result[Diff]:
        """commit / pull_request_numberのいずれか一方から取得したDiffを返す。
        両方指定・両方未指定の場合は失敗Resultを返す(IS20仕様書8.5節)。"""

        def _build() -> Diff:
            if (commit is None) == (pull_request_number is None):
                raise InvalidDiffTargetError("commit と pull_request_number はいずれか一方のみ指定してください。")
            if commit is not None:
                raw_commit = self._client.get_commit_diff(repository, commit)
                files: list[dict[str, Any]] = raw_commit.get("files") or []
            else:
                assert pull_request_number is not None
                files = self._client.get_pull_request_diff(repository, pull_request_number)
            changed_files = [str(item.get("filename", "")) for item in files]
            added_lines = sum(int(item.get("additions", 0)) for item in files)
            deleted_lines = sum(int(item.get("deletions", 0)) for item in files)
            return Diff(
                changed_files=changed_files,
                added_lines=added_lines,
                deleted_lines=deleted_lines,
            )

        pull_request_label = str(pull_request_number) if pull_request_number is not None else "-"
        return self._execute("get_diff", repository, _build, pull_request=pull_request_label)

    def build_repository_context(self, repository: str, workflow_scope: Any) -> Result[RepositoryContext]:
        """指定されたWorkflow Scopeに必要なRepository情報のみを収集する。
        Repository全体は取得しない(設計書3.3節・4.4節)。

        `workflow_scope`はWorkflow種別を識別する文字列として扱い、本モジュールはこの値を
        用いて取得対象を絞り込むのみでWorkflow自体の解釈・制御は行わない(IS20仕様書4.2節)。
        MVPでは対象Repositoryの基本情報のみを取得し、target_files/changed_files/
        related_directoriesはWorkflow Scope単体からは導出できないため空リストとする
        (設計書4.4節: Repository全体を取得してはならない)。
        """

        def _build() -> RepositoryContext:
            raw = self._client.get_repository(repository)
            return RepositoryContext(
                repository_name=str(raw.get("full_name", repository)),
                current_branch=str(raw.get("default_branch", "")),
                target_files=[],
                changed_files=[],
                related_directories=[],
            )

        return self._execute("build_repository_context", repository, _build)
