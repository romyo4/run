"""Planner (M06) 本体(IS06 4節)。

自然言語の要求(Normalized Request)を分析し、実行可能な Execution Plan へ
変換する。要求分析・Task分解・優先順位付け・Execution Plan生成の4処理に
責務を限定し、システム設計・コード生成・Pull Request作成・レビューは一切
行わない(M06 4.1〜4.3節)。Knowledgeは参照のみ許可し、書き換えは行わない
(M06 4.4節)。

責務外操作の禁止: 本モジュールは foundation.* と planner.types のみに依存し、
GitHub API・コード生成・レビュー判定に関するクライアントは一切importしない。
"""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from foundation.base_module import BaseModule
from foundation.errors import ValidationError
from foundation.interfaces import ConfigurationClient
from foundation.logger import get_logger
from foundation.result import Result
from foundation.types import SubTask, Task
from foundation.validation import require_in, require_non_empty, require_not_none
from planner.types import (
    ExecutionPlan,
    NormalizedRequest,
    PlannerSubTask,
    Priority,
    Requirement,
)

MODULE_NAME = "planner"

# --- analyze() ヒアリスティック抽出ルール(MVP簡易実装。真のNLP/LLM推論は行わない) ---

_DELIVERABLE_RULES: tuple[tuple[str, str], ...] = (
    ("pull request", "Pull Request"),
    ("プルリクエスト", "Pull Request"),
    ("pr", "Pull Request"),
    ("テスト", "テスト"),
    ("ドキュメント", "ドキュメント"),
    ("レポート", "レポート"),
)
_DEFAULT_DELIVERABLE = "成果物"

_CONSTRAINT_KEYWORDS: tuple[str, ...] = (
    "維持",
    "変更しない",
    "変更せず",
    "壊さない",
    "崩さない",
    "そのまま",
    "既存",
)

_HIGH_PRIORITY_KEYWORDS: tuple[str, ...] = ("緊急", "至急", "asap", "最優先", "早急")
_LOW_PRIORITY_KEYWORDS: tuple[str, ...] = ("余裕があれば", "低優先", "後回し", "任意")

_NO_PROJECT_CONTEXT_BACKGROUND = "project_context未指定"

# --- create_tasks() 既定分解テンプレート(M06 3.3節の例に準拠) ---

_TASK_TEMPLATE: tuple[tuple[str, str], ...] = (
    ("現状分析", "要求内容と対象範囲の現状を分析する。"),
    ("改善案作成", "現状分析結果を踏まえた改善案を作成する。"),
    ("改善案評価", "作成した改善案を評価する。"),
    ("実装", "評価済みの改善案を実装する。"),
)


def _extract_deliverable(text: str) -> str:
    lowered = text.lower()
    for keyword, label in _DELIVERABLE_RULES:
        if keyword in lowered:
            return label
    return _DEFAULT_DELIVERABLE


def _extract_constraints(text: str) -> list[str]:
    segments = re.split(r"[。、\n]", text)
    return [
        segment.strip()
        for segment in segments
        if segment.strip() and any(keyword in segment for keyword in _CONSTRAINT_KEYWORDS)
    ]


def _extract_priority(text: str) -> Priority:
    lowered = text.lower()
    if any(keyword in lowered for keyword in _HIGH_PRIORITY_KEYWORDS):
        return Priority.HIGH
    if any(keyword in lowered for keyword in _LOW_PRIORITY_KEYWORDS):
        return Priority.LOW
    return Priority.MEDIUM


def _extract_objective(text: str) -> str:
    # MVP簡易実装: 真の要約・NLP推論は行わず、要求文全体を目的の基礎とする。
    return text


def _extract_background(project_context: object | None) -> str:
    if project_context is None:
        return _NO_PROJECT_CONTEXT_BACKGROUND
    context_id = getattr(project_context, "id", None)
    return f"project_context(id={context_id})を参照"


