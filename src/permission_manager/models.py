"""Permission Manager (M04) のドメイン型定義。

Module / Operation / Effect の3つのEnumと PermissionEntry dataclass を定義する。
Foundation `types.py` のDomain Modelは変更・追加せず、本モジュール固有の型として独立定義する
(IS04 2. ファイル構成 / models.py)。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Module(str, Enum):
    """権限判定の対象となる呼び出し元モジュール(設計書1. 適用対象 / 3.4)。"""

    PLANNER = "Planner"
    DESIGNER = "Designer"
    EXECUTOR = "Executor"
    REVIEWER = "Reviewer"
    SCHEDULER = "Scheduler"
    KNOWLEDGE_MANAGER = "Knowledge Manager"
    COMMAND_ROUTER = "Command Router"


class Operation(str, Enum):
    """Moduleが実行しようとする操作(設計書3.4)。"""

    EXECUTION_PLAN_CREATE = "ExecutionPlan作成"
    DESIGN_CREATE = "Design作成"
    PULL_REQUEST_CREATE = "Pull Request作成"
    REVIEW_CREATE = "Review作成"
    WORKFLOW_START = "Workflow開始"
    KNOWLEDGE_UPDATE = "Knowledge更新"
    COMMAND_DISPATCH = "Command振り分け"


class Effect(str, Enum):
    """Module × Operation の組み合わせに対する判定結果(設計書3.2)。"""

    ALLOW = "Allow"
    DENY = "Deny"


@dataclass(frozen=True)
class PermissionEntry:
    """Permissionの管理単位(設計書3.2: Module / Operation / Allow-Deny)。"""

    module: Module
    operation: Operation
    effect: Effect
