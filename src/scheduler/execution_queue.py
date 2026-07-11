"""実行キュー(IS14 4.3節)。

MVPでは単一プロセス内・単一キューに限定し、同一Workflowの重複起動を禁止する
(設計書4.4 単一実行)。分散キュー・優先度・ワーカープール等は実装しない。
"""

from __future__ import annotations

from foundation.result import Result

from .exceptions import DuplicateWorkflowExecutionError
from .models import ExecutionRequest


class ExecutionQueue:
    """MVPでは単一キュー。同一Workflowの重複起動を禁止する(4.4)。"""

    def __init__(self) -> None:
        self._running: set[str] = set()
        self._queue: list[ExecutionRequest] = []

    def try_enqueue(self, request: ExecutionRequest) -> Result[bool]:
        """workflow_idが実行中でなければキューに積みTrueを返す。

        実行中であればResult(success=False, error=DuplicateWorkflowExecutionError)を返す。
        """
        if request.workflow_id in self._running:
            return Result(
                success=False,
                value=False,
                error=DuplicateWorkflowExecutionError(f"workflow_id={request.workflow_id} is already running"),
            )

        self._running.add(request.workflow_id)
        self._queue.append(request)
        return Result(success=True, value=True, error=None)

    def mark_running(self, workflow_id: str) -> None:
        self._running.add(workflow_id)

    def mark_finished(self, workflow_id: str) -> None:
        self._running.discard(workflow_id)

    def is_running(self, workflow_id: str) -> bool:
        return workflow_id in self._running
