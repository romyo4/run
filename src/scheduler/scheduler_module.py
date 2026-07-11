"""Scheduler (M14) 本体(IS14 4.1節)。

`BaseModule` を継承し、公開インターフェース `schedule()`/`trigger()`/`retry()`/`status()` を
実装する。Workflowの起動管理のみを担当し、要件分析・設計・コード生成・テスト・レビュー・
Pull Request作成・GitHub操作・Workflowの内容/Execution Plan/Design Documentの変更は
一切行わない(設計書1./4.1/4.2)。

責務外操作の禁止: 本モジュールはCommand Routerの公開インターフェースのうち `receive()` のみを
`CommandRouterClient`(Protocol)経由で呼び出し、具象クラスをimportしない。依存方向は
Scheduler→Command Routerの一方向のみ(Design Freeze監査確定事項)。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from foundation.base_module import BaseModule
from foundation.errors import FoundationError
from foundation.interfaces import ConfigurationClient
from foundation.logger import get_logger
from foundation.result import Result
from foundation.utils import generate_id, utc_now

from .command_router_client import CommandRouterAdapter, CommandRouterClient
from .exceptions import InvalidScheduleDefinitionError, SchedulerError, UnknownWorkflowError
from .execution_queue import ExecutionQueue
from .history_recorder import HistoryRecorder
from .logging_utils import log_execution
from .models import (
    Event,
    ExecutionHistory,
    ExecutionRequest,
    ExecutionResultStatus,
    FailedExecution,
    RetryRequest,
    ScheduleDefinition,
    ScheduledWorkflow,
    ScheduleFrequency,
    ScheduleStatus,
    TriggerType,
    WorkflowRunState,
)
from .retry_manager import RetryManager

MODULE_NAME = "scheduler"

_STATE_BY_RESULT: dict[ExecutionResultStatus, WorkflowRunState] = {
    ExecutionResultStatus.RUNNING: WorkflowRunState.RUNNING,
    ExecutionResultStatus.SUCCESS: WorkflowRunState.SUCCEEDED,
    ExecutionResultStatus.FAILURE: WorkflowRunState.FAILED,
    ExecutionResultStatus.RETRY_SCHEDULED: WorkflowRunState.PENDING,
    ExecutionResultStatus.RETRY_LIMIT_EXCEEDED: WorkflowRunState.RETRY_LIMIT_EXCEEDED,
}


class SchedulerModule(BaseModule):
    """手動/定期/イベント起動を受け付け、Execution RequestをCommand Routerへ引き渡す。"""

    def __init__(
        self,
        command_router_client: CommandRouterClient,
        configuration_client: ConfigurationClient,
        execution_queue: ExecutionQueue | None = None,
        retry_manager: RetryManager | None = None,
        history_recorder: HistoryRecorder | None = None,
    ) -> None:
        self._command_router_adapter = CommandRouterAdapter(command_router_client)
        self._configuration_client = configuration_client
        self._execution_queue = execution_queue if execution_queue is not None else ExecutionQueue()
        self._retry_manager = retry_manager if retry_manager is not None else RetryManager()
        self._history_recorder = history_recorder if history_recorder is not None else HistoryRecorder()
        self._logger = get_logger(MODULE_NAME)

        self._schedules: dict[str, ScheduledWorkflow] = {}
        self._known_workflows: set[str] = set()
        self._requests_by_id: dict[str, ExecutionRequest] = {}

    def name(self) -> str:
        return MODULE_NAME

    def health_check(self) -> Result[bool]:
        return Result(success=True, value=True, error=None)

    # ------------------------------------------------------------------
    # 3.5 schedule()
    # ------------------------------------------------------------------

    def schedule(self, definition: ScheduleDefinition) -> Result[ScheduledWorkflow]:
        """Schedule Definitionを登録し、Scheduled Workflowを返す。(3.5 schedule())"""
        try:
            if definition.frequency is ScheduleFrequency.CRON and not definition.cron_expression:
                return Result(
                    success=False,
                    value=None,
                    error=InvalidScheduleDefinitionError("cron_expression is required when frequency is CRON"),
                )

            scheduled_workflow = ScheduledWorkflow(
                schedule_id=generate_id(),
                workflow_id=definition.workflow_id,
                definition=definition,
                created_at=utc_now(),
                next_run_at=self._compute_next_run_at(definition),
                enabled=True,
            )
            self._schedules[scheduled_workflow.schedule_id] = scheduled_workflow
            self._known_workflows.add(definition.workflow_id)
            return Result(success=True, value=scheduled_workflow, error=None)
        except FoundationError as exc:
            return Result(success=False, value=None, error=exc)
        except Exception as exc:  # noqa: BLE001 - 呼び出し元へ例外を送出しない(5.2)
            return Result(success=False, value=None, error=SchedulerError(str(exc)))

    # ------------------------------------------------------------------
    # 3.5 trigger()
    # ------------------------------------------------------------------

    def trigger(self, event: Event) -> Result[ExecutionRequest]:
        """手動/定期/イベントいずれかのEventを受けてExecution Requestを生成し、

        Command Routerへ引き渡す。同一Workflowが実行中の場合は起動しない(4.4)。(3.5 trigger())
        """
        try:
            request = ExecutionRequest(
                request_id=generate_id(),
                workflow_id=event.workflow_id,
                trigger_type=event.trigger_type,
                source=event.source,
                requested_at=event.occurred_at,
                payload=dict(event.payload),
                retry_count=0,
            )
            self._requests_by_id[request.request_id] = request

            enqueue_result = self._execution_queue.try_enqueue(request)
            if not enqueue_result.success:
                # 4.4 制約: 実行中の場合は新規Execution Requestを生成しない(既に生成済みの
                # requestオブジェクトはCommand Routerへ引き渡さない)。
                return Result(success=False, value=None, error=enqueue_result.error)

            self._known_workflows.add(event.workflow_id)
            started_at = utc_now()

            submit_result = self._command_router_adapter.submit(request)

            if not submit_result.success:
                # Command Router呼び出し失敗時はキューを解放し、失敗履歴を記録する(5.2)。
                self._execution_queue.mark_finished(event.workflow_id)
                history = self._build_history(
                    request=request,
                    execution_result=ExecutionResultStatus.FAILURE,
                    started_at=started_at,
                    finished_at=utc_now(),
                )
                self._record_and_log(history)
                return Result(success=False, value=None, error=submit_result.error)

            history = self._build_history(
                request=request,
                execution_result=ExecutionResultStatus.RUNNING,
                started_at=started_at,
                finished_at=None,
            )
            self._record_and_log(history)
            return Result(success=True, value=request, error=None)
        except FoundationError as exc:
            return Result(success=False, value=None, error=exc)
        except Exception as exc:  # noqa: BLE001 - 呼び出し元へ例外を送出しない(5.2)
            return Result(success=False, value=None, error=SchedulerError(str(exc)))

    # ------------------------------------------------------------------
    # 3.5 retry()
    # ------------------------------------------------------------------

    def retry(self, failed_execution: FailedExecution) -> Result[RetryRequest]:
        """失敗した実行のリトライ要求を生成する。最大3回を超える場合は失敗として記録する(4.3)。

        (3.5 retry())
        """
        try:
            self._known_workflows.add(failed_execution.workflow_id)
            result = self._retry_manager.next_retry(failed_execution)

            if not result.success:
                # 超過時: 失敗として確定させ、RETRY_LIMIT_EXCEEDEDのExecutionHistoryを記録する。
                original_request = self._requests_by_id.get(failed_execution.request_id)
                trigger_type = original_request.trigger_type if original_request else TriggerType.EVENT
                history = ExecutionHistory(
                    history_id=generate_id(),
                    workflow_id=failed_execution.workflow_id,
                    request_id=failed_execution.request_id,
                    trigger_type=trigger_type,
                    execution_result=ExecutionResultStatus.RETRY_LIMIT_EXCEEDED,
                    retry_count=failed_execution.retry_count,
                    started_at=failed_execution.failed_at,
                    finished_at=utc_now(),
                    duration_seconds=None,
                )
                self._record_and_log(history)
                return Result(success=False, value=None, error=result.error)

            return result
        except FoundationError as exc:
            return Result(success=False, value=None, error=exc)
        except Exception as exc:  # noqa: BLE001 - 呼び出し元へ例外を送出しない(5.2)
            return Result(success=False, value=None, error=SchedulerError(str(exc)))

    # ------------------------------------------------------------------
    # 3.5 status()
    # ------------------------------------------------------------------

    def status(self, workflow_id: str) -> Result[ScheduleStatus]:
        """Workflow IDに対応する現在のSchedule Statusを返す。(3.5 status())"""
        try:
            if workflow_id not in self._known_workflows:
                return Result(
                    success=False,
                    value=None,
                    error=UnknownWorkflowError(f"unknown workflow_id: {workflow_id}"),
                )

            is_running = self._execution_queue.is_running(workflow_id)
            retry_count = self._retry_manager.get_retry_count(workflow_id)
            last_history = self._history_recorder.latest(workflow_id)

            status = ScheduleStatus(
                workflow_id=workflow_id,
                state=self._resolve_state(is_running, last_history),
                is_running=is_running,
                retry_count=retry_count,
                last_history=last_history,
                updated_at=utc_now(),
            )
            return Result(success=True, value=status, error=None)
        except FoundationError as exc:
            return Result(success=False, value=None, error=exc)
        except Exception as exc:  # noqa: BLE001 - 呼び出し元へ例外を送出しない(5.2)
            return Result(success=False, value=None, error=SchedulerError(str(exc)))

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_state(is_running: bool, last_history: ExecutionHistory | None) -> WorkflowRunState:
        if is_running:
            return WorkflowRunState.RUNNING
        if last_history is None:
            return WorkflowRunState.IDLE
        return _STATE_BY_RESULT.get(last_history.execution_result, WorkflowRunState.IDLE)

    @staticmethod
    def _build_history(
        *,
        request: ExecutionRequest,
        execution_result: ExecutionResultStatus,
        started_at: datetime,
        finished_at: datetime | None,
    ) -> ExecutionHistory:
        duration_seconds = (finished_at - started_at).total_seconds() if finished_at is not None else None
        return ExecutionHistory(
            history_id=generate_id(),
            workflow_id=request.workflow_id,
            request_id=request.request_id,
            trigger_type=request.trigger_type,
            execution_result=execution_result,
            retry_count=request.retry_count,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration_seconds,
        )

    def _record_and_log(self, history: ExecutionHistory) -> None:
        self._history_recorder.record(history)
        log_execution(
            self._logger,
            workflow_id=history.workflow_id,
            trigger_type=history.trigger_type.value,
            execution_result=history.execution_result.value,
            retry_count=history.retry_count,
            duration_seconds=history.duration_seconds,
            timestamp=history.started_at,
        )

    @staticmethod
    def _compute_next_run_at(definition: ScheduleDefinition) -> datetime | None:
        """DAILY/WEEKLY/MONTHLYはtime_of_day("HH:MM")から次回実行時刻を概算する。

        CRONは標準ライブラリのみでの厳密なcron式解析を行わない(MVP範囲外)ため、
        next_run_atはNoneとする。time_of_dayが未設定/不正な場合もNoneを返す。
        """
        if definition.frequency is ScheduleFrequency.CRON:
            return None
        if not definition.time_of_day:
            return None

        try:
            hour_str, minute_str = definition.time_of_day.split(":", maxsplit=1)
            hour, minute = int(hour_str), int(minute_str)
        except (ValueError, AttributeError):
            return None

        now = utc_now()
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        if definition.frequency is ScheduleFrequency.DAILY:
            if candidate <= now:
                candidate += timedelta(days=1)
            return candidate

        if definition.frequency is ScheduleFrequency.WEEKLY:
            if definition.day_of_week is None:
                return None
            days_ahead = (definition.day_of_week - candidate.weekday()) % 7
            candidate += timedelta(days=days_ahead)
            if candidate <= now:
                candidate += timedelta(days=7)
            return candidate

        if definition.frequency is ScheduleFrequency.MONTHLY:
            if definition.day_of_month is None:
                return None
            candidate = SchedulerModule._next_monthly_candidate(candidate, definition.day_of_month, now)
            return candidate

        return None

    @staticmethod
    def _next_monthly_candidate(candidate: datetime, day_of_month: int, now: datetime) -> datetime:
        def _with_day(base: datetime, day: int) -> datetime | None:
            try:
                return base.replace(day=day)
            except ValueError:
                return None

        result = _with_day(candidate, day_of_month)
        if result is None or result <= now:
            year = candidate.year + (1 if candidate.month == 12 else 0)
            month = 1 if candidate.month == 12 else candidate.month + 1
            next_month_base = candidate.replace(year=year, month=month)
            result = _with_day(next_month_base, day_of_month)
        return result if result is not None else candidate
