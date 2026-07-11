"""errors.pyで定義した例外クラスをre-exportする薄いモジュール。

クラスの実体はerrors.pyに一本化し、ここでは二重定義しない。
"""

from foundation.errors import (
    ConfigurationError,
    ExternalServiceError,
    FoundationError,
    NotFoundError,
    PermissionDeniedError,
    StateTransitionError,
    ValidationError,
)

__all__ = [
    "ConfigurationError",
    "ExternalServiceError",
    "FoundationError",
    "NotFoundError",
    "PermissionDeniedError",
    "StateTransitionError",
    "ValidationError",
]
