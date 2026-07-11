"""PRCreatorクラス本体(IS11 2章 pr_creator.py, BaseModule継承、公開I/F 4関数を実装)。

AI Development Pipelineの Pull Request 作成モジュール(M11)。
Tester(M10)がQuality GateをPASSさせた実装成果物をGitHub Pull Requestとして登録する。
コード生成・コード修正・テスト実行・レビュー・マージ・Release作成は一切行わない。
"""

from __future__ import annotations

import logging

from foundation.base_module import BaseModule
from foundation.errors import ConfigurationError, NotFoundError
from foundation.interfaces import ConfigurationClient
from foundation.logger import get_logger
from foundation.result import Result
from foundation.types import PullRequest
from foundation.utils import utc_now
from pr_creator import quality_gate, template
from pr_creator.errors import (
    GitHubPullRequestError,
    PullRequestNotFoundError,
    QualityGateNotPassedError,
)
from pr_creator.github_client import GitHubPullRequestClient, GitHubPullRequestClientProtocol
from pr_creator.logging_utils import log_operation
from pr_creator.models import (
    AssignmentResult,
    BranchInformation,
    CreatePullRequestInput,
    CreationReport,
    PullRequestTemplate,
    RepositoryInformation,
)

__all__ = ["PRCreator"]

_MODULE_NAME = "pr_creator"


