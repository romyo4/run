"""パイプライン各モジュール間のデータ受け渡しにおける型不整合を吸収するアダプタ。

いずれも既存モジュールのソースコード(design/実装仕様書ではなく実際のsrc/実装)を唯一の
正として、実際に要求されている属性名に合わせて変換する。2026-07統合レビューで判明した
以下2件の不整合の是正:

1. Planner `ExecutionPlan`(`planner.types`)は`id`属性を持つが、Architect
   `analyzer.py`(および`architect.models.ExecutionPlan` Protocol)は`plan_id`を読む。
2. Design Auditor `ApprovedDesign`(`design_auditor.types`)は`metadata`属性を持たないが、
   Executor `_validate_approval()`(`executor.executor`)は`getattr(approved_design,
   "metadata", None)`経由で`approval_status`/`design_id`キーを読む。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from design_auditor.types import ApprovedDesign
from planner.types import ExecutionPlan

__all__ = [
    "ArchitectExecutionPlanView",
    "ExecutorApprovedDesignView",
    "to_architect_execution_plan",
    "to_executor_approved_design",
]

# executor.executor._validate_approval()が参照するmetadataキー名と同一の規約
# (executor/executor.py 内の _APPROVAL_STATUS_METADATA_KEY 等と一致させる)。
_APPROVAL_STATUS_METADATA_KEY = "approval_status"
_APPROVED_STATUS_VALUE = "approved"
_APPROVED_DESIGN_ID_METADATA_KEY = "design_id"


@dataclass
class ArchitectExecutionPlanView:
    """Architect `analyzer.py` / `architect.models.ExecutionPlan` Protocolが要求する
    `plan_id`属性を、Planner `ExecutionPlan.id`から補って公開するビュー。

    `plan_id`/`objective`/`task_list`/`dependencies`はanalyzer.pyが実際に読む属性。
    `expected_output`はPlannerの`ExecutionPlan`にも同名で存在する1:1の項目。
    `priority`はanalyzer.py自体は現時点で読まないが、`architect.models.ExecutionPlan`
    Protocol(analyze_plan()の型注釈上の契約)が要求するため、構造的に満たす目的でのみ
    空dictを既定値として保持する(Plannerの`ExecutionPlan`にはPlan単位のpriorityが
    存在しないため)。
    """

    plan_id: str
    objective: str
    task_list: list[Any]
    dependencies: dict[str, list[str]]
    expected_output: str
    priority: dict[str, str] = field(default_factory=dict)


def to_architect_execution_plan(execution_plan: ExecutionPlan) -> ArchitectExecutionPlanView:
    """PlannerのExecutionPlanを、ArchitectがそのままAnalyzer入力として使える形へ変換する。"""
    return ArchitectExecutionPlanView(
        plan_id=execution_plan.id,
        objective=execution_plan.objective,
        task_list=execution_plan.task_list,
        dependencies=execution_plan.dependencies,
        expected_output=execution_plan.expected_output,
    )


@dataclass
class ExecutorApprovedDesignView:
    """Executor `_validate_approval()` が要求する`metadata["approval_status"]`/
    `metadata["design_id"]`を、Design Auditorの`ApprovedDesign`(metadata非保持)から
    補って公開するビュー。

    `metadata`以外の属性(`design_id`/`audit_id`/`approved_at`/`comments`等)は、
    executor.py側が将来アクセスする可能性を考慮し、`source`(元のApprovedDesign)へ
    そのまま委譲する。
    """

    source: ApprovedDesign
    metadata: dict[str, Any]

    def __getattr__(self, name: str) -> Any:
        # dataclassフィールド(source/metadata)は通常の属性解決で見つかるため、
        # ここに到達するのはsource側にのみ存在する属性へのアクセス時のみ。
        source = self.__dict__.get("source")
        if source is None:
            raise AttributeError(name)
        return getattr(source, name)


def to_executor_approved_design(approved_design: ApprovedDesign) -> ExecutorApprovedDesignView:
    """Design AuditorのApprovedDesignを、Executorがそのままload_design()入力として
    使える形へ変換する。"""
    return ExecutorApprovedDesignView(
        source=approved_design,
        metadata={
            _APPROVAL_STATUS_METADATA_KEY: _APPROVED_STATUS_VALUE,
            _APPROVED_DESIGN_ID_METADATA_KEY: approved_design.design_id,
        },
    )
