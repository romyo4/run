"""Task Queue のデータモデル定義(設計書3.1/3.2/3.3節、IS02 3章)。

業務ロジックは持たない。キュー状態Enum・優先順位Enum・TaskQueue dataclassのみを定義する。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum


class QueueStatus(Enum):
    """キュー内部での実行制御状態(設計書3.1)。

    正式な状態遷移の正本はState Managerであり、本Enumはキュー内部の実行制御用。
    """

    QUEUED = "Queued"
    WAITING_DEPENDENCY = "WaitingDependency"
    READY = "Ready"
    RUNNING = "Running"
    RETRY_WAITING = "RetryWaiting"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


class TaskPriority(IntEnum):
    """優先順位(設計書3.3)。数値が小さいほど優先度が高い。同一優先度内はFIFO(created_at昇順)。"""

    EMERGENCY = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


@dataclass
class TaskQueue:
    """キュー内の1タスクを表すレコード(設計書3.2)。

    `task_id` はFoundation(F01)の`Task`/`SubTask` Domainの`id`を参照する値であり、
    Task Queueは`Task`/`SubTask`本体の内容を保持・解釈しない。
    """

    task_id: str
    priority: TaskPriority
    queue_name: str
    status: QueueStatus
    created_at: datetime
    depends_on: list[str] = field(default_factory=list)
    worker_id: str | None = None
    retry_count: int = 0
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
