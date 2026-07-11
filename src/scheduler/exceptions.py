"""Scheduler (M14) 固有の例外階層(IS14 5.1節)。

Foundationの共通エラー階層(`FoundationError`/`ValidationError`/`NotFoundError`/
`StateTransitionError`/`ExternalServiceError`)を継承し、Scheduler固有の意味を持つ
例外のみを追加する。新しい基底例外は追加しない(Foundation 4.2 制約に準拠)。
"""

from __future__ import annotations

from foundation.errors import (
    ExternalServiceError,
    FoundationError,
    NotFoundError,
    StateTransitionError,
    ValidationError,
)


class SchedulerError(FoundationError):
    """Scheduler内で発生するエラーの基底クラス。"""


class InvalidScheduleDefinitionError(ValidationError, SchedulerError):
    """ScheduleDefinitionの内容が不正な場合(例: CRON指定なのにcron_expression未設定)。"""


class DuplicateWorkflowExecutionError(StateTransitionError, SchedulerError):
    """同一Workflowが実行中に再度起動要求された場合(4.4 制約)。"""


class RetryLimitExceededError(StateTransitionError, SchedulerError):
    """リトライ回数が最大3回を超過した場合(4.3 制約)。"""


class UnknownWorkflowError(NotFoundError, SchedulerError):
    """status()/retry()等で未知のworkflow_idが指定された場合。"""


class CommandRouterDispatchError(ExternalServiceError, SchedulerError):
    """Command Router呼び出し(receive())が失敗した場合。"""
