"""State Manager (M01) のデータ構造定義(IS01 3章 / 設計書3.1・3.3)。

TaskStateEnum・TERMINAL_STATES・TaskState の定義のみを行う。バリデーションや
遷移ロジックはここに含めない(それぞれ transitions.py / manager.py の責務)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TaskStateEnum(str, Enum):
    """タスク状態(設計書3.1に定義された13状態)。"""

    CREATED = "Created"
    PLANNING = "Planning"
    DESIGNING = "Designing"
    DESIGN_REVIEW = "DesignReview"
    WAITING_APPROVAL = "WaitingApproval"
    EXECUTING = "Executing"
    TESTING = "Testing"
    REVIEWING = "Reviewing"
    PR_CREATED = "PRCreated"
    MERGED = "Merged"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


# 終端状態(これ以上の遷移を許可しない)
TERMINAL_STATES: frozenset[TaskStateEnum] = frozenset(
    {TaskStateEnum.COMPLETED, TaskStateEnum.FAILED, TaskStateEnum.CANCELLED}
)


@dataclass
class TaskState:
    """State Managerが管理する状態レコード(設計書3.3)。

    task_id は Foundation(F01) Task Domain の id と対応する。State Managerは
    Task自体の生成・内容管理は行わない。
    """

    task_id: str
    workflow_id: str | None
    current_state: TaskStateEnum
    previous_state: TaskStateEnum | None
    updated_at: datetime
    updated_by: str
    retry_count: int = 0
    error_code: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
