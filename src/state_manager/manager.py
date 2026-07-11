"""State Manager (M01) 本体(IS01 4.2 / 設計書3.4)。

Task・SubTask・Workflow・Pull Request・Reviewの状態を一元管理する。状態遷移の
妥当性検証・履歴保存・実行中タスク管理・排他制御に責務を限定し、業務処理は行わない。
"""

from __future__ import annotations

from foundation.base_module import BaseModule
from foundation.errors import StateTransitionError, ValidationError
from foundation.interfaces import ConfigurationClient
from foundation.logger import get_logger
from foundation.result import Result
from foundation.utils import utc_now
from foundation.validation import require_non_empty, require_not_none

from .models import TERMINAL_STATES, TaskState, TaskStateEnum
from .store import StateStore
from .transitions import validate_transition

MODULE_NAME = "state_manager"

# ロック取得のデフォルトタイムアウト秒数。config_client経由で上書きできる。
DEFAULT_LOCK_TIMEOUT_SECONDS = 5.0

logger = get_logger(MODULE_NAME)


class StateManager(BaseModule):
    """タスク状態を一元管理するモジュール(設計書全体)。"""

    def __init__(self, config_client: ConfigurationClient) -> None:
        self._store = StateStore(config_client)
        self._lock_timeout_seconds = self._resolve_lock_timeout(config_client)

    @staticmethod
    def _resolve_lock_timeout(config_client: ConfigurationClient) -> float:
        result = config_client.get(MODULE_NAME, "lock_timeout_seconds")
        if result.success and isinstance(result.value, (int, float)) and result.value > 0:
            return float(result.value)
        return DEFAULT_LOCK_TIMEOUT_SECONDS

    # --- F02: BaseModule ---
    def name(self) -> str:
        return MODULE_NAME

    def health_check(self) -> Result[bool]:
        return Result(success=True, value=True)

    # --- 設計書3.4: 公開インターフェース ---
    def get_state(self, task_id: str) -> Result[TaskState]:
        """task_idに対応する最新のTaskStateを返す。存在しない場合はNotFoundError。"""
        try:
            require_non_empty(task_id, "task_id")
        except ValidationError as exc:
            return Result(success=False, error=exc)
        return self._store.get_latest(task_id)

    def transition(
        self,
        task_id: str,
        new_state: TaskStateEnum,
        *,
        updated_by: str = "system",
        reason: str | None = None,
    ) -> Result[TaskState]:
        """current_stateからnew_stateへの遷移を検証した上で状態を更新し、履歴に追記する。"""
        try:
            require_non_empty(task_id, "task_id")
            require_not_none(new_state, "new_state")
        except ValidationError as exc:
            return Result(success=False, error=exc)

        lock_result = self._store.acquire_lock(task_id, self._lock_timeout_seconds)
        if not lock_result.success:
            logger.error(
                "task_id=%s before=? after=%s updated_by=%s reason=%s error=%s",
                task_id,
                new_state.value,
                updated_by,
                reason,
                lock_result.error,
            )
            return Result(success=False, error=lock_result.error)

        try:
            current_result = self._store.get_latest(task_id)
            if not current_result.success:
                logger.warning(
                    "task_id=%s before=? after=%s updated_by=%s reason=%s error=%s",
                    task_id,
                    new_state.value,
                    updated_by,
                    reason,
                    current_result.error,
                )
                return Result(success=False, error=current_result.error)

            current = current_result.value
            assert current is not None

            validation_result = validate_transition(current.current_state, new_state)
            if not validation_result.success:
                logger.warning(
                    "task_id=%s before=%s after=%s updated_by=%s reason=%s error=%s",
                    task_id,
                    current.current_state.value,
                    new_state.value,
                    updated_by,
                    reason,
                    validation_result.error,
                )
                return Result(success=False, error=validation_result.error)

            new_record = TaskState(
                task_id=task_id,
                workflow_id=current.workflow_id,
                current_state=new_state,
                previous_state=current.current_state,
                updated_at=utc_now(),
                updated_by=updated_by,
                retry_count=current.retry_count,
                error_code=None,
                error_message=None,
                metadata=current.metadata,
            )
            append_result = self._store.append(new_record)
            logger.info(
                "task_id=%s before=%s after=%s updated_by=%s reason=%s",
                task_id,
                current.current_state.value,
                new_state.value,
                updated_by,
                reason,
            )
            return append_result
        finally:
            self._store.release_lock(task_id)

    def history(self, task_id: str) -> Result[list[TaskState]]:
        """task_idに対応する状態変更履歴を時系列(古い→新しい)で返す。"""
        try:
            require_non_empty(task_id, "task_id")
        except ValidationError as exc:
            return Result(success=False, error=exc)
        return self._store.get_history(task_id)

    def rollback(self, task_id: str) -> Result[TaskState]:
        """現在のTaskState.previous_stateへ状態を戻す。履歴には通常の遷移として追記される。"""
        try:
            require_non_empty(task_id, "task_id")
        except ValidationError as exc:
            return Result(success=False, error=exc)

        lock_result = self._store.acquire_lock(task_id, self._lock_timeout_seconds)
        if not lock_result.success:
            logger.error("task_id=%s rollback error=%s", task_id, lock_result.error)
            return Result(success=False, error=lock_result.error)

        try:
            current_result = self._store.get_latest(task_id)
            if not current_result.success:
                logger.warning("task_id=%s rollback error=%s", task_id, current_result.error)
                return Result(success=False, error=current_result.error)

            current = current_result.value
            assert current is not None

            if current.previous_state is None:
                error = StateTransitionError(f"no previous state to rollback for task_id: {task_id}")
                logger.warning(
                    "task_id=%s before=%s after=? updated_by=system reason=rollback error=%s",
                    task_id,
                    current.current_state.value,
                    error,
                )
                return Result(success=False, error=error)

            new_record = TaskState(
                task_id=task_id,
                workflow_id=current.workflow_id,
                current_state=current.previous_state,
                previous_state=current.current_state,
                updated_at=utc_now(),
                updated_by="system",
                retry_count=current.retry_count,
                error_code=current.error_code,
                error_message=current.error_message,
                metadata=current.metadata,
            )
            append_result = self._store.append(new_record)
            logger.info(
                "task_id=%s before=%s after=%s updated_by=system reason=rollback",
                task_id,
                current.current_state.value,
                current.previous_state.value,
            )
            return append_result
        finally:
            self._store.release_lock(task_id)

    def list_running(self) -> Result[list[TaskState]]:
        """終端状態(Completed/Failed/Cancelled)以外の状態にある全TaskStateを返す。"""
        return self._store.list_running(TERMINAL_STATES)
