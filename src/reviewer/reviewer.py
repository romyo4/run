"""ReviewerModule(BaseModule)本体、公開インターフェース実装(IS12 4.1)。"""

from __future__ import annotations

from foundation.base_module import BaseModule
from foundation.errors import FoundationError
from foundation.interfaces import ConfigurationClient
from foundation.logger import get_logger
from foundation.result import Result
from foundation.types import Implementation, PullRequest
from foundation.utils import utc_now
from foundation.validation import require_not_none
from reviewer.checks import (
    check_business_alignment,
    check_design_alignment,
    check_documentation,
    check_maintainability,
    check_mvp_compliance,
    check_requirements,
    check_technical_debt,
    determine_decision,
)
from reviewer.config import get_reviewer_config
from reviewer.domain import (
    BusinessEvaluation,
    IssueCategory,
    MVPAssessment,
    ReviewDecision,
    ReviewInput,
    ReviewIssue,
    ReviewOutcome,
    ReviewReport,
    Severity,
)

__all__ = ["ReviewerModule"]

_MODULE_NAME = "reviewer"


class ReviewerModule(BaseModule):
    """Pull Requestをレビューし、承認可否を判定するモジュール(設計書2.1)。

    Reviewerはレビューおよび承認判定のみを行い、コード修正・設計変更・Pull Request更新・
    テスト実行・GitHubマージは一切行わない(設計書2.2, 4.1, 4.2)。
    """

    def __init__(self, configuration_client: ConfigurationClient) -> None:
        self._configuration_client = configuration_client
        self._logger = get_logger(_MODULE_NAME)

    def name(self) -> str:
        """モジュール名 'reviewer' を返す。"""
        return _MODULE_NAME

    def health_check(self) -> Result[bool]:
        """Logger/ConfigurationClient疎通確認結果を返す。"""
        try:
            config_result = get_reviewer_config(self._configuration_client)
            if not config_result.success:
                return Result(success=False, value=False, error=config_result.error)
            return Result(success=True, value=True)
        except FoundationError as exc:
            return Result(success=False, value=False, error=exc)

    def review(self, pull_request: PullRequest) -> Result[ReviewReport]:
        """Pull Requestを入力に、要件/設計/Business/技術的負債の順でレビューし
        Review Reportを返す(設計書3.5, 3.6)。"""
        try:
            require_not_none(pull_request, "pull_request")
            review_input = self._build_review_input(pull_request)

            config_result = get_reviewer_config(self._configuration_client)
            if not config_result.success:
                self._logger.error(
                    "review failed: workflow_id=%s error=%s",
                    review_input.workflow_id,
                    type(config_result.error).__name__,
                )
                return Result(success=False, error=config_result.error)
            config = config_result.value

            issues: list[ReviewIssue] = []
            issues.extend(
                check_requirements(
                    review_input.design_document,
                    review_input.implementation_result,
                    review_input.test_report,
                )
            )
            issues.extend(check_design_alignment(review_input.design_document, review_input.implementation_result))
            issues.extend(check_maintainability(review_input.implementation_result))
            issues.extend(check_documentation(review_input.pull_request))

            mvp_assessment = check_mvp_compliance(review_input.implementation_result)
            business_evaluation = check_business_alignment(review_input.pull_request, review_input.business_goal)
            if business_evaluation.business_score < config.min_business_score:
                business_evaluation.aligned_with_business_goal = False

            technical_debt = check_technical_debt(review_input.implementation_result, review_input.audit_report)

            if config.blocker_severity_blocks_approval:
                for item in technical_debt:
                    if item.severity == Severity.BLOCKER:
                        issues.append(
                            ReviewIssue(
                                category=IssueCategory.TECHNICAL_DEBT,
                                description=item.description,
                                severity=Severity.BLOCKER,
                            )
                        )

            decision = determine_decision(issues, mvp_assessment, business_evaluation, technical_debt)

            review_report = ReviewReport(
                workflow_id=review_input.workflow_id,
                pull_request_id=pull_request.id,
                result=decision,
                strengths=[],
                issues=issues,
                technical_debt=technical_debt,
                business_evaluation=business_evaluation,
                recommendations=[],
            )
            self._log_completion(review_report, success=True)
            return Result(success=True, value=review_report)
        except FoundationError as exc:
            self._logger.error(
                "review failed: workflow_id=%s error=%s",
                getattr(pull_request, "id", "unknown") if pull_request is not None else "unknown",
                type(exc).__name__,
            )
            return Result(success=False, error=exc)

    def evaluate_business(self, pull_request: PullRequest) -> Result[BusinessEvaluation]:
        """Business Goalとの整合性を評価する(設計書3.5)。"""
        try:
            require_not_none(pull_request, "pull_request")
            business_goal = (pull_request.metadata or {}).get("business_goal")
            require_not_none(business_goal, "business_goal")

            config_result = get_reviewer_config(self._configuration_client)
            if not config_result.success:
                return Result(success=False, error=config_result.error)
            config = config_result.value

            evaluation = check_business_alignment(pull_request, business_goal)
            if evaluation.business_score < config.min_business_score:
                evaluation.aligned_with_business_goal = False
            return Result(success=True, value=evaluation)
        except FoundationError as exc:
            self._logger.error("evaluate_business failed: error=%s", type(exc).__name__)
            return Result(success=False, error=exc)

    def evaluate_mvp(self, implementation_result: Implementation) -> Result[MVPAssessment]:
        """MVP適合性(不要な抽象化/不要な機能/過剰設計)を評価する(設計書3.5, 4.4)。"""
        try:
            require_not_none(implementation_result, "implementation_result")
            assessment = check_mvp_compliance(implementation_result)
            return Result(success=True, value=assessment)
        except FoundationError as exc:
            self._logger.error("evaluate_mvp failed: error=%s", type(exc).__name__)
            return Result(success=False, error=exc)

    def publish_review(self, review_report: ReviewReport) -> Result[ReviewOutcome]:
        """Review Reportを最終Review Resultとして確定する。
        マージ実行・PR更新は行わず、次モジュール名のみを決定する(設計書3.5, 4.1, 4.2)。"""
        try:
            require_not_none(review_report, "review_report")
            next_module = self._route_next_module(review_report)
            outcome = ReviewOutcome(
                review_id=review_report.id,
                decision=review_report.result,
                next_module=next_module,
                published_at=utc_now(),
            )
            self._log_completion(review_report, success=True)
            return Result(success=True, value=outcome)
        except FoundationError as exc:
            self._logger.error(
                "publish_review failed: workflow_id=%s error=%s",
                (getattr(review_report, "workflow_id", "unknown") if review_report is not None else "unknown"),
                type(exc).__name__,
            )
            return Result(success=False, error=exc)

    def _build_review_input(self, pull_request: PullRequest) -> ReviewInput:
        """Pull Requestのmetadataからreview()実行に必要な入力一式を組み立てる。

        Foundationの `PullRequest` はid/created_at/updated_at/metadataのみを保証する
        (M00 3.3節)ため、Reviewer実行に必要な残りの入力(design_document等)は
        `pull_request.metadata` に格納されている前提とする。
        """
        metadata = pull_request.metadata or {}
        design_document = metadata.get("design_document")
        implementation_result = metadata.get("implementation_result")
        test_report = metadata.get("test_report")
        business_goal = metadata.get("business_goal")

        require_not_none(design_document, "design_document")
        require_not_none(implementation_result, "implementation_result")
        require_not_none(test_report, "test_report")
        require_not_none(business_goal, "business_goal")

        return ReviewInput(
            workflow_id=metadata.get("workflow_id", ""),
            execution_plan=metadata.get("execution_plan"),
            design_document=design_document,
            audit_report=metadata.get("audit_report"),
            implementation_result=implementation_result,
            test_report=test_report,
            pull_request=pull_request,
            project_context=metadata.get("project_context"),
            business_goal=business_goal,
        )

    @staticmethod
    def _route_next_module(review_report: ReviewReport) -> str:
        """判定結果から次モジュール名を決定する(設計書3.6)。

        APPROVED/APPROVED_WITH_COMMENTはMerge Managerへ、
        CHANGES_REQUESTED/REJECTEDはExecutorへ引き渡す想定とする。
        実際のルーティング実行はReviewerの責務外(次モジュール名の提示のみ)。
        """
        if review_report.result in (
            ReviewDecision.APPROVED,
            ReviewDecision.APPROVED_WITH_COMMENT,
        ):
            return "merge_manager"
        return "executor"

    def _log_completion(self, review_report: ReviewReport, success: bool) -> None:
        """設計書4.5の項目をINFOレベルで1行にまとめて記録する。

        Pull Requestの本文・diff内容、Secret・Access Token・Credentialは記録しない。
        """
        business_score = (
            review_report.business_evaluation.business_score if review_report.business_evaluation is not None else None
        )
        self._logger.info(
            "workflow_id=%s review_id=%s review_result=%s technical_debt_count=%s " "business_score=%s result=%s",
            review_report.workflow_id,
            review_report.id,
            review_report.result.value,
            len(review_report.technical_debt),
            business_score,
            "success" if success else "failure",
        )
