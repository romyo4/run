"""Planner (M06) 固有のdataclass定義(IS06 3節)。

Foundationの `Task` / `SubTask` / `Knowledge` / `Context` を利用してPlanner固有の
成果物データ構造を定義する。業務ロジックはここに含めない(planner.pyの責務)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from foundation.types import Context, Knowledge, SubTask, Task


class Priority(str, Enum):
    """M06 3.4節: Taskごとに付与する優先度。"""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class NormalizedRequest:
    """analyze() の入力。M06 3.1節の入力項目を集約したもの。"""

    workflow_id: str
    command: str
    request_text: str
    knowledge: list[Knowledge] = field(default_factory=list)
    project_context: Context | None = None


@dataclass
class Requirement:
    """analyze() の出力。M06 3.2節で抽出される5項目を保持する。

    task: Foundationの Task Domain(id/created_at/updated_at/metadataを提供)。
          Planner固有属性は本クラスのフィールドとして追加する(F01の規約に準拠)。
    """

    task: Task
    objective: str  # 目的
    background: str  # 背景
    constraints: list[str]  # 制約
    deliverable: str  # 成果物
    priority: Priority  # 優先度


@dataclass
class PlannerSubTask:
    """create_tasks() / prioritize() が扱うTask Listの1要素。
    M06 3.3節(Task分解)・3.4節(優先順位)に対応する。

    subtask: FoundationのSubTask Domain(id/created_at/updated_at/metadataを提供)。
    """

    subtask: SubTask
    order: int  # Task1, Task2... の並び順
    title: str  # 例: "現状分析"
    description: str
    depends_on: list[str] = field(default_factory=list)  # 依存するSubTask.id一覧
    priority: Priority | None = None  # create_tasks()時点ではNone。prioritize()で確定する。


@dataclass
class ExecutionPlan:
    """create_execution_plan() の出力。M06 3.5節の成果物。

    id/created_at/updated_at/metadata はF01共通属性の命名規約に準拠する
    (Foundation Domain一覧には存在しない、Planner固有の成果物)。
    id が設計書上の「Plan ID」に相当する。
    """

    id: str
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]
    objective: str
    task_list: list[PlannerSubTask]
    dependencies: dict[str, list[str]]  # SubTask.id -> 依存するSubTask.id一覧(集約ビュー)
    expected_output: str