class PRCreator(BaseModule):
    """AI Development PipelineのPull Request作成モジュール(M11)。"""

    def __init__(
        self,
        configuration_client: ConfigurationClient | None = None,
        github_client: GitHubPullRequestClientProtocol | None = None,
    ) -> None:
        self._logger = get_logger("pr_creator")
        self._configuration_client = configuration_client
        self._github_client = github_client
        self._creation_reports: list[CreationReport] = []

    # --- BaseModule (F02) ---
    def name(self) -> str:
        return _MODULE_NAME

    def health_check(self) -> Result[bool]:
        return Result(success=True, value=True)

    @property
    def creation_reports(self) -> list[CreationReport]:
        """publish()が記録したCreation Reportの一覧(読み取り専用コピー)。"""
        return list(self._creation_reports)

    # --- 公開インターフェース(IS11 3.5) ---
    def create_pr(self, request: CreatePullRequestInput) -> Result[PullRequest]:
        """Quality Gate PASSを確認したうえでTitle/Descriptionを生成し、GitHub Pull Requestを
        作成する。Quality Gate未PASS時は作成せずResult[PullRequest](success=False)を返す(IS11 4.2)。"""
        repository = request.repository_information
        branch = request.branch_information
        repo_label = self._repo_label_from_information(repository)
        branch_label = self._branch_label_from_information(branch)

        log_operation(
            self._logger,
            logging.INFO,
            workflow_id=request.workflow_id,
            repository=repo_label,
            branch=branch_label,
            result="STARTED",
        )

        try:
            quality_gate.ensure_passed(request.test_report)
        except QualityGateNotPassedError as exc:
            log_operation(
                self._logger,
                logging.WARNING,
                workflow_id=request.workflow_id,
                repository=repo_label,
                branch=branch_label,
                result="FAILURE",
            )
            return Result(success=False, error=exc)

        client_result = self._resolve_client()
        if not client_result.success:
            log_operation(
                self._logger,
                logging.ERROR,
                workflow_id=request.workflow_id,
                repository=repo_label,
                branch=branch_label,
                result="FAILURE",
            )
            return Result(success=False, error=client_result.error)
        client = client_result.value
        assert client is not None

        title = template.build_title(request.implementation_result, request.workflow_id)
        pr_template = template.build_template(request.implementation_result, request.test_report, request.project_context)
        body = template.render(pr_template)

        creation_result = client.create_pull_request(repository, branch, title, body)
        if not creation_result.success:
            log_operation(
                self._logger,
                logging.ERROR,
                workflow_id=request.workflow_id,
                repository=repo_label,
                branch=branch_label,
                result="FAILURE",
            )
            return Result(
                success=False,
                error=GitHubPullRequestError(str(creation_result.error)),
            )

        payload = creation_result.value or {}
        number = payload.get("number")
        url = payload.get("html_url") or payload.get("url")

        # Reviewer(M12)はPull Request単体を入力とし、design_document/implementation_result/
        # test_report/business_goal等をpull_request.metadataから読み取る設計になっている
        # (IS12 4.1 review()、reviewer.reviewer.py `_build_review_input()`)。これらのうち
        # PR Creator自身の入力契約(3.1)に無いもの(design_document/execution_plan/
        # audit_report/business_goal)は、project_contextに含まれていれば転記する
        # (models.CreatePullRequestInputのdocstring参照。2026-07 統合レビューの是正)。
        project_context = request.project_context or {}
        pull_request = PullRequest(
            metadata={
                "number": number,
                "url": url,
                "repository_owner": repository.owner,
                "repository_name": repository.name,
                "repository_default_branch": repository.default_branch,
                "base_branch": branch.base_branch,
                "head_branch": branch.head_branch,
                "title": title,
                "body": body,
                "summary": pr_template.summary,
                "labels": [],
                "workflow_id": request.workflow_id,
                "implementation_result": request.implementation_result,
                "test_report": request.test_report,
                "project_context": project_context,
                "design_document": project_context.get("design_document"),
                "execution_plan": project_context.get("execution_plan"),
                "audit_report": project_context.get("audit_report"),
                "business_goal": project_context.get("business_goal"),
                "documentation_updated": project_context.get("documentation_updated", True),
            }
        )

        log_operation(
            self._logger,
            logging.INFO,
            workflow_id=request.workflow_id,
            repository=repo_label,
            branch=branch_label,
            pull_request_number=number,
            pull_request_url=url,
            result="SUCCESS",
        )
        return Result(success=True, value=pull_request)

    def update_pr(
        self,
        pull_request: PullRequest,
        template: PullRequestTemplate | None = None,
        labels: list[str] | None = None,
    ) -> Result[PullRequest]:
        """既存のPull Request(Title/Description/Label)を更新する。Branchの切り替え・統合は行わない(IS11 4.3)。"""
        from pr_creator import template as template_module

        metadata = pull_request.metadata or {}
        number = metadata.get("number")
        repo_label = self._repo_label(metadata)
        branch_label = self._branch_label(metadata)
        workflow_id = str(metadata.get("workflow_id", ""))

        log_operation(
            self._logger,
            logging.INFO,
            workflow_id=workflow_id,
            repository=repo_label,
            branch=branch_label,
            pull_request_number=number,
            result="STARTED",
        )

        if number is None:
            error = PullRequestNotFoundError("更新対象のPull Request numberが見つかりません。")
            log_operation(
                self._logger,
                logging.ERROR,
                workflow_id=workflow_id,
                repository=repo_label,
                branch=branch_label,
                result="FAILURE",
            )
            return Result(success=False, error=error)

        client_result = self._resolve_client()
        if not client_result.success:
            log_operation(
                self._logger,
                logging.ERROR,
                workflow_id=workflow_id,
                repository=repo_label,
                branch=branch_label,
                pull_request_number=number,
                result="FAILURE",
            )
            return Result(success=False, error=client_result.error)
        client = client_result.value
        assert client is not None

        repository = self._repository_from_metadata(metadata)
        new_body = template_module.render(template) if template is not None else None

        update_result = client.update_pull_request(repository, number, title=None, body=new_body, labels=labels)
        if not update_result.success:
            wrapped = self._wrap_client_error(update_result.error)
            log_operation(
                self._logger,
                logging.ERROR,
                workflow_id=workflow_id,
                repository=repo_label,
                branch=branch_label,
                pull_request_number=number,
                result="FAILURE",
            )
            return Result(success=False, error=wrapped)

        updated_metadata = dict(metadata)
        if new_body is not None:
            updated_metadata["body"] = new_body
        if labels is not None:
            updated_metadata["labels"] = list(labels)

        updated_pull_request = PullRequest(
            id=pull_request.id,
            created_at=pull_request.created_at,
            updated_at=utc_now(),
            metadata=updated_metadata,
        )

        log_operation(
            self._logger,
            logging.INFO,
            workflow_id=workflow_id,
            repository=repo_label,
            branch=branch_label,
            pull_request_number=number,
            result="SUCCESS",
        )
        return Result(success=True, value=updated_pull_request)

    def assign_reviewers(
        self,
        pull_request: PullRequest,
        reviewers: list[str],
        team_reviewers: list[str] | None = None,
    ) -> Result[AssignmentResult]:
        """既存のPull RequestにReviewerを設定する。"""
        metadata = pull_request.metadata or {}
        number = metadata.get("number")
        repo_label = self._repo_label(metadata)
        branch_label = self._branch_label(metadata)
        workflow_id = str(metadata.get("workflow_id", ""))
        team_reviewers = team_reviewers or []

        log_operation(
            self._logger,
            logging.INFO,
            workflow_id=workflow_id,
            repository=repo_label,
            branch=branch_label,
            pull_request_number=number,
            result="STARTED",
        )

        if number is None:
            error = PullRequestNotFoundError("Reviewer設定対象のPull Request numberが見つかりません。")
            log_operation(
                self._logger,
                logging.ERROR,
                workflow_id=workflow_id,
                repository=repo_label,
                branch=branch_label,
                result="FAILURE",
            )
            return Result(success=False, error=error)

        if not reviewers and not team_reviewers:
            value = AssignmentResult(
                pull_request_number=number,
                requested_reviewers=[],
                requested_team_reviewers=[],
                success=True,
                message="Reviewerが指定されていないため、GitHub APIの呼び出しをスキップしました。",
            )
            log_operation(
                self._logger,
                logging.INFO,
                workflow_id=workflow_id,
                repository=repo_label,
                branch=branch_label,
                pull_request_number=number,
                result="SUCCESS",
            )
            return Result(success=True, value=value)

        client_result = self._resolve_client()
        if not client_result.success:
            log_operation(
                self._logger,
                logging.ERROR,
                workflow_id=workflow_id,
                repository=repo_label,
                branch=branch_label,
                pull_request_number=number,
                result="FAILURE",
            )
            return Result(success=False, error=client_result.error)
        client = client_result.value
        assert client is not None

        repository = self._repository_from_metadata(metadata)
        request_result = client.request_reviewers(repository, number, reviewers, team_reviewers)
        if not request_result.success:
            wrapped = self._wrap_client_error(request_result.error)
            log_operation(
                self._logger,
                logging.ERROR,
                workflow_id=workflow_id,
                repository=repo_label,
                branch=branch_label,
                pull_request_number=number,
                result="FAILURE",
            )
            return Result(success=False, error=wrapped)

        value = AssignmentResult(
            pull_request_number=number,
            requested_reviewers=list(reviewers),
            requested_team_reviewers=list(team_reviewers),
            success=True,
        )
        log_operation(
            self._logger,
            logging.INFO,
            workflow_id=workflow_id,
            repository=repo_label,
            branch=branch_label,
            pull_request_number=number,
            result="SUCCESS",
        )
        return Result(success=True, value=value)

    def publish(self, pull_request: PullRequest) -> Result[str]:
        """作成・更新・Reviewer設定が完了したPull Requestを最終確認し、Pull Request URLを確定・
        報告する(Creation Reportの記録を含む)。GitHubへの新規Pull Request作成は行わない。"""
        metadata = pull_request.metadata or {}
        number = metadata.get("number")
        repo_label = self._repo_label(metadata)
        branch_label = self._branch_label(metadata)
        workflow_id = str(metadata.get("workflow_id", ""))

        log_operation(
            self._logger,
            logging.INFO,
            workflow_id=workflow_id,
            repository=repo_label,
            branch=branch_label,
            pull_request_number=number,
            result="STARTED",
        )

        if number is None:
            error = PullRequestNotFoundError("公開対象のPull Request numberが見つかりません。")
            self._record_creation_report(workflow_id, repo_label, branch_label, None, None, "FAILURE")
            log_operation(
                self._logger,
                logging.ERROR,
                workflow_id=workflow_id,
                repository=repo_label,
                branch=branch_label,
                result="FAILURE",
            )
            return Result(success=False, error=error)

        client_result = self._resolve_client()
        if not client_result.success:
            self._record_creation_report(workflow_id, repo_label, branch_label, number, None, "FAILURE")
            log_operation(
                self._logger,
                logging.ERROR,
                workflow_id=workflow_id,
                repository=repo_label,
                branch=branch_label,
                pull_request_number=number,
                result="FAILURE",
            )
            return Result(success=False, error=client_result.error)
        client = client_result.value
        assert client is not None

        repository = self._repository_from_metadata(metadata)
        get_result = client.get_pull_request(repository, number)
        if not get_result.success:
            wrapped = self._wrap_client_error(get_result.error)
            self._record_creation_report(workflow_id, repo_label, branch_label, number, None, "FAILURE")
            log_operation(
                self._logger,
                logging.ERROR,
                workflow_id=workflow_id,
                repository=repo_label,
                branch=branch_label,
                pull_request_number=number,
                result="FAILURE",
            )
            return Result(success=False, error=wrapped)

        payload = get_result.value or {}
        url = payload.get("html_url") or payload.get("url") or metadata.get("url")

        self._record_creation_report(workflow_id, repo_label, branch_label, number, url, "SUCCESS")
        log_operation(
            self._logger,
            logging.INFO,
            workflow_id=workflow_id,
            repository=repo_label,
            branch=branch_label,
            pull_request_number=number,
            pull_request_url=url,
            result="SUCCESS",
        )
        return Result(success=True, value=url)

    # --- 内部ヘルパー ---
    def _resolve_client(self) -> Result[GitHubPullRequestClientProtocol]:
        """設定済みのGitHub Clientを返す。未設定時はConfigurationClient(F03)経由でAccess Tokenを
        取得しGitHubPullRequestClientを構築する。"""
        if self._github_client is not None:
            return Result(success=True, value=self._github_client)
        if self._configuration_client is None:
            return Result(
                success=False,
                error=ConfigurationError("GitHub接続情報を取得するためのConfigurationClientが設定されていません。"),
            )
        token_result = self._configuration_client.get(_MODULE_NAME, "github_access_token")
        if not token_result.success or not token_result.value:
            return Result(
                success=False,
                error=token_result.error or ConfigurationError("github_access_tokenを取得できませんでした。"),
            )
        client = GitHubPullRequestClient(str(token_result.value))
        self._github_client = client
        return Result(success=True, value=client)

    @staticmethod
    def _wrap_client_error(error: object) -> GitHubPullRequestError | PullRequestNotFoundError:
        if isinstance(error, NotFoundError):
            return PullRequestNotFoundError(str(error))
        return GitHubPullRequestError(str(error))

    def _record_creation_report(
        self,
        workflow_id: str,
        repository: str,
        branch: str,
        pull_request_number: int | None,
        pull_request_url: str | None,
        result: str,
    ) -> None:
        self._creation_reports.append(
            CreationReport(
                timestamp=utc_now(),
                workflow_id=workflow_id,
                repository=repository,
                branch=branch,
                pull_request_number=pull_request_number,
                pull_request_url=pull_request_url,
                result=result,
            )
        )

    @staticmethod
    def _repo_label_from_information(repository: RepositoryInformation) -> str:
        return f"{repository.owner}/{repository.name}"

    @staticmethod
    def _branch_label_from_information(branch: BranchInformation) -> str:
        return f"{branch.base_branch}<-{branch.head_branch}"

    @staticmethod
    def _repo_label(metadata: dict[str, object]) -> str:
        owner = metadata.get("repository_owner", "")
        name = metadata.get("repository_name", "")
        return f"{owner}/{name}"

    @staticmethod
    def _branch_label(metadata: dict[str, object]) -> str:
        base = metadata.get("base_branch", "")
        head = metadata.get("head_branch", "")
        return f"{base}<-{head}"

    @staticmethod
    def _repository_from_metadata(metadata: dict[str, object]) -> RepositoryInformation:
        return RepositoryInformation(
            owner=str(metadata.get("repository_owner", "")),
            name=str(metadata.get("repository_name", "")),
            default_branch=str(metadata.get("repository_default_branch", "")),
        )
