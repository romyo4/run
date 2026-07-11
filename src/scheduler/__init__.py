"""Scheduler(M14)パッケージ公開API。

SchedulerModule・データクラス・固有例外を再エクスポートする(IS14 2節)。
"""

from __future__ import annotations

from scheduler.command_router_client import CommandRouterAdapter, CommandRouterClient, RawCommand
from scheduler.exceptions import (
    CommandRouterDispatchError,
    DuplicateWorkflowExecutionError,
    InvalidScheduleDefinitionError,
    RetryLimitExceededError,
    SchedulerError,
    UnknownWorkflowError,
)
from scheduler.execution_queue import ExecutionQueue
from scheduler.history_recorder import HistoryRecorder
from scheduler.models import (
    Event,
    EventType,
    ExecutionHistory,
    ExecutionRequest,
    ExecutionResultStatus,
    FailedExecution,
    ManualRequest,
    RetryRequest,
    ScheduleDefinition,
    ScheduledWorkflow,
    ScheduleFrequency,
    ScheduleStatus,
    TriggerType,
    WorkflowRunState,
)
from scheduler.retry_manager import RetryManager
from scheduler.scheduler_module import SchedulerModule

__all__ = [
    "SchedulerModule",
    "CommandRouterAdapter",
    "CommandRouterClient",
    "RawCommand",
    "ExecutionQueue",
    "RetryManager",
    "HistoryRecorder",
    "Event",
    "EventType",
    "ExecutionHistory",
    "ExecutionRequest",
    "ExecutionResultStatus",
    "FailedExecution",
    "ManualRequest",
    "RetryRequest",
    "ScheduleDefinition",
    "ScheduledWorkflow",
    "ScheduleFrequency",
    "ScheduleStatus",
    "TriggerType",
    "WorkflowRunState",
    "SchedulerError",
    "InvalidScheduleDefinitionError",
    "DuplicateWorkflowExecutionError",
    "RetryLimitExceededError",
    "UnknownWorkflowError",
    "CommandRouterDispatchError",
]
