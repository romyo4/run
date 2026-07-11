"""WeeklyReviewer(BaseModule)本体、公開インターフェース実装(IS13 4.1節)。

Weekly Reviewer は 3.6節の処理フロー(Collect → Business Review → MVP Review →
Technical Debt Review → Priority Analysis → Weekly Report)のうち、Collect〜Weekly
Report生成までを担当し、Project Ownerへの配信自体(通知等)は呼び出し元が行う。
これは Weekly Reviewer の責務(4.1節: 修正しない、4.4節: 提案のみ行う)と整合する。
"""

from __future__ import annotations

import logging
from datetime import date

from foundation.base_module import BaseModule
from foundation.errors import FoundationError
from foundation.result import Result
from foundation.types import PullRequest
from weekly_reviewer.analyzer import build_weekly_analysis
from weekly_reviewer.collector import collect_merged_pull_requests, resolve_review_period
from weekly_reviewer.errors import (
    WeeklyReviewerConfigurationError,
    WeeklyReviewerValidationError,
)
from weekly_reviewer.evaluator import evaluate_weekly_analysis
from weekly_reviewer.fable_client import FableClient
from weekly_reviewer.logging_utils import build_log_message
from weekly_reviewer.models import (
    Project,
    ReviewPeriod,
    WeeklyAnalysis,
    WeeklyReport,
    WeeklyReview,
    WeeklyReviewContext,
    WeeklyReviewerConfig,
)
from weekly_reviewer.reporter import render_weekly_report

__all__ = ["WeeklyReviewer"]

_MODULE_NAME = "weekly_reviewer"


