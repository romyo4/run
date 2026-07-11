"""Architect (M07) 本体。

Planner(M06) が作成した Execution Plan を実装可能な Design Document へ変換する設計専任
モジュール。要件分析・Task分解・コード生成・Pull Request作成・GitHub操作・設計品質の
レビュー判定(Design Auditorの責務)は一切行わない(IS07 1. モジュール概要)。

責務外操作の禁止: 本モジュールは foundation.* と architect.* のみに依存し、GitHub API・
コード生成・Pull Request作成のいずれのクライアントもimportしない。
"""

from __future__ import annotations

from logging import Logger

from architect import analyzer, designer, publisher, validator
from architect.errors import DesignCreationError, PlanAnalysisError
from architect.models import (
    ArchitectureGuidelines,
    DesignDocument,
    DesignRequirement,
    ExecutionPlan,
    Knowledge,
    ProjectContext,
    ValidatedDesign,
    ValidationResult,
)
from foundation.base_module import BaseModule
from foundation.errors import ConfigurationError, FoundationError
from foundation.interfaces import ConfigurationClient
from foundation.logger import get_logger
from foundation.result import Result

MODULE_NAME = "architect"


class ArchitectModule(BaseModule):
    """M07 Architect の公開インターフェース実装(BaseModule継承)。"""

    def __init__(
        self,
        config_client: ConfigurationClient,
        logger: Logger | None = None,
    ) -> None:
        self._config_client = config_client
        self._logger = logger if logger is not None else get_logger(MODULE_NAME)

    def name(self) -> str:
        """ "architect" を返す。"""
        return MODULE_NAME

    def health_check(self) -> Result[bool]:
        """ConfigurationClient疎通確認を行い、Result[bool]で稼働可否を返す。"""
        try:
            result = self._config_client.get(MODULE_NAME, "health_check")
        except Exception as exc:  # noqa: BLE001 - ConfigurationClient実装側の任意の例外を捕捉する
            self._logger.warning("event=health_check result=FAILURE error=%s", type(exc).__name__)
            return Result(success=False, value=False, error=ConfigurationError(str(exc)))

        if not result.success:
            self._logger.warning("event=health_check result=FAILURE")
            error = result.error if result.error is not None else ConfigurationError("ConfigurationClient is unavailable")
            return Result(success=False, value=False, error=error)

        self._logger.info("event=health_check result=SUCCESS")
        return Result(success=True, value=True)

    def analyze_plan(
        self,
        workflow_id: str,
        execution_plan: ExecutionPlan,
        knowledge: list[Knowledge] | None = None,
        project_context: ProjectContext | None = None,
        architecture_guidelines: ArchitectureGuidelines | None = None,
    ) -> Result[DesignRequirement]:
        """Execution Plan を分析し Design Requirement を生成する(3.5 analyze_plan)。

        Planner が確定した要求(objective / task_list等)は変更しない(4.2)。
        """
        try:
            result = analyzer.analyze_plan(
                workflow_id,
                execution_plan,
                knowledge or [],
                project_context,
                architecture_guidelines,
            )
        except PlanAnalysisError as exc:
            self._logger.warning(
                "event=plan_analyzed workflow_id=%s result=FAILURE error=%s",
                workflow_id,
                type(exc).__name__,
            )
            return Result(success=False, value=None, error=exc)

        self._logger.info(
            "event=plan_analyzed workflow_id=%s requirement_id=%s result=SUCCESS",
            workflow_id,
            result.value.requirement_id if result.value else "",
        )
        return result

    def create_design(self, design_requirement: DesignRequirement) -> Result[DesignDocument]:
        """Design Requirement から Design Document を生成する(3.5 create_design)。"""
        try:
            result = designer.create_design(design_requirement)
        except DesignCreationError as exc:
            self._logger.warning(
                "event=design_created workflow_id=%s result=FAILURE error=%s",
                design_requirement.workflow_id,
                type(exc).__name__,
            )
            return Result(success=False, value=None, error=exc)

        document = result.value
        self._logger.info(
            "event=design_created workflow_id=%s design_id=%s module_count=%d " "interface_count=%d result=SUCCESS",
            design_requirement.workflow_id,
            document.id if document else "",
            len(document.module_design) if document else 0,
            len(document.interface_design) if document else 0,
        )
        return result

    def validate_design(self, design_document: DesignDocument) -> Result[ValidationResult]:
        """Design Documentの構造的完全性・内部整合性のみを自己検証する(3.5 validate_design)。

        要求適合性・品質評価はDesign Auditor(M08)の責務であり本メソッドでは行わない(4.3)。
        """
        try:
            result = validator.validate_design(design_document)
        except FoundationError as exc:
            self._logger.warning(
                "event=design_validated design_id=%s result=FAILURE error=%s",
                design_document.id,
                type(exc).__name__,
            )
            return Result(success=False, value=None, error=exc)

        validation_result = result.value
        self._logger.info(
            "event=design_validated design_id=%s module_count=%d interface_count=%d " "issue_count=%d result=%s",
            design_document.id,
            len(design_document.module_design),
            len(design_document.interface_design),
            len(validation_result.issues) if validation_result else 0,
            validation_result.status.value if validation_result else "",
        )
        return result

    def publish_design(self, validated_design: ValidatedDesign) -> Result[DesignDocument]:
        """検証済みDesignを確定し、status=PUBLISHEDのDesign Documentを返す(3.5 publish_design)。

        validation_result.status != VALID の場合は publish せず
        Result[DesignDocument](success=False)を返す。
        """
        result = publisher.publish_design(validated_design)

        design_id = validated_design.design_document.id
        module_count = len(validated_design.design_document.module_design)
        interface_count = len(validated_design.design_document.interface_design)

        if not result.success:
            self._logger.warning(
                "event=design_published design_id=%s module_count=%d interface_count=%d " "result=FAILURE error=%s",
                design_id,
                module_count,
                interface_count,
                type(result.error).__name__ if result.error else "",
            )
            return result

        self._logger.info(
            "event=design_published design_id=%s module_count=%d interface_count=%d " "result=SUCCESS",
            design_id,
            module_count,
            interface_count,
        )
        return result
