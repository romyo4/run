"""Context Manager(M19)パッケージの公開API(IS19 2章)。

新規ロジックは持たず、`ContextManager`・`types.py` の公開dataclass/Enum・`errors.py` の
例外クラスをre-exportするのみとする。
"""

from context_manager.errors import (
    ContextConfigurationRetrievalError,
    ContextNotFoundError,
    ContextValidationError,
    KnowledgeRetrievalError,
    RepositoryContextRetrievalError,
)
from context_manager.manager import ContextManager
from context_manager.types import (
    AIContext,
    CollectedContext,
    ContextMetadata,
    ContextRequest,
    SelectedContext,
    ValidationResult,
    WorkflowScope,
    WorkflowType,
)

__all__ = [
    "AIContext",
    "CollectedContext",
    "ContextConfigurationRetrievalError",
    "ContextManager",
    "ContextMetadata",
    "ContextNotFoundError",
    "ContextRequest",
    "ContextValidationError",
    "KnowledgeRetrievalError",
    "RepositoryContextRetrievalError",
    "SelectedContext",
    "ValidationResult",
    "WorkflowScope",
    "WorkflowType",
]
