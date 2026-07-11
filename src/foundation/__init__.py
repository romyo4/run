"""Foundation公開API(F00-F03)。全モジュールはここ経由で共通定義を利用する。"""

from foundation.base_module import BaseModule
from foundation.errors import (
    ConfigurationError,
    ExternalServiceError,
    FoundationError,
    NotFoundError,
    PermissionDeniedError,
    StateTransitionError,
    ValidationError,
)
from foundation.interfaces import ConfigurationClient
from foundation.logger import get_logger
from foundation.result import Result
from foundation.types import (
    CommunicationMessage,
    Configuration,
    Context,
    Design,
    Implementation,
    Knowledge,
    Notification,
    PullRequest,
    Repository,
    Review,
    SubTask,
    Task,
    TestResult,
    Workflow,
)
from foundation.validation import require_in, require_non_empty, require_not_none, validate
from foundation.version import DESIGN_VERSION

__all__ = [
    "BaseModule",
    "ConfigurationClient",
    "ConfigurationError",
    "ExternalServiceError",
    "FoundationError",
    "NotFoundError",
    "PermissionDeniedError",
    "StateTransitionError",
    "ValidationError",
    "get_logger",
    "Result",
    "CommunicationMessage",
    "Configuration",
    "Context",
    "Design",
    "Implementation",
    "Knowledge",
    "Notification",
    "PullRequest",
    "Repository",
    "Review",
    "SubTask",
    "Task",
    "TestResult",
    "Workflow",
    "require_in",
    "require_non_empty",
    "require_not_none",
    "validate",
    "DESIGN_VERSION",
]
