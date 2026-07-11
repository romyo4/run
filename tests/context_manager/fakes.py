"""Context Manager テスト共通フェイク実装。

Knowledge Manager(M03)・GitHub Manager(M20)・ConfigurationClient(F03)の実体は
未実装のため、`context_manager.ports` のProtocol・Foundation `ConfigurationClient` に
準拠したフェイクをここに定義し、各テストから再利用する。
"""

from dataclasses import dataclass
from typing import Any

from foundation.errors import ConfigurationError, ExternalServiceError
from foundation.interfaces import ConfigurationClient
from foundation.result import Result


@dataclass
class FakeKnowledgeDocument:
    """Knowledge Manager `KnowledgeDocument` の代替フェイク(`category`属性のみ利用)。"""

    category: str
    body: str = ""


class FakeKnowledgeManager:
    def __init__(
        self,
        documents_by_category: dict[str, list[Any]] | None = None,
        fail: bool = False,
    ) -> None:
        self.documents_by_category = documents_by_category or {}
        self.fail = fail
        self.list_documents_calls: list[str] = []
        self.search_calls: list[str] = []
        self.get_calls: list[str] = []

    def get(self, document_id: str) -> Result[Any]:
        self.get_calls.append(document_id)
        if self.fail:
            return Result(success=False, error=ExternalServiceError("knowledge get failed"))
        return Result(success=True, value=None)

    def search(self, keyword: str) -> Result[list[Any]]:
        self.search_calls.append(keyword)
        if self.fail:
            return Result(success=False, error=ExternalServiceError("knowledge search failed"))
        return Result(success=True, value=[])

    def list_documents(self, category: str) -> Result[list[Any]]:
        self.list_documents_calls.append(category)
        if self.fail:
            return Result(success=False, error=ExternalServiceError("knowledge list_documents failed"))
        return Result(success=True, value=list(self.documents_by_category.get(category, [])))


class FakeGitHubManager:
    def __init__(self, repository_context: Any = None, fail: bool = False) -> None:
        self.repository_context = repository_context
        self.fail = fail
        self.received_scopes: list[Any] = []

    def build_repository_context(self, repository: str, workflow_scope: Any) -> Result[Any]:
        self.received_scopes.append(workflow_scope)
        self.received_repositories = getattr(self, "received_repositories", [])
        self.received_repositories.append(repository)
        if self.fail:
            return Result(success=False, error=ExternalServiceError("github build failed"))
        return Result(success=True, value=self.repository_context)


def make_fake_configuration_client(environment: str = "staging", fail: bool = False) -> ConfigurationClient:
    """呼び出しごとに独立した状態を持つ`ConfigurationClient`実装インスタンスを生成する。"""

    class _FakeConfigurationClient(ConfigurationClient):
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def get(self, module_name: str, key: str) -> Result[Any]:
            self.calls.append((module_name, key))
            if fail:
                return Result(success=False, error=ConfigurationError("configuration get failed"))
            return Result(success=True, value=environment)

    return _FakeConfigurationClient()
