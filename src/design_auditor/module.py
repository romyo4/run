"""Design Auditor (M08) 本体。

Architect(M07)が作成したDesign Documentを対象に、要求との整合性・Foundation(F00〜F03)
とのアーキテクチャ整合性・MVP適合性・設計品質を監査し、実装(Executor)へ進めてよいかを
判定する単一責務モジュール。設計の修正・コード生成・Pull Request作成・GitHub操作は
一切行わない(design/M08 Design Auditor.txt 2.2 / 4.1〜4.3)。

責務外操作の禁止: 本モジュールは foundation.* と design_auditor.* のみに依存し、
コード生成・GitHub API・Pull Request作成用のクライアントはいずれもimportしない。
"""

from __future__ import annotations

from foundation.base_module import BaseModule
from foundation.errors import ConfigurationError, FoundationError
from foundation.interfaces import ConfigurationClient
from foundation.logger import get_logger
from foundation.result import Result
from foundation.types import Design
from foundation.utils import generate_id, utc_now
from foundation.validation import require_not_none

from .aggregation import aggregate_result
from .architecture_check import check_architecture
from .mvp_check import check_mvp_fitness
from .quality_check import check_quality
from .requirement_check import check_requirements
from .types import (
    ApprovedDesign,
    AuditCategory,
    AuditIssue,
    AuditReport,
    AuditResultStatus,
    MVPAssessment,
    PublishOutcome,
    ReworkRequest,
    ValidationResult,
)

MODULE_NAME = "design_auditor"