def _topological_order(task_list: list[PlannerSubTask]) -> list[PlannerSubTask]:
    """depends_on を考慮し、依存元が依存先より後に来ないよう並び替える(Kahn法)。
    循環依存等で解決不能な場合はorder順のままフォールバックする(MVP)。
    """
    by_id = {task.subtask.id: task for task in task_list}
    indegree = {task.subtask.id: 0 for task in task_list}
    for task in task_list:
        for dep in task.depends_on:
            if dep in by_id:
                indegree[task.subtask.id] += 1

    remaining = {task.subtask.id for task in task_list}
    ordered: list[PlannerSubTask] = []

    while remaining:
        ready = [by_id[task_id] for task_id in remaining if indegree[task_id] == 0]
        if not ready:
            # 循環依存フォールバック: 残りをorder順にそのまま採用する。
            ready = [by_id[task_id] for task_id in remaining]
        ready.sort(key=lambda task: task.order)
        chosen = ready[0]
        ordered.append(chosen)
        remaining.discard(chosen.subtask.id)
        for task in task_list:
            if task.subtask.id in remaining and chosen.subtask.id in task.depends_on:
                indegree[task.subtask.id] -= 1

    return ordered


def _downstream_counts(task_list: list[PlannerSubTask]) -> dict[str, int]:
    """各Taskについて、直接・間接的に依存している(下流にある)Task数を数える。
    下流Task数が多いTaskほど後続処理を多くブロックしているとみなし、優先度算出に使う。
    """
    reverse_deps: dict[str, list[str]] = {task.subtask.id: [] for task in task_list}
    for task in task_list:
        for dep in task.depends_on:
            if dep in reverse_deps:
                reverse_deps[dep].append(task.subtask.id)

    def _reachable(node_id: str, visiting: set[str]) -> set[str]:
        if node_id in visiting:
            return set()
        visiting.add(node_id)
        found: set[str] = set()
        for child in reverse_deps.get(node_id, []):
            if child not in found:
                found.add(child)
                found |= _reachable(child, visiting)
        return found

    return {task.subtask.id: len(_reachable(task.subtask.id, set())) for task in task_list}


