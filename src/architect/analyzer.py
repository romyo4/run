"""Architect(M07) analyze_plan() の内部処理(IS07 4.2節 / 設計書3.2)。

要件抽出・既存アーキテクチャ分析・再利用可能コンポーネント検出・技術的制約分析を行う。
Execution Plan(Plannerが確定した要求)の内容は変更しない(設計書4.2)。
"""

from __future__ import annotations

from architect.errors import PlanAnalysisError
from architect.models import (
    ArchitectureGuidelines,
    DesignRequirement,
    ExecutionPlan,
    Knowledge,
    ProjectContext,
)
from foundation.result import Result
from foundation.utils import generate_id

__all__ = [
    "analyze_plan",
    "extract_constraints",
    "identify_reusable_components",
    "summarize_existing_architecture",
]


def analyze_plan(
    workflow_id: str,
    execution_plan: ExecutionPlan,
    knowledge: list[Knowledge],
    project_context: ProjectContext | None,
    architecture_guidelines: ArchitectureGuidelines | None,
) -> Result[DesignRequirement]:
    """要件・既存アーキテクチャ・既存モジュール・再利用可能コンポーネント・技術的制約を分析する(3.2)。

    execution_plan.objective が空、または execution_plan.task_list が空の場合は
    `PlanAnalysisError` を送出する(必須フィールド欠落・Task List空)。
    Planner が確定した objective の文字列自体は変更しない(設計書4.2)。
    """
    objective = getattr(execution_plan, "objective", None)
    if not objective:
        raise PlanAnalysisError("execution_plan.objective must not be empty")

    task_list = getattr(execution_plan, "task_list", None)
    if not task_list:
        raise PlanAnalysisError("execution_plan.task_list must not be empty")

    requirement = DesignRequirement(
        requirement_id=generate_id(),
        workflow_id=workflow_id,
        source_execution_plan_id=execution_plan.plan_id,
        objective=objective,
        constraints=extract_constraints(execution_plan),
        functional_requirements=[str(task) for task in task_list],
        existing_architecture_summary=summarize_existing_architecture(architecture_guidelines),
        reusable_components=identify_reusable_components(project_context, architecture_guidelines),
    )
    return Result(success=True, value=requirement)


def extract_constraints(execution_plan: ExecutionPlan) -> list[str]:
    """execution_plan.dependencies から技術的制約(タスク間依存)を文字列化して抽出する。"""
    dependencies = getattr(execution_plan, "dependencies", None) or {}
    constraints: list[str] = []
    for task_id, depends_on in dependencies.items():
        if depends_on:
            constraints.append(f"{task_id} depends on {', '.join(depends_on)}")
    return constraints


def identify_reusable_components(
    project_context: ProjectContext | None,
    architecture_guidelines: ArchitectureGuidelines | None,
) -> list[str]:
    """project_context / architecture_guidelines から再利用可能コンポーネントを検出する(Reuse First)。"""
    components: list[str] = []

    if architecture_guidelines:
        components.extend(architecture_guidelines.get("reusable_components", []))

    if project_context is not None:
        components.extend(project_context.metadata.get("existing_modules", []))

    # 重複除去(順序保持)
    seen: set[str] = set()
    unique_components: list[str] = []
    for component in components:
        if component not in seen:
            seen.add(component)
            unique_components.append(component)
    return unique_components


def summarize_existing_architecture(
    architecture_guidelines: ArchitectureGuidelines | None,
) -> str:
    """architecture_guidelines から既存アーキテクチャの要約を抽出する。"""
    if not architecture_guidelines:
        return ""
    return str(architecture_guidelines.get("existing_architecture_summary", ""))