class DesignAuditor(BaseModule):
    """Design Documentを監査し、実装へ進めてよいかを判定するモジュール。"""

    def __init__(self, config_client: ConfigurationClient) -> None:
        """
        Args:
            config_client: F03 Configuration Access Patternに基づき注入するConfigurationClient実装。
        """
        self._config_client = config_client
        self._logger = get_logger(MODULE_NAME)

    def name(self) -> str:
        """F02 BaseModule契約。'design_auditor' を返す。"""
        return MODULE_NAME

    def health_check(self) -> Result[bool]:
        """F02 BaseModule契約。config_client疎通確認等の軽量チェックのみ行う。"""
        try:
            result = self._config_client.get(MODULE_NAME, "health_check")
        except Exception as exc:  # noqa: BLE001 - 疎通確認のため任意の例外を捕捉し安全側に倒す
            return Result(success=False, value=False, error=ConfigurationError(str(exc)))

        if result.success:
            return Result(success=True, value=True, error=None)

        error = (
            result.error if isinstance(result.error, FoundationError) else ConfigurationError("config_clientに接続できない")
        )
        return Result(success=False, value=False, error=error)

    def audit(self, design_document: Design) -> Result[AuditReport]:
        """3.5 audit(). 3.6の4段階チェック(Requirement/Architecture/MVP/Quality)を
        この順に内部実行し、結果を集約してAudit Reportを生成する。"""
        try:
            workflow_id, design_id = self._extract_ids(design_document)
        except FoundationError as exc:
            return Result(success=False, value=None, error=exc)

        findings = check_requirements(design_document)
        architecture_result = check_architecture(design_document)
        mvp_assessment = check_mvp_fitness(design_document)
        quality_issues = check_quality(design_document)

        violations = list(architecture_result.violations) + self._mvp_violations(mvp_assessment)
        warnings = quality_issues

        result_status = aggregate_result(findings, warnings, violations)
        recommendations = self._build_recommendations(violations, warnings)

        report = AuditReport(
            id=generate_id(),
            created_at=utc_now(),
            updated_at=utc_now(),
            metadata={},
            workflow_id=workflow_id,
            design_id=design_id,
            result=result_status,
            findings=findings,
            warnings=warnings,
            violations=violations,
            recommendations=recommendations,
        )

        self._log_audit(report)
        return Result(success=True, value=report, error=None)

    def validate_architecture(self, design_document: Design) -> Result[ValidationResult]:
        """3.5 validate_architecture(). 責務分離・モジュール境界・Interface整合性・
        Domain整合性・Configuration整合性を確認する(architecture_check.pyに委譲)。"""
        try:
            self._extract_ids(design_document)
        except FoundationError as exc:
            return Result(success=False, value=None, error=exc)

        return Result(success=True, value=check_architecture(design_document), error=None)

    def check_mvp(self, design_document: Design) -> Result[MVPAssessment]:
        """3.5 check_mvp(). MVP適合性(5.3 重厚壮大化監査基準)を確認する
        (mvp_check.pyに委譲)。"""
        try:
            self._extract_ids(design_document)
        except FoundationError as exc:
            return Result(success=False, value=None, error=exc)

        return Result(success=True, value=check_mvp_fitness(design_document), error=None)

    def publish_result(self, audit_report: AuditReport) -> Result[PublishOutcome]:
        """3.5 publish_result(). resultがPASS/PASS_WITH_COMMENTの場合はApprovedDesign、
        REWORK_REQUIRED/REJECTの場合はReworkRequestをvalueに格納する。"""
        try:
            require_not_none(audit_report, "audit_report")
        except FoundationError as exc:
            return Result(success=False, value=None, error=exc)

        outcome: PublishOutcome
        if audit_report.result in (AuditResultStatus.PASS, AuditResultStatus.PASS_WITH_COMMENT):
            comments = (
                [issue.message for issue in audit_report.warnings]
                if audit_report.result is AuditResultStatus.PASS_WITH_COMMENT
                else []
            )
            outcome = ApprovedDesign(
                design_id=audit_report.design_id,
                audit_id=audit_report.id,
                approved_at=utc_now(),
                comments=comments,
            )
        else:
            outcome = ReworkRequest(
                design_id=audit_report.design_id,
                audit_id=audit_report.id,
                reasons=[issue.message for issue in audit_report.violations],
                required_changes=list(audit_report.recommendations),
                returned_to="architect",
            )

        self._log_publish(audit_report)
        return Result(success=True, value=outcome, error=None)

    @staticmethod
    def _extract_ids(design_document: Design) -> tuple[str, str]:
        """workflow_id/design_idを取得する。

        実装解釈メモ: 3.5では各メソッドの入力はDesign Documentのみが記載されている一方、
        4.5ログ仕様はworkflow_id/design_idを要求する。設計書に新規パラメータの追加は
        行わないため、design_id=design_document.id、
        workflow_id=design_document.metadata["workflow_id"]
        (Architect側がDesign生成時にmetadataへ格納する前提)として取得する。
        この前提が成立しない場合はNotFoundErrorを送出する。
        """
        require_not_none(design_document, "design_document")

        metadata = design_document.metadata or {}
        workflow_id = metadata.get("workflow_id")
        if not workflow_id:
            from foundation.errors import NotFoundError

            raise NotFoundError("design_document.metadata['workflow_id'] が見つからない")

        return workflow_id, design_document.id

    @staticmethod
    def _mvp_violations(assessment: MVPAssessment) -> list[AuditIssue]:
        return [
            AuditIssue(
                category=AuditCategory.MVP_FITNESS,
                message=f"MVP対象外機能 '{feature}' が検出された",
                location=None,
            )
            for feature in assessment.excluded_features_detected
        ]

    @staticmethod
    def _build_recommendations(violations: list[AuditIssue], warnings: list[AuditIssue]) -> list[str]:
        recommendations = [f"[{issue.category.value}] {issue.message} を修正してください" for issue in violations]
        recommendations.extend(f"[{issue.category.value}] {issue.message} の改善を検討してください" for issue in warnings)
        return recommendations

    def _log_audit(self, report: AuditReport) -> None:
        self._logger.info(
            "workflow_id=%s design_id=%s audit_result=%s finding_count=%d warning_count=%d result=%s",
            report.workflow_id,
            report.design_id,
            report.result.value,
            len(report.findings),
            len(report.warnings),
            "success",
        )

    def _log_publish(self, audit_report: AuditReport) -> None:
        self._logger.info(
            "workflow_id=%s design_id=%s audit_result=%s finding_count=%d warning_count=%d result=%s",
            audit_report.workflow_id,
            audit_report.design_id,
            audit_report.result.value,
            len(audit_report.findings),
            len(audit_report.warnings),
            "success",
        )