class Planner(BaseModule):
    """M06 Planner の公開インターフェース実装。
    設計・実装・レビューは行わない(M06 4章の制約)。
    """

    def __init__(self, config_client: ConfigurationClient) -> None:
        self._config_client = config_client
        self._logger = get_logger(MODULE_NAME)
        # analyze()で確定した値をcreate_execution_plan()のログ・成果物生成で再利用する
        # (create_execution_plan()は仕様上prioritized_tasksのみを受け取るため、
        # workflow_id/objective/expected_outputはインスタンス内部で引き継ぐ:
        # IS06 4節「呼び出し順序の制御は...内部プライベートヘルパー(非公開)に委ねる」)。
        self._last_workflow_id: str | None = None
        self._last_objective: str | None = None
        self._last_expected_output: str | None = None

    # --- F02 Common Interface ---

    def name(self) -> str:
        return MODULE_NAME

    def health_check(self) -> Result[bool]:
        return Result(success=True, value=True, error=None)

    # --- M06 3.6 公開インターフェース ---

    def analyze(self, normalized_request: NormalizedRequest) -> Result[Requirement]:
        """M06 3.2節: 目的・背景・制約・成果物・優先度を抽出する。"""
        try:
            require_not_none(normalized_request, "normalized_request")
            require_not_none(normalized_request.workflow_id, "workflow_id")
            require_non_empty(normalized_request.request_text, "request_text")
        except ValidationError as exc:
            self._logger.debug("analyze_failed reason=%s", exc.message)
            return Result(success=False, value=None, error=exc)

        text = normalized_request.request_text.strip()
        objective = _extract_objective(text)
        background = _extract_background(normalized_request.project_context)
        constraints = _extract_constraints(text)
        deliverable = _extract_deliverable(text)
        priority = _extract_priority(text)

        requirement = Requirement(
            task=Task(),
            objective=objective,
            background=background,
            constraints=constraints,
            deliverable=deliverable,
            priority=priority,
        )

        self._last_workflow_id = normalized_request.workflow_id
        self._last_objective = objective
        self._last_expected_output = deliverable

        self._logger.debug(
            "analyze_completed workflow_id=%s objective=%s",
            normalized_request.workflow_id,
            objective,
        )
        return Result(success=True, value=requirement, error=None)

    def create_tasks(self, requirement: Requirement) -> Result[list[PlannerSubTask]]:
        """M06 3.3節: 要求をTask Listへ分解する。"""
        try:
            require_not_none(requirement, "requirement")
            require_non_empty(requirement.objective, "objective")
        except ValidationError as exc:
            self._logger.debug("create_tasks_failed reason=%s", exc.message)
            return Result(success=False, value=None, error=exc)

        steps = list(_TASK_TEMPLATE) + [
            (
                f"{requirement.deliverable}作成",
                f"実装結果をもとに{requirement.deliverable}を作成する。",
            )
        ]

        task_list: list[PlannerSubTask] = []
        previous_id: str | None = None
        for index, (title, description) in enumerate(steps, start=1):
            subtask = SubTask()
            depends_on = [previous_id] if previous_id else []
            task_list.append(
                PlannerSubTask(
                    subtask=subtask,
                    order=index,
                    title=title,
                    description=description,
                    depends_on=depends_on,
                    priority=None,
                )
            )
            previous_id = subtask.id

        self._logger.debug("create_tasks_completed task_count=%d", len(task_list))
        return Result(success=True, value=task_list, error=None)

    def prioritize(self, task_list: list[PlannerSubTask]) -> Result[list[PlannerSubTask]]:
        """M06 3.4節: 各TaskにPriorityを付与し、依存関係を考慮した実行順序に並び替える。"""
        try:
            require_non_empty(task_list, "task_list")
            for subtask in task_list:
                if subtask.priority is not None:
                    require_in(subtask.priority, list(Priority), "priority")
        except ValidationError as exc:
            self._logger.debug("prioritize_failed reason=%s", exc.message)
            return Result(success=False, value=None, error=exc)

        ordered = _topological_order(task_list)
        downstream_counts = _downstream_counts(ordered)

        prioritized: list[PlannerSubTask] = []
        for subtask in ordered:
            count = downstream_counts.get(subtask.subtask.id, 0)
            if count >= 2:
                priority = Priority.HIGH
            elif count == 1:
                priority = Priority.MEDIUM
            else:
                priority = Priority.LOW
            prioritized.append(replace(subtask, priority=priority))

        self._logger.debug("prioritize_completed task_count=%d", len(prioritized))
        return Result(success=True, value=prioritized, error=None)

    def create_execution_plan(self, prioritized_tasks: list[PlannerSubTask]) -> Result[ExecutionPlan]:
        """M06 3.5節: Prioritized TasksからExecution Planを生成する。"""
        workflow_id = self._last_workflow_id
        try:
            require_non_empty(prioritized_tasks, "prioritized_tasks")
        except ValidationError as exc:
            self._log_execution_plan_result(workflow_id, self._last_objective, 0, "N/A", success=False)
            return Result(success=False, value=None, error=exc)

        objective = self._last_objective or prioritized_tasks[0].title
        expected_output = self._last_expected_output or prioritized_tasks[-1].title
        dependencies = {task.subtask.id: list(task.depends_on) for task in prioritized_tasks}

        now = datetime.now(UTC)
        plan = ExecutionPlan(
            id=str(uuid4()),
            created_at=now,
            updated_at=now,
            metadata={},
            objective=objective,
            task_list=list(prioritized_tasks),
            dependencies=dependencies,
            expected_output=expected_output,
        )

        self._log_execution_plan_result(workflow_id, objective, len(prioritized_tasks), plan.id, success=True)
        return Result(success=True, value=plan, error=None)

    def _log_execution_plan_result(
        self,
        workflow_id: str | None,
        objective: str | None,
        task_count: int,
        execution_plan_id: str,
        *,
        success: bool,
    ) -> None:
        """M06 4.5節の必須ログ項目(workflow_id/objective/task_count/execution_plan_id/result)を
        1行に集約して記録する。Secret・Knowledge本文は出力しない。
        """
        if success:
            self._logger.info(
                "execution_plan_created workflow_id=%s objective=%s task_count=%d " "execution_plan_id=%s result=%s",
                workflow_id,
                objective,
                task_count,
                execution_plan_id,
                "success",
            )
        else:
            self._logger.error(
                "execution_plan_failed workflow_id=%s objective=%s task_count=%d " "execution_plan_id=%s result=%s",
                workflow_id,
                objective,
                task_count,
                execution_plan_id,
                "failure",
            )
