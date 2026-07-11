"""FoundationErrorを頂点とする共通例外階層(設計書3.6節)。

新しい基底例外(FoundationErrorの直下の兄弟クラス)の追加はFoundation側でのみ行う。
各モジュールはこれらを継承してモジュール固有の例外を定義できる。
"""


class FoundationError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ValidationError(FoundationError):
    pass


class NotFoundError(FoundationError):
    pass


class PermissionDeniedError(FoundationError):
    pass


class StateTransitionError(FoundationError):
    pass


class ConfigurationError(FoundationError):
    pass


class ExternalServiceError(FoundationError):
    pass
