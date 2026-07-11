"""状態の保持・履歴保存・排他制御を担当するストア層(IS01 4.3 / 設計書2.1・4.3)。

MVP範囲として単一プロセス内のインメモリ保持とする(IS01 8節: 分散State Store対象外)。
排他制御は task_id ごとに threading.Lock を割り当てる方式とし、ロック辞書自体への
アクセスは別途1本のロックで保護する。
"""

from __future__ import annotations

import threading

from foundation.errors import ConfigurationError, NotFoundError
from foundation.interfaces import ConfigurationClient
from foundation.result import Result

from .exceptions import StateLockTimeoutError
from .models import TaskState, TaskStateEnum


class StateStore:
    """TaskStateの保持・履歴保存・排他制御を担当する。"""

    def __init__(self, config_client: ConfigurationClient) -> None:
        # 永続化先(DB/ファイル)の接続設定をF03経由で取得する。MVPでは実体としては
        # インメモリ保持のみを行うが、設定取得自体の失敗(F03アクセス失敗)は
        # ConfigurationErrorとしてfail-fastする(設計書5.2 F03整合性)。
        result = config_client.get("state_manager", "backend_path")
        if not result.success:
            message = getattr(result.error, "message", None) or "failed to resolve state_manager backend_path"
            raise ConfigurationError(message)
        self._backend_path = result.value

        self._states: dict[str, TaskState] = {}
        self._history: dict[str, list[TaskState]] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def get_latest(self, task_id: str) -> Result[TaskState]:
        """task_idに対応する最新のTaskStateを返す。存在しない場合はNotFoundError。"""
        state = self._states.get(task_id)
        if state is None:
            return Result(success=False, error=NotFoundError(f"task_id not found: {task_id}"))
        return Result(success=True, value=state)

    def get_history(self, task_id: str) -> Result[list[TaskState]]:
        """task_idに対応する状態変更履歴を時系列(古い→新しい)で返す。"""
        history = self._history.get(task_id)
        if history is None:
            return Result(success=False, error=NotFoundError(f"task_id not found: {task_id}"))
        return Result(success=True, value=list(history))

    def append(self, state: TaskState) -> Result[TaskState]:
        """TaskStateを最新状態として登録し、履歴に追記する。"""
        self._states[state.task_id] = state
        self._history.setdefault(state.task_id, []).append(state)
        return Result(success=True, value=state)

    def list_running(self, terminal_states: frozenset[TaskStateEnum]) -> Result[list[TaskState]]:
        """終端状態(terminal_states)以外の状態にある全TaskStateを返す。"""
        running = [state for state in self._states.values() if state.current_state not in terminal_states]
        return Result(success=True, value=running)

    def acquire_lock(self, task_id: str, timeout_seconds: float) -> Result[bool]:
        """task_id単位の排他ロックを取得する。取得できない場合はStateLockTimeoutError。"""
        with self._locks_guard:
            lock = self._locks.setdefault(task_id, threading.Lock())
        acquired = lock.acquire(timeout=timeout_seconds)
        if not acquired:
            return Result(
                success=False,
                error=StateLockTimeoutError(f"lock acquisition timed out for task_id: {task_id}"),
            )
        return Result(success=True, value=True)

    def release_lock(self, task_id: str) -> None:
        """task_idのロックを解放する。"""
        with self._locks_guard:
            lock = self._locks.get(task_id)
        if lock is not None and lock.locked():
            lock.release()
