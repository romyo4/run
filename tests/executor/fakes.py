"""Executorテスト用の共有フェイク・ビルダー(unittestテストコードそのものではない)。

実際のCodex CLI/API呼び出しは行わない。`CodexAdapter`インターフェース(Protocol)を
満たす決定的なフェイク実装、および各テストで再利用するテストデータビルダーを提供する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from executor.errors import CodexGenerationError
from executor.models import (
    GeneratedTest,
    ImplementationContext,
    ModifiedFile,
    RepositoryInfo,
)
from foundation.logger import get_logger
from foundation.result import Result
from foundation.types import Design


@dataclass
class FakeCodexAdapter:
    """`executor.codex_adapter.CodexAdapter`プロトコルを満たすフェイク実装。

    決定的な結果をあらかじめ設定して返すのみで、実際の外部呼び出しは一切行わない。
    """

    modified_files: tuple[ModifiedFile, ...] = ()
    generated_tests: tuple[GeneratedTest, ...] = ()
    fail_generate_implementation: bool = False
    fail_generate_tests: bool = False
    generate_implementation_calls: list[ImplementationContext] = field(default_factory=list)
    generate_tests_calls: list[tuple[ImplementationContext, tuple[ModifiedFile, ...]]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._logger = get_logger("codex_adapter")

    def generate_implementation(self, context: ImplementationContext) -> Result[tuple[ModifiedFile, ...]]:
        self.generate_implementation_calls.append(context)
        # ログにはホワイトリストされたフィールド(design_id)のみを出力し、
        # project_context等の任意の自由記述(Secret/Token/Credentialを含み得る)は出力しない。
        self._logger.info("generate_implementation called", extra={"design_id": context.design_id})
        if self.fail_generate_implementation:
            return Result(success=False, error=CodexGenerationError("codex external call failed"))
        return Result(success=True, value=self.modified_files)

    def generate_tests(
        self, context: ImplementationContext, modified_files: tuple[ModifiedFile, ...]
    ) -> Result[tuple[GeneratedTest, ...]]:
        self.generate_tests_calls.append((context, modified_files))
        self._logger.info("generate_tests called", extra={"design_id": context.design_id})
        if self.fail_generate_tests:
            return Result(success=False, error=CodexGenerationError("codex external call failed"))
        return Result(success=True, value=self.generated_tests)


def make_design(design_id: str | None = None, metadata: dict[str, Any] | None = None) -> Design:
    """Foundation `Design` Domainのテスト用インスタンスを作る。"""
    design = Design(metadata=dict(metadata or {}))
    if design_id is not None:
        design.id = design_id
    return design


def make_approved_design(design_document: Design, *, approved: bool = True) -> Design:
    """`design_document`に対応する承認済みDesignを作る(metadata経由の規約)。"""
    metadata: dict[str, Any] = {}
    if approved:
        metadata["approval_status"] = "approved"
        metadata["design_id"] = design_document.id
    return Design(metadata=metadata)


def make_repository_info(root_path: Path, repository_id: str = "repo-1") -> RepositoryInfo:
    return RepositoryInfo(repository_id=repository_id, root_path=root_path, default_branch="main")


def make_context(root_path: Path, **overrides: Any) -> ImplementationContext:
    """テスト用の`ImplementationContext`を組み立てる。"""
    design_document = overrides.pop("design_document", None) or make_design()
    approved_design = overrides.pop("approved_design", None) or make_approved_design(design_document)
    repository_information = overrides.pop("repository_information", None) or make_repository_info(root_path)
    defaults: dict[str, Any] = dict(
        workflow_id="workflow-1",
        design_id=design_document.id,
        approved_design=approved_design,
        design_document=design_document,
        project_context={},
        repository_information=repository_information,
        execution_plan=None,
    )
    defaults.update(overrides)
    return ImplementationContext(**defaults)
