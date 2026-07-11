"""TaskQueueManager(IS02 4章)。

Task Queueの公開インターフェース7関数(enqueue/dequeue/peek/cancel/retry/reprioritize/list)と、
排他制御・依存解決・デッドロック検知・障害復旧などの内部処理を実装する。

Task Queueは「キュー管理のみ」を担当し、Task内容の解釈・状態の正本管理(State Managerの責務)・
Workflow起動判断は行わない。State Managerとの結合は、Foundation(F03)が提供する
`ConfigurationClient`のような抽象インターフェース経由に限定し、具体クラスへは一切依存しない。
"""

from __future__ import annotations

import copy
import threading
import uuid
from datetime import UTC, datetime
from typing import Any

from foundation.base_module import BaseModule
from foundation.errors import FoundationError
from foundation.interfaces import ConfigurationClient
from foundation.logger import get_logger
from foundation.result import Result
from foundation.types import SubTask, Task
from task_queue.errors import (
    DeadlockDetectedError,
    InvalidQueueTransitionError,
    MaxRetryExceededError,
    QueueCorruptionError,
    QueueNotFoundError,
    TaskNotFoundError,
    WorkerFailureError,
)
from task_queue.models import QueueStatus, TaskPriority, TaskQueue

_MODULE_NAME = "task_queue"

# Configuration(F03)から取得するキー名(設計書5.2/IS02 4.4)。
_CONFIG_KEY_MAX_PARALLEL_EXECUTIONS = "max_parallel_executions"
_CONFIG_KEY_MAX_RETRY_COUNT = "max_retry_count"
_CONFIG_KEY_WORKER_TIMEOUT_SECONDS = "worker_timeout_seconds"

# Configuration Manager未接続・値未設定時のフォールバック既定値。
# 設計書・IS02にフォールバック値の明記はないため、本実装での安全側の補完値とする。
_DEFAULT_MAX_PARALLEL_EXECUTIONS = 1
_DEFAULT_MAX_RETRY_COUNT = 3
_DEFAULT_WORKER_TIMEOUT_SECONDS = 300.0

_DEFAULT_QUEUE_NAME = "default"

