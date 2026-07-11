"""Task Queue固有の例外(設計書4.4節、IS02 5章)。

Foundationのエラー階層(`FoundationError`基底)を継承する。新しい基底例外は追加しない。
"""

from foundation.errors import FoundationError, NotFoundError, StateTransitionError


class TaskNotFoundError(NotFoundError):
    """指定task_idがキュー内に存在しない、または対象条件に合致するタスクが存在しない。"""


class QueueNotFoundError(NotFoundError):
    """指定queue_nameのキューが存在しない。"""


class InvalidQueueTransitionError(StateTransitionError):
    """禁止されたキュー内状態遷移(例: Completed/Cancelledへのretry呼び出し)。"""


class MaxRetryExceededError(FoundationError):
    """リトライ上限超過。設計書3.4「最大リトライ回数超過でFailed」に対応。"""


class WorkerFailureError(FoundationError):
    """Worker異常終了検知。設計書4.4対応。"""


class QueueCorruptionError(FoundationError):
    """キュー内部データ不整合検知。設計書4.4対応。"""


class DeadlockDetectedError(FoundationError):
    """依存関係の循環等によるデッドロック検知。設計書4.4対応。"""


class TaskTimeoutError(FoundationError):
    """実行タイムアウト検知。設計書4.4対応。"""
