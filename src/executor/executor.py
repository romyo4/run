"""Executor(M09)本体(IS09 4節)。

`load_design()`/`implement()`の2つの公開メソッドのみを提供する。
要件分析・設計・設計監査・テスト実行・Build実行・Lint実行・コードレビュー・
Pull Request作成・GitHubマージは一切行わない(Design Freeze監査によりTester/
PR Creatorへ責務を一本化済み)。
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from executor.codex_adapter import CodexAdapter
from executor.errors import (
    CodexGenerationError,
    DesignDocumentNotFoundError,
    DesignNotApprovedError,
    MultiRepositoryNotAllowedError,
    RepositoryBoundaryViolationError,
)
from executor.models import (
    ExecutionReport,
    GeneratedTest,
    ImplementationContext,
    ImplementationResult,
    ModifiedFile,
    RepositoryInfo,
)
from executor.repository_guard import RepositoryGuard
from foundation.base_module import BaseModule
from foundation.errors import FoundationError, ValidationError
from foundation.logger import get_logger
from foundation.result import Result
from foundation.types import Implementation
from foundation.utils import utc_now

# Design AuditorがDesignの`metadata`にどのように承認情報を格納するかはM08(Design Auditor)側の
# 詳細設計書が定義する範囲であり、Executor独自のDomain属性としては追加しない(IS09 3節 補足)。
# ここではExecutorが読み取り専用で参照する`metadata`のキー名のみをモジュールローカルな規約として
# 定義する。
_APPROVAL_STATUS_METADATA_KEY = "approval_status"
_APPROVED_STATUS_VALUE = "approved"
_APPROVED_DESIGN_ID_METADATA_KEY = "design_id"

_CODEX_FAILURE_MESSAGE = "Codex呼び出しに失敗しました"


class Executor(BaseModule):
    """Design Document読込と実装(コード生成・テストコード生成)のみを担当する。"""

    def __init__(self, codex_adapter: CodexAdapter, repository_guard: RepositoryGuard) -> None:
        self._codex_adapter = codex_adapter
        self._repository_guard = repository_guard
        self._logger = get_logger("executor")

    def name(self) -> str:
        """BaseModule(F02)実装。"""
        return "executor"

    def health_check(self) -> Result[bool]:
        """BaseModule(F02)実装。"""
        return Result(success=True, value=True)

    def load_design(
        self,
        workflow_id: str,
        approved_design: Any,
        design_document: Any,
        project_context: dict,
        repository_information: RepositoryInfo,
        execution_plan: dict | None = None,
    ) -> Result[ImplementationContext]:
        """Approved Designを検証し、ImplementationContextを構築する。

        設計書3.4に定義された入出力: 入力Approved Design → 出力Implementation Context。
        承認確認・Repository単一性チェックは本メソッド内で行う。
        """
        try:
            if design_document is None:
                return Result(
                    success=False,
                    error=DesignDocumentNotFoundError("design_document is required"),
                )
            if repository_information is None:
                return Result(
                    success=False,
                    error=ValidationError("repository_information is required"),
                )

            approval_error = self._validate_approval(approved_design, design_document)
            if approval_error is not None:
                return Result(success=False, error=approval_error)

            context = ImplementationContext(
                workflow_id=workflow_id,
                design_id=design_document.id,
                approved_design=approved_design,
                design_document=design_document,
                project_context=project_context or {},
                repository_information=repository_information,
                execution_plan=execution_plan,
            )
            return Result(success=True, value=context)
        except Exception as exc:  # noqa: BLE001 - モジュール境界を越えて例外を送出しない(F02)
            return Result(success=False, error=ValidationError(str(exc)))

    def implement(self, context: ImplementationContext) -> Result[ImplementationResult]:
        """ImplementationContextを基にCodexで実装コード・テストコードを生成する。

        設計書3.4に定義された入出力: 入力Implementation Context → 出力Implementation Result。
        Build/Test/Lint実行、Pull Request作成は一切行わない(4.5)。
        """
        try:
            impl_result = self._call_codex(self._codex_adapter.generate_implementation, context)
            if not impl_result.success:
                self._log_result(context, (), success=False, error=impl_result.error)
                return Result(success=False, error=impl_result.error)
            modified_files: tuple[ModifiedFile, ...] = impl_result.value or ()

            boundary_result = self._check_repository_boundaries(context.repository_information, modified_files)
            if not boundary_result.success:
                self._log_result(context, modified_files, success=False, error=boundary_result.error)
                return Result(success=False, error=boundary_result.error)

            tests_result = self._call_codex(self._codex_adapter.generate_tests, context, modified_files)
            if not tests_result.success:
                self._log_result(context, modified_files, success=False, error=tests_result.error)
                return Result(success=False, error=tests_result.error)
            generated_tests: tuple[GeneratedTest, ...] = tests_result.value or ()

            implementation = Implementation(
                metadata={
                    "workflow_id": context.workflow_id,
                    "design_id": context.design_id,
                    "repository_id": context.repository_information.repository_id,
                    "modified_file_count": len(modified_files),
                    "generated_test_count": len(generated_tests),
                }
            )
            execution_report = ExecutionReport(
                workflow_id=context.workflow_id,
                design_id=context.design_id,
                repository_id=context.repository_information.repository_id,
                modified_files=modified_files,
                generated_tests=generated_tests,
                summary=(f"{len(modified_files)} file(s) modified, " f"{len(generated_tests)} test(s) generated."),
                created_at=utc_now(),
            )
            result_value = ImplementationResult(
                implementation=implementation,
                modified_files=modified_files,
                generated_tests=generated_tests,
                execution_report=execution_report,
            )

            self._log_result(context, modified_files, success=True)
            return Result(success=True, value=result_value)
        except Exception as exc:  # noqa: BLE001 - モジュール境界を越えて例外を送出しない(F02)
            return Result(success=False, error=ValidationError(str(exc)))

    # -- 内部ヘルパー ---------------------------------------------------

    def _validate_approval(self, approved_design: Any, design_document: Any) -> FoundationError | None:
        """承認済み設計であることを検証する(4.3)。問題なければNoneを返す。"""
        if approved_design is None:
            return DesignNotApprovedError("no approved design was found for the given design document")

        metadata: Mapping[str, Any] = getattr(approved_design, "metadata", None) or {}
        approval_status = metadata.get(_APPROVAL_STATUS_METADATA_KEY)
        if approval_status != _APPROVED_STATUS_VALUE:
            return DesignNotApprovedError("no approved design was found for the given design document")

        approved_design_id = metadata.get(_APPROVED_DESIGN_ID_METADATA_KEY)
        if approved_design_id != design_document.id:
            return DesignNotApprovedError(
                "approved_design does not correspond to the given design_document "
                f"(expected design_id={design_document.id!r}, got {approved_design_id!r})"
            )
        return None

    def _call_codex(self, func: Any, *args: Any) -> Result[Any]:
        """Codex呼び出しをResultへ正規化する。例外・失敗は`CodexGenerationError`へラップする。

        認証情報を含み得る詳細原因はログへ出さず、例外の`__cause__`にのみ保持する(6節)。
        """
        try:
            result = func(*args)
        except Exception as exc:  # noqa: BLE001 - Codex呼び出し失敗を一律ラップする
            wrapped = CodexGenerationError(_CODEX_FAILURE_MESSAGE)
            wrapped.__cause__ = exc
            return Result(success=False, error=wrapped)

        if not result.success:
            wrapped = CodexGenerationError(_CODEX_FAILURE_MESSAGE)
            wrapped.__cause__ = result.error
            return Result(success=False, error=wrapped)
        return result

    def _check_repository_boundaries(
        self, repository_information: RepositoryInfo, modified_files: tuple[ModifiedFile, ...]
    ) -> Result[bool]:
        """単一Repository制約(4.4)を強制する。境界違反かつ複数Repositoryにまたがる場合は
        `MultiRepositoryNotAllowedError`、単一の境界違反は`RepositoryBoundaryViolationError`
        として返す。
        """
        foreign_roots: set[Path] = set()
        has_violation = False

        for modified_file in modified_files:
            guard_result = self._repository_guard.ensure_within_repository(repository_information, modified_file.path)
            if not (guard_result.success and guard_result.value):
                has_violation = True
                if modified_file.path.is_absolute():
                    foreign_roots.add(modified_file.path.parent)

        if not has_violation:
            return Result(success=True, value=True)

        if len(foreign_roots) >= 2:
            return Result(
                success=False,
                error=MultiRepositoryNotAllowedError(
                    "modified files span multiple repositories, which is not allowed (MVP)"
                ),
            )
        return Result(
            success=False,
            error=RepositoryBoundaryViolationError("modified files include a path outside the target repository root"),
        )

    def _log_result(
        self,
        context: ImplementationContext,
        modified_files: tuple[ModifiedFile, ...],
        success: bool,
        error: FoundationError | None = None,
    ) -> None:
        """ホワイトリスト方式でログ出力する(6節)。Secret/Token/Credentialは出力しない。"""
        extra: dict[str, Any] = {
            "workflow_id": context.workflow_id,
            "design_id": context.design_id,
            "modified_files": [str(f.path) for f in modified_files],
            "result": "success" if success else "failure",
        }
        if error is not None:
            extra["error_type"] = type(error).__name__
            self._logger.info("implementation failed", extra=extra)
        else:
            self._logger.info("implementation completed", extra=extra)