_TERMINAL_STATUSES = (QueueStatus.COMPLETED, QueueStatus.CANCELLED)
_REPRIORITIZE_FORBIDDEN_STATUSES = (
    QueueStatus.RUNNING,
    QueueStatus.COMPLETED,
    QueueStatus.FAILED,
    QueueStatus.CANCELLED,
)
_RETRYABLE_STATUSES = (QueueStatus.FAILED, QueueStatus.RETRY_WAITING)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class TaskQueueManager(BaseModule):
    """Task Queue の公開インターフェースを提供する。BaseModule(F02)を継承する。"""

    def __init__(self, config_client: ConfigurationClient) -> None:
        self._config_client = config_client
        self._logger = get_logger(_MODULE_NAME)
        self._lock = threading.Lock()
        self._tasks: dict[str, TaskQueue] = {}
        self._locked_task_ids: set[str] = set()

    # ------------------------------------------------------------------
    # BaseModule(F02)
    # ------------------------------------------------------------------

    def name(self) -> str:
        return _MODULE_NAME

    def health_check(self) -> Result[bool]:
        with self._lock:
            healthy = all(self._is_consistent(tq) for tq in self._tasks.values())
        return Result(success=True, value=healthy)

    # ------------------------------------------------------------------
    # 公開インターフェース(設計書3.5、IS02 4.2)
    # ------------------------------------------------------------------

    def enqueue(self, task: Task | SubTask) -> Result[TaskQueue]:
        queue_name = str(task.metadata.get("queue_name", _DEFAULT_QUEUE_NAME))
        priority = self._coerce_priority(task.metadata.get("priority"))
        depends_on = list(task.metadata.get("depends_on", []))

        with self._lock:
            if self._has_dependency_cycle(task.id, depends_on):
                error = DeadlockDetectedError(f"circular dependency detected for task_id={task.id}")
                self._log_error("enqueue", task.id, error)
                return Result(success=False, error=error)

            status = QueueStatus.WAITING_DEPENDENCY if depends_on else QueueStatus.READY
            task_queue = TaskQueue(
                task_id=task.id,
                priority=priority,
                queue_name=queue_name,
                status=status,
                created_at=task.created_at,
                depends_on=depends_on,
            )
            self._tasks[task.id] = task_queue
            self._logger.info(
                "event=enqueue task_id=%s queue_name=%s priority=%s status=%s",
                task.id,
                queue_name,
                priority.name,
                status.value,
            )
            return Result(success=True, value=copy.deepcopy(task_queue))

    def dequeue(self, queue_name: str) -> Result[TaskQueue]:
        with self._lock:
            if not self._queue_exists(queue_name):
                error = QueueNotFoundError(f"queue '{queue_name}' does not exist")
                self._log_error("dispatch", None, error, queue_name=queue_name)
                return Result(success=False, error=error)

            max_parallel = self._get_config_int(_CONFIG_KEY_MAX_PARALLEL_EXECUTIONS, _DEFAULT_MAX_PARALLEL_EXECUTIONS)
            if self._running_count(queue_name) >= max_parallel:
                error = TaskNotFoundError(f"queue '{queue_name}' reached max_parallel_executions={max_parallel}")
                self._log_error("dispatch", None, error, queue_name=queue_name)
                return Result(success=False, error=error)

            candidate = self._select_next_ready(queue_name)
            if candidate is None:
                error = TaskNotFoundError(f"no ready task available in queue '{queue_name}'")
                self._log_error("dispatch", None, error, queue_name=queue_name)
                return Result(success=False, error=error)

            if not self._is_consistent(candidate):
                error = QueueCorruptionError(f"task_id={candidate.task_id} has inconsistent status/data")
                self._log_error("dispatch", candidate.task_id, error, queue_name=queue_name)
                return Result(success=False, error=error)

            if not self._acquire_task_lock(candidate.task_id):
                error = TaskNotFoundError(f"task_id={candidate.task_id} is locked")
                self._log_error("dispatch", candidate.task_id, error, queue_name=queue_name)
                return Result(success=False, error=error)
            try:
                candidate.status = QueueStatus.RUNNING
                candidate.worker_id = f"W-{uuid.uuid4().hex[:8]}"
                candidate.started_at = _utc_now()
            finally:
                self._release_task_lock(candidate.task_id)

            self._logger.info(
                "event=dispatch task_id=%s queue_name=%s worker_id=%s from_status=%s to_status=%s",
                candidate.task_id,
                queue_name,
                candidate.worker_id,
                QueueStatus.READY.value,
                QueueStatus.RUNNING.value,
            )
            return Result(success=True, value=copy.deepcopy(candidate))

    def peek(self, queue_name: str) -> Result[TaskQueue]:
        with self._lock:
            if not self._queue_exists(queue_name):
                error = QueueNotFoundError(f"queue '{queue_name}' does not exist")
                return Result(success=False, error=error)

            candidate = self._select_next_ready(queue_name)
            if candidate is None:
                error = TaskNotFoundError(f"no ready task available in queue '{queue_name}'")
                return Result(success=False, error=error)

            if not self._is_consistent(candidate):
                error = QueueCorruptionError(f"task_id={candidate.task_id} has inconsistent status/data")
                self._log_error("peek", candidate.task_id, error, queue_name=queue_name)
                return Result(success=False, error=error)

            return Result(success=True, value=copy.deepcopy(candidate))

    def cancel(self, task_id: str) -> Result[bool]:
        with self._lock:
            task_queue = self._tasks.get(task_id)
            if task_queue is None:
                error = TaskNotFoundError(f"task_id={task_id} not found")
                return Result(success=False, error=error)

            if task_queue.status in _TERMINAL_STATUSES:
                return Result(success=True, value=False)

            if not self._acquire_task_lock(task_id):
                error = TaskNotFoundError(f"task_id={task_id} is locked")
                return Result(success=False, error=error)
            try:
                from_status = task_queue.status
                task_queue.status = QueueStatus.CANCELLED
                task_queue.finished_at = _utc_now()
            finally:
                self._release_task_lock(task_id)

            self._logger.info(
                "event=cancel task_id=%s from_status=%s to_status=%s",
                task_id,
                from_status.value,
                QueueStatus.CANCELLED.value,
            )
            return Result(success=True, value=True)

    def retry(self, task_id: str) -> Result[TaskQueue]:
        with self._lock:
            task_queue = self._tasks.get(task_id)
            if task_queue is None:
                error = TaskNotFoundError(f"task_id={task_id} not found")
                return Result(success=False, error=error)

            if task_queue.status not in _RETRYABLE_STATUSES:
                error = InvalidQueueTransitionError(
                    f"task_id={task_id} is in status={task_queue.status.value}; "
                    "retry is only allowed from Failed or RetryWaiting"
                )
                return Result(success=False, error=error)

            max_retry = self._get_config_int(_CONFIG_KEY_MAX_RETRY_COUNT, _DEFAULT_MAX_RETRY_COUNT)
            from_status = task_queue.status
            task_queue.retry_count += 1

            if task_queue.retry_count < max_retry:
                task_queue.status = (
                    QueueStatus.WAITING_DEPENDENCY
                    if task_queue.depends_on and not self._all_dependencies_completed(task_queue.depends_on)
                    else QueueStatus.QUEUED
                )
                task_queue.worker_id = None
                task_queue.started_at = None
                self._logger.info(
                    "event=retry task_id=%s retry_count=%s from_status=%s to_status=%s",
                    task_id,
                    task_queue.retry_count,
                    from_status.value,
                    task_queue.status.value,
                )
                return Result(success=True, value=copy.deepcopy(task_queue))

            task_queue.status = QueueStatus.FAILED
            error = MaxRetryExceededError(f"task_id={task_id} exceeded max_retry_count={max_retry}")
            self._log_error("retry", task_id, error)
            return Result(success=False, error=error)

    def reprioritize(self, task_id: str, priority: TaskPriority) -> Result[TaskQueue]:
        with self._lock:
            task_queue = self._tasks.get(task_id)
            if task_queue is None:
                error = TaskNotFoundError(f"task_id={task_id} not found")
                return Result(success=False, error=error)

            if task_queue.status in _REPRIORITIZE_FORBIDDEN_STATUSES:
                error = InvalidQueueTransitionError(
                    f"task_id={task_id} is in status={task_queue.status.value}; " "priority cannot be changed"
                )
                return Result(success=False, error=error)

            task_queue.priority = priority
            self._logger.info("event=reprioritize task_id=%s priority=%s", task_id, priority.name)
            return Result(success=True, value=copy.deepcopy(task_queue))

    def list(self, queue_name: str) -> Result[list[TaskQueue]]:
        with self._lock:
            items = [copy.deepcopy(tq) for tq in self._tasks.values() if tq.queue_name == queue_name]
            return Result(success=True, value=items)

    # ------------------------------------------------------------------
    # 内部処理(非公開、IS02 4.3)
    # ------------------------------------------------------------------

    def _resolve_dependencies(self, completed_task_id: str) -> None:
        """`completed_task_id`の完了を受けて、依存待ちタスクをReadyへ遷移させる。

        Task Queueは状態の正本を持たない(State Managerが正本)ため、
        「完了」の事実そのものはこのメソッドの呼び出し側が確定させる前提とする。
        """
        with self._lock:
            for task_queue in self._tasks.values():
                if (
                    task_queue.status == QueueStatus.WAITING_DEPENDENCY
                    and completed_task_id in task_queue.depends_on
                    and self._all_dependencies_completed(task_queue.depends_on)
                ):
                    task_queue.status = QueueStatus.READY
                    self._logger.info(
                        "event=dependency_resolved task_id=%s to_status=%s",
                        task_queue.task_id,
                        QueueStatus.READY.value,
                    )

    def _has_dependency_cycle(self, task_id: str, depends_on: list[str]) -> bool:
        visited: set[str] = set()
        stack: list[str] = list(depends_on)
        while stack:
            current = stack.pop()
            if current == task_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            dep_task = self._tasks.get(current)
            if dep_task is not None:
                stack.extend(dep_task.depends_on)
        return False

    def _acquire_task_lock(self, task_id: str) -> bool:
        if task_id in self._locked_task_ids:
            return False
        self._locked_task_ids.add(task_id)
        return True

    def _release_task_lock(self, task_id: str) -> None:
        self._locked_task_ids.discard(task_id)

    def _select_next_ready(self, queue_name: str) -> TaskQueue | None:
        candidates = [tq for tq in self._tasks.values() if tq.queue_name == queue_name and tq.status == QueueStatus.READY]
        if not candidates:
            return None
        candidates.sort(key=lambda tq: (tq.priority.value, tq.created_at))
        return candidates[0]

    def _running_count(self, queue_name: str) -> int:
        return sum(1 for tq in self._tasks.values() if tq.queue_name == queue_name and tq.status == QueueStatus.RUNNING)

    def _detect_stale_workers(self) -> list[str]:
        """Workerハートビート監視の代替実装(IS02 4.3参照)。

        設計書にはハートビート送信プロトコル自体の定義がないため、`started_at`と
        Configuration経由の`worker_timeout_seconds`の比較により、一定時間内に
        完了/失敗報告のないWorkerを異常とみなす(実装上の補完)。
        検知したタスクはRetryWaitingへ遷移させ、検知したtask_idの一覧を返す。
        """
        timeout_seconds = self._get_config_float(_CONFIG_KEY_WORKER_TIMEOUT_SECONDS, _DEFAULT_WORKER_TIMEOUT_SECONDS)
        stale_task_ids: list[str] = []
        with self._lock:
            now = _utc_now()
            for task_queue in self._tasks.values():
                if task_queue.status != QueueStatus.RUNNING or task_queue.started_at is None:
                    continue
                elapsed = (now - task_queue.started_at).total_seconds()
                if elapsed > timeout_seconds:
                    task_queue.status = QueueStatus.RETRY_WAITING
                    task_queue.worker_id = None
                    error = WorkerFailureError(
                        f"task_id={task_queue.task_id} worker timeout exceeded " f"({elapsed:.1f}s > {timeout_seconds:.1f}s)"
                    )
                    self._log_error("stale_worker", task_queue.task_id, error)
                    stale_task_ids.append(task_queue.task_id)
        return stale_task_ids

    # ------------------------------------------------------------------
    # 補助関数
    # ------------------------------------------------------------------

    def _queue_exists(self, queue_name: str) -> bool:
        return any(tq.queue_name == queue_name for tq in self._tasks.values())

    def _all_dependencies_completed(self, depends_on: list[str]) -> bool:
        return all(
            self._tasks.get(dep_id) is not None and self._tasks[dep_id].status == QueueStatus.COMPLETED
            for dep_id in depends_on
        )

    def _is_consistent(self, task_queue: TaskQueue) -> bool:
        if task_queue.status == QueueStatus.READY and (
            task_queue.worker_id is not None or task_queue.started_at is not None
        ):
            return False
        if task_queue.status == QueueStatus.RUNNING and (task_queue.worker_id is None or task_queue.started_at is None):
            return False
        return True

    @staticmethod
    def _coerce_priority(raw_priority: Any) -> TaskPriority:
        if isinstance(raw_priority, TaskPriority):
            return raw_priority
        if isinstance(raw_priority, int):
            return TaskPriority(raw_priority)
        if isinstance(raw_priority, str):
            return TaskPriority[raw_priority.upper()]
        return TaskPriority.NORMAL

    def _get_config_int(self, key: str, default: int) -> int:
        result = self._config_client.get(_MODULE_NAME, key)
        if result.success and isinstance(result.value, (int, float)):
            return int(result.value)
        return default

    def _get_config_float(self, key: str, default: float) -> float:
        result = self._config_client.get(_MODULE_NAME, key)
        if result.success and isinstance(result.value, (int, float)):
            return float(result.value)
        return default

    def _log_error(
        self,
        event: str,
        task_id: str | None,
        error: FoundationError,
        *,
        queue_name: str | None = None,
    ) -> None:
        self._logger.error(
            "event=error task_id=%s queue_name=%s error_code=%s detail=%s",
            task_id,
            queue_name,
            type(error).__name__,
            error.message,
        )