class WeeklyReviewer(BaseModule):
    """1週間のMerge済みPull Requestを俯瞰し、Business Goal > MVP > Technical Debt の
    優先順位(設計書4.3節)で評価してWeekly Reportを作成するモジュール(設計書2.1節)。

    要件分析・設計・コード生成・Pull Requestレビュー・マージ・リリース・コード修正・
    Design修正は一切行わず、実施判断も行わない(提案のみ、設計書4.1節・4.4節)。
    """

    def __init__(
        self,
        config: WeeklyReviewerConfig,
        logger: logging.Logger,
        fable_client: FableClient,
    ) -> None:
        self._config = config
        self._logger = logger
        self._fable_client = fable_client

    def name(self) -> str:
        """モジュール名 'weekly_reviewer' を返す。"""
        return _MODULE_NAME

    def health_check(self) -> Result[bool]:
        """設定値・Fableクライアントの疎通確認結果を返す。"""
        if self._config is None:
            return Result(
                success=False,
                value=False,
                error=WeeklyReviewerConfigurationError("weekly_reviewer config is unavailable"),
            )
        if self._fable_client is None:
            return Result(
                success=False,
                value=False,
                error=WeeklyReviewerConfigurationError("fable_client is unavailable"),
            )
        return Result(success=True, value=True)

    def collect(self, project: Project) -> Result[list[PullRequest]]:
        """設計書3.5節。対象期間(review_period)のMerge済みPull Requestを収集する。
        review_period は WeeklyReviewerConfig.review_period_days
        (F03、ConfigurationClient経由で解決済みの設定値、既定値7日)から算出する。"""
        try:
            if project is None:
                raise WeeklyReviewerValidationError("project must not be None")

            review_period = self._resolve_review_period()
            collection_result = collect_merged_pull_requests(project, review_period)
            if not collection_result.success:
                self._log(review_period, 0, 0, 0, "failure")
                return Result(success=False, error=collection_result.error)

            self._log(review_period, len(collection_result.value), 0, 0, "success")
            return Result(success=True, value=collection_result.value)
        except FoundationError as exc:
            self._logger.error("collect failed: error=%s", type(exc).__name__)
            return Result(success=False, error=exc)

    def analyze(
        self,
        merged_pull_requests: list[PullRequest] | None,
        context: WeeklyReviewContext | None = None,
    ) -> Result[WeeklyAnalysis]:
        """設計書3.5節。Merged Pull Requestsを要約しWeekly Analysisを構築する。
        contextは設計書3.1節の入力(review_reports等)を後続evaluate()へ引き継ぐための
        補助引数であり、公開インターフェースの主入出力は変更しない。project_id等の
        Projectに由来する値はcontext.project_contextから引き継ぐ。"""
        try:
            if merged_pull_requests is None:
                raise WeeklyReviewerValidationError("merged_pull_requests must not be None")

            ctx = context or WeeklyReviewContext()
            project = Project(
                project_id=ctx.project_context.get("project_id", ""),
                business_goal=ctx.project_context.get("business_goal"),
                project_context=ctx.project_context,
            )
            review_period = self._resolve_review_period()

            analysis_result = build_weekly_analysis(project, review_period, merged_pull_requests)
            if not analysis_result.success:
                return Result(success=False, error=analysis_result.error)
            return Result(success=True, value=analysis_result.value)
        except FoundationError as exc:
            self._logger.error("analyze failed: error=%s", type(exc).__name__)
            return Result(success=False, error=exc)

    def evaluate(
        self,
        weekly_analysis: WeeklyAnalysis,
        context: WeeklyReviewContext | None = None,
    ) -> Result[WeeklyReview]:
        """設計書3.5節。Business Goal > MVP > Technical Debt > Development Directionの順(4.3節)で
        Fableへ評価を委譲し、Weekly Reviewを構築する。business_goalが引数(context)で得られない
        場合はWeeklyReviewerConfig.business_goal(F03、ConfigurationClient経由で解決済みの設定値)
        から取得する。"""
        try:
            if weekly_analysis is None:
                raise WeeklyReviewerValidationError("weekly_analysis must not be None")

            ctx = context or WeeklyReviewContext()
            business_goal = ctx.project_context.get("business_goal") or self._config.business_goal
            if not business_goal:
                raise WeeklyReviewerConfigurationError("business_goal is unavailable")

            evaluation_result = evaluate_weekly_analysis(weekly_analysis, business_goal, ctx, self._fable_client)
            if not evaluation_result.success:
                self._log(
                    weekly_analysis.review_period,
                    len(weekly_analysis.merged_pull_requests),
                    0,
                    0,
                    "failure",
                )
                return Result(success=False, error=evaluation_result.error)

            weekly_review = evaluation_result.value
            technical_debt_count = weekly_review.technical_debt.count if weekly_review.technical_debt is not None else 0
            self._log(
                weekly_analysis.review_period,
                len(weekly_analysis.merged_pull_requests),
                technical_debt_count,
                len(weekly_review.recommendations),
                "success",
            )
            return Result(success=True, value=weekly_review)
        except FoundationError as exc:
            self._logger.error("evaluate failed: error=%s", type(exc).__name__)
            return Result(success=False, error=exc)

    def publish(self, weekly_review: WeeklyReview) -> Result[WeeklyReport]:
        """設計書3.5節。Weekly ReviewからWeekly Reportを生成する。Project Ownerへの
        引き渡し(通知送信等)自体はWeekly Reviewerの責務外であり、戻り値のWeeklyReportを
        呼び出し元(Scheduler/Notification等)へ返すのみとする(2.2節・4.4節)。"""
        try:
            if weekly_review is None:
                raise WeeklyReviewerValidationError("weekly_review must not be None")

            report_result = render_weekly_report(weekly_review)
            if not report_result.success:
                return Result(success=False, error=report_result.error)

            report = report_result.value
            technical_debt_count = report.technical_debt.count if report.technical_debt is not None else 0
            self._log(
                report.review_period,
                len(report.merged_pull_requests),
                technical_debt_count,
                len(report.recommendations),
                "success",
            )
            return Result(success=True, value=report)
        except FoundationError as exc:
            self._logger.error("publish failed: error=%s", type(exc).__name__)
            return Result(success=False, error=exc)

    def _resolve_review_period(self) -> ReviewPeriod:
        return resolve_review_period(self._config.review_period_days, date.today())

    def _log(
        self,
        review_period: ReviewPeriod,
        merged_pr_count: int,
        technical_debt_count: int,
        recommendation_count: int,
        result: str,
    ) -> None:
        """設計書4.5節・IS13 6節の5項目をログへ出力する(timestampはLoggerが付与)。
        Pull Requestの本文・差分・Secret・Access Token・Credentialは出力しない。"""
        message = build_log_message(review_period, merged_pr_count, technical_debt_count, recommendation_count, result)
        if result == "success":
            self._logger.info(message)
        else:
            self._logger.error(message)
