"""処理フロー『Collect』段階(IS19 4.2節)。

`ports.py` 経由で Knowledge Manager・GitHub Manager を呼び出し、Foundation
`ConfigurationClient` 経由で Configuration を取得し、`CollectedContext` を組み立てる。
Knowledge・Repository情報を内部にキャッシュせず、呼び出しごとに再取得する(設計書4.4/4.5節)。
"""

from typing import Any

from context_manager.errors import (
    ContextConfigurationRetrievalError,
    KnowledgeRetrievalError,
    RepositoryContextRetrievalError,
)
from context_manager.ports import GitHubManagerPort, KnowledgeManagerPort
from context_manager.types import CollectedContext, ContextRequest
from foundation.interfaces import ConfigurationClient
from foundation.result import Result

MODULE_NAME = "context_manager"

# Workflow別Context対応表(設計書3.3節)を構成するために必要なKnowledge Manager
# カテゴリの全体集合。CollectはWorkflow種別に依存せず収集可能な全情報を集める
# (Select段階でWorkflow種別に応じて絞り込む、設計書3.6節)。
REQUIRED_KNOWLEDGE_CATEGORIES: tuple[str, ...] = (
    "business_goal",
    "knowledge",
    "requirements",
    "architecture_principles",
    "coding_rules",
)


def collect(
    request: ContextRequest,
    knowledge_manager: KnowledgeManagerPort,
    github_manager: GitHubManagerPort,
    configuration_client: ConfigurationClient,
) -> Result[CollectedContext]:
    """Knowledge Manager・GitHub Manager・ConfigurationClient(F03)を都度呼び出し、
    CollectedContextを組み立てる。いずれかの呼び出しが失敗した場合、
    Result(success=False, error=...)を返し、以降の処理へ進めない(Safety原則)。
    Knowledge/Repository情報を内部にキャッシュせず、呼び出しごとに再取得する(設計書4.4/4.5節)。
    """
    knowledge_documents: list[Any] = []
    for category in REQUIRED_KNOWLEDGE_CATEGORIES:
        result = knowledge_manager.list_documents(category)
        if not result.success:
            return Result(
                success=False,
                error=KnowledgeRetrievalError(f"Knowledge Manager list_documents() failed for category={category!r}"),
            )
        knowledge_documents.extend(result.value or [])

    repository_result = github_manager.build_repository_context(request.workflow_scope.repository, request.workflow_scope)
    if not repository_result.success:
        return Result(
            success=False,
            error=RepositoryContextRetrievalError("GitHub Manager build_repository_context() failed"),
        )

    environment_result = configuration_client.get(MODULE_NAME, "system.environment")
    if not environment_result.success:
        return Result(
            success=False,
            error=ContextConfigurationRetrievalError("ConfigurationClient.get() failed for key='system.environment'"),
        )

    collected = CollectedContext(
        knowledge_documents=knowledge_documents,
        repository_context=repository_result.value,
        environment=environment_result.value,
        execution_plan=request.execution_plan,
        user_instruction=request.user_instruction,
        implementation=request.implementation,
        test_report=request.test_report,
        merged_pull_requests=list(request.merged_pull_requests),
        review_reports=list(request.review_reports),
        technical_debt_reports=list(request.technical_debt_reports),
    )
    return Result(success=True, value=collected)
