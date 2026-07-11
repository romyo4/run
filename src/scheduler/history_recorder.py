"""実行履歴記録(IS14 4.5節)。Execution Historyの記録・参照のみを行う。"""

from __future__ import annotations

from collections import defaultdict

from foundation.result import Result

from .models import ExecutionHistory


class HistoryRecorder:
    def __init__(self) -> None:
        self._history: dict[str, list[ExecutionHistory]] = defaultdict(list)

    def record(self, history: ExecutionHistory) -> Result[None]:
        self._history[history.workflow_id].append(history)
        return Result(success=True, value=None, error=None)

    def latest(self, workflow_id: str) -> ExecutionHistory | None:
        entries = self._history.get(workflow_id)
        if not entries:
            return None
        return entries[-1]

    def all_for(self, workflow_id: str) -> list[ExecutionHistory]:
        return list(self._history.get(workflow_id, []))
