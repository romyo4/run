"""Scheduler (M14) 固有のdataclass/Enum定義(IS14 3節)。

Foundation `F01 Domain Model` の `Workflow`(`id`/`created_at`/`updated_at`/`metadata`)を
そのまま参照し、Scheduler側で `Workflow` を再定義しない。ここではWorkflowを
`workflow_id: str` の外部キーとして参照するだけの、Scheduler固有の入出力型のみを定義する。

全dataclassは `frozen=True` とし、Schedulerが受け取った入力値を内部で書き換えないことを
型レベルで担保する(IS14 3節 補足 / 設計書4.2)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from foundation.errors import ValidationError


class TriggerType(str, Enum):
    MANUAL = "MANUAL"
    SCHEDULED = "SCHEDULED"
    EVENT = "EVENT"


class ScheduleFrequency(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    CRON = "CRON"


class EventType(str, Enum):
    PULL_REQUEST_MERGED = "PULL_REQUEST_MERGED"
    WORKFLOW_COMPLETED = "WORKFLOW_COMPLETED"
    WEBHOOK_RECEIVED = "WEBHOOK_RECEIVED"
    TIMER = "TIMER"


class ExecutionResultStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    RETRY_LIMIT_EXCEEDED = "RETRY_LIMIT_EXCEEDED"


class WorkflowRunState(str, Enum):
    IDLE = "IDLE"
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RETRY_LIMIT_EXCEEDED = "RETRY_LIMIT_EXCEEDED"


# --- 3.5 公開インターフェースの入力型 -----------------------------------


@dataclass(frozen=True)
class ScheduleDefinition:
    """schedule() の入力。定期実行/Cron実行の定義。"""

    workflow_id: str
    frequency: ScheduleFrequency
    cron_expression: str | None = None  # frequency == CRON の場合に必須
    time_of_day: str | None = None  # "HH:MM"。DAILY/WEEKLY/MONTHLYで使用
    day_of_week: int | None = None  # 0=Mon〜6=Sun。WEEKLYで使用
    day_of_month: int | None = None  # 1-31。MONTHLYで使用
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ManualRequest:
    """手動起動(Slack/Discord/CLI/API)の入力。trigger()呼び出し前にEventへ変換される。"""

    workflow_id: str
    source: str  # "slack" | "discord" | "cli" | "api"
    requested_by: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Event:
    """trigger() の入力。手動/定期/イベントいずれの起動要求も本型に正規化して渡す。"""

    workflow_id: str
    trigger_type: TriggerType
    source: str  # 例: "slack", "scheduler", "github_webhook"
    occurred_at: datetime
    event_type: EventType | None = None  # trigger_type == EVENT の場合に設定
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.trigger_type is TriggerType.EVENT and self.event_type is None:
            raise ValidationError("event_type is required when trigger_type is EVENT")


@dataclass(frozen=True)
class FailedExecution:
    """retry() の入力。"""

    request_id: str
    workflow_id: str
    failure_reason: str
    retry_count: int
    failed_at: datetime


# --- 3.4 成果物(公開インターフェースの出力型) --------------------------


@dataclass(frozen=True)
class ScheduledWorkflow:
    """schedule() の出力。"""

    schedule_id: str
    workflow_id: str
    definition: ScheduleDefinition
    created_at: datetime
    next_run_at: datetime | None
    enabled: bool = True


@dataclass(frozen=True)
class ExecutionRequest:
    """trigger() の出力。Command Routerへ渡す実行要求。"""

    request_id: str
    workflow_id: str
    trigger_type: TriggerType
    source: str
    requested_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0


@dataclass(frozen=True)
class RetryRequest:
    """retry() の出力。"""

    retry_request_id: str
    original_request_id: str
    workflow_id: str
    retry_count: int
    requested_at: datetime


@dataclass(frozen=True)
class ExecutionHistory:
    """実行履歴1件分。"""

    history_id: str
    workflow_id: str
    request_id: str
    trigger_type: TriggerType
    execution_result: ExecutionResultStatus
    retry_count: int
    started_at: datetime
    finished_at: datetime | None
    duration_seconds: float | None


@dataclass(frozen=True)
class ScheduleStatus:
    """status() の出力。"""

    workflow_id: str
    state: WorkflowRunState
    is_running: bool
    retry_count: int
    last_history: ExecutionHistory | None
    updated_at: datetime
