"""公開インターフェース(`build()`/`select()`/`validate()`/`get()`)を実装する
`ContextManager`(`BaseModule`継承)本体(IS19 4.5節)。

Collect→Select→Build→Validateの一連のオーケストレーションを行う。
"""

import dataclasses

from context_manager import collector, selector
from context_manager import validator as validator_module
from context_manager.errors import ContextNotFoundError, ContextValidationError
from context_manager.logging_utils import log_build_result
from context_manager.ports import GitHubManagerPort, KnowledgeManagerPort
from context_manager.selector import WORKFLOW_FIELD_MAP
from context_manager.store import ContextStore
from context_manager.types import (
    AIContext,
    ContextMetadata,
    ContextRequest,
    SelectedContext,
    ValidationResult,
    WorkflowType,
)
from foundation.base_module import BaseModule
from foundation.interfaces import ConfigurationClient
from foundation.logger import get_logger
from foundation.result import Result

logger = get_logger("context_manager")


class ContextManager(BaseModule):
    def __init__(
        self,
        knowledge_manager: KnowledgeManagerPort,
        github_manager: GitHubManagerPort,
        configuration_client: ConfigurationClient,
        store: ContextStore | None = None,
    ) -> None:
        self._knowledge_manager = knowledge_manager
        self._github_manager = github_manager
        self._configuration_client = configuration_client
        self._store = store if store is not None else ContextStore()

    def name(self) -> str:
        """'context_manager' を返す。"""
        return "context_manager"

    def health_check(self) -> Result[bool]:
        """依存先3モジュールへの疎通確認は行わず、自身の内部状態(store初期化済み等)のみを確認する
        (設計書2.2節: Repository解析・Knowledge管理・Configuration管理はContext Managerの責務外)。"""
        return Result(success=True, value=self._store is not None)

    def build(self, request: ContextRequest) -> Result[AIContext]:
        """設計書3.5節 build()。Collect→Select→組み立て→Validateを順に実行し、
        Validate結果に関わらずAIContextをResult[AIContext]として返す
        (不足がある場合はContext自体は返しつつ、4.6節のvalidation_resultログでNGを記録する)。
        Collect段階でいずれかの参照元呼び出しが失敗した場合は、その時点で
        Result(success=False, error=...) を返す。"""
        collected_result = collector.collect(
            request, self._knowledge_manager, self._github_manager, self._configuration_client
        )
        if not collected_result.success:
            return Result(success=False, error=collected_result.error)
        collected = collected_result.value

        selected_context = selector.select(request.workflow_type, collected)

        context_version = self._store.next_version(request.workflow_id)
        context_metadata = ContextMetadata(
            workflow_id=request.workflow_id,
            workflow_type=request.workflow_type,
            context_version=context_version,
            environment=collected.environment,
        )
        ai_context = AIContext(
            workflow_id=request.workflow_id,
            workflow_type=request.workflow_type,
            selected_context=selected_context,
            context_metadata=context_metadata,
            context_version=context_version,
        )

        validation_result = validator_module.validate(ai_context)

        self._store.save(ai_context)

        context_size = sum(1 for value in dataclasses.asdict(selected_context).values() if value not in (None, [], ""))
        log_build_result(
            workflow_id=request.workflow_id,
            workflow_type=request.workflow_type,
            context_version=context_version,
            context_size=context_size,
            validation_result=validation_result.is_valid,
        )

        return Result(success=True, value=ai_context)

    def select(self, workflow_type: WorkflowType, request: ContextRequest) -> Result[SelectedContext]:
        """設計書3.5節 select()。内部でcollector.collect()を実行したうえでselector.select()を適用する
        単独呼び出し用の公開API(build()からも内部的に利用される)。"""
        collected_result = collector.collect(
            request, self._knowledge_manager, self._github_manager, self._configuration_client
        )
        if not collected_result.success:
            return Result(success=False, error=collected_result.error)
        selected_context = selector.select(workflow_type, collected_result.value)
        return Result(success=True, value=selected_context)

    def validate(self, context: AIContext) -> Result[ValidationResult]:
        """設計書3.5節 validate()。validator.validate()を呼び出しResultへラップする。"""
        if context.workflow_type not in WORKFLOW_FIELD_MAP:
            return Result(
                success=False,
                error=ContextValidationError(f"Undefined workflow_type: {context.workflow_type!r}"),
            )
        result = validator_module.validate(context)
        return Result(success=True, value=result)

    def get(self, workflow_id: str) -> Result[AIContext]:
        """設計書3.5節 get()。ContextStoreから直近ビルド済みのAIContextを取得する。
        存在しない場合 Result(success=False, error=ContextNotFoundError(...)) を返す。"""
        context = self._store.get(workflow_id)
        if context is None:
            return Result(
                success=False,
                error=ContextNotFoundError(f"AIContext not found for workflow_id={workflow_id!r}"),
            )
        return Result(success=True, value=context)
