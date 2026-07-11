"""許可遷移表と検証ロジック(IS01 4.1 / 設計書3.2・3.5)。

正常遷移の直線経路(Created→...→Completed)と、任意の非終端状態からFailed/Cancelled
への遷移のみを許可する。Completed/Failed/Cancelledは終端状態であり、そこからの遷移は
一切許可しない(禁止例: Completed→Executing, Failed→Testing, Merged→Planning は
いずれもこのルールで拒否される)。
"""

from __future__ import annotations

from foundation.errors import StateTransitionError
from foundation.result import Result

from .models import TaskStateEnum

ALLOWED_TRANSITIONS: dict[TaskStateEnum, frozenset[TaskStateEnum]] = {
    TaskStateEnum.CREATED: frozenset({TaskStateEnum.PLANNING, TaskStateEnum.FAILED, TaskStateEnum.CANCELLED}),
    TaskStateEnum.PLANNING: frozenset({TaskStateEnum.DESIGNING, TaskStateEnum.FAILED, TaskStateEnum.CANCELLED}),
    TaskStateEnum.DESIGNING: frozenset({TaskStateEnum.DESIGN_REVIEW, TaskStateEnum.FAILED, TaskStateEnum.CANCELLED}),
    TaskStateEnum.DESIGN_REVIEW: frozenset({TaskStateEnum.WAITING_APPROVAL, TaskStateEnum.FAILED, TaskStateEnum.CANCELLED}),
    TaskStateEnum.WAITING_APPROVAL: frozenset({TaskStateEnum.EXECUTING, TaskStateEnum.FAILED, TaskStateEnum.CANCELLED}),
    TaskStateEnum.EXECUTING: frozenset({TaskStateEnum.TESTING, TaskStateEnum.FAILED, TaskStateEnum.CANCELLED}),
    TaskStateEnum.TESTING: frozenset({TaskStateEnum.REVIEWING, TaskStateEnum.FAILED, TaskStateEnum.CANCELLED}),
    TaskStateEnum.REVIEWING: frozenset({TaskStateEnum.PR_CREATED, TaskStateEnum.FAILED, TaskStateEnum.CANCELLED}),
    TaskStateEnum.PR_CREATED: frozenset({TaskStateEnum.MERGED, TaskStateEnum.FAILED, TaskStateEnum.CANCELLED}),
    TaskStateEnum.MERGED: frozenset({TaskStateEnum.COMPLETED, TaskStateEnum.FAILED, TaskStateEnum.CANCELLED}),
    TaskStateEnum.COMPLETED: frozenset(),
    TaskStateEnum.FAILED: frozenset(),
    TaskStateEnum.CANCELLED: frozenset(),
}


def validate_transition(current: TaskStateEnum, new_state: TaskStateEnum) -> Result[bool]:
    """current から new_state への遷移が許可されているか検証する。

    許可されている場合 Result(success=True, value=True) を返す。
    許可されていない場合 Result(success=False, value=False, error=StateTransitionError(...)) を返す。
    """
    allowed = ALLOWED_TRANSITIONS.get(current)
    if allowed is None:
        return Result(
            success=False,
            value=False,
            error=StateTransitionError(f"unknown current state: {current!r}"),
        )
    if new_state not in allowed:
        return Result(
            success=False,
            value=False,
            error=StateTransitionError(f"transition from {current.value} to {new_state.value} is not allowed"),
        )
    return Result(success=True, value=True)
