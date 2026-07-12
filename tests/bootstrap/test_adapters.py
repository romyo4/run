"""adaptersモジュールの単体テスト(Task 3)。

2026-07統合レビューで判明した、パイプライン間の既知の型不整合2件をそれぞれ検証する。

1. Planner `ExecutionPlan.id` ⇔ Architect `analyzer.py` が読む `execution_plan.plan_id`
   (`src/architect/analyzer.py` line 52, および `architect.models.ExecutionPlan` Protocol)
2. Design Auditor `ApprovedDesign`(metadata非保持)⇔ Executor `_validate_approval()` が読む
   `getattr(approved_design, "metadata", None)`(`src/executor/executor.py` line 170)

いずれも実際のソースコード(src/実装)を正として検証し、ダミーの属性追加は行わない(YAGNI)。
"""

from __future__ import annotations

import unittest
from pathlib import Path

from architect.analyzer import analyze_plan
from bootstrap.adapters import (
    to_architect_execution_plan,
    to_executor_approved_design,
)
from design_auditor.types import ApprovedDesign
from executor.executor import Executor
from executor.models import RepositoryInfo
from executor.repository_guard import RepositoryGuard
from foundation.types import Design
from foundation.utils import utc_now
from planner.types import ExecutionPlan
from tests.executor.fakes import FakeCodexAdapter


def _make_execution_plan(**overrides: object) -> ExecutionPlan:
    defaults: dict[str, object] = dict(
        id="plan-1",
        created_at=utc_now(),
        updated_at=utc_now(),
        metadata={},
        objective="LP改善",
        task_list=[],
        dependencies={},
        expected_output="改善後のLPドラフト",
    )
    defaults.update(overrides)
    return ExecutionPlan(**defaults)  # type: ignore[arg-type]


class ToArchitectExecutionPlanTest(unittest.TestCase):
    """`analyzer.py`が実際に読む属性(objective/task_list/plan_id/dependencies)を検証する。"""

    def test_wrapped_plan_exposes_plan_id_matching_source_id(self) -> None:
        plan = _make_execution_plan(id="plan-42")

        wrapped = to_architect_execution_plan(plan)

        self.assertEqual(wrapped.plan_id, "plan-42")
        self.assertEqual(wrapped.plan_id, plan.id)

    def test_wrapped_plan_exposes_objective_task_list_and_dependencies(self) -> None:
        plan = _make_execution_plan(
            objective="LP改善",
            task_list=["task-a", "task-b"],
            dependencies={"task-a": ["task-b"]},
        )

        wrapped = to_architect_execution_plan(plan)

        self.assertEqual(wrapped.objective, plan.objective)
        self.assertEqual(wrapped.task_list, plan.task_list)
        self.assertEqual(wrapped.dependencies, plan.dependencies)

    def test_wrapped_plan_exposes_expected_output_and_priority_for_protocol_conformance(
        self,
    ) -> None:
        """`architect.models.ExecutionPlan` Protocolは`expected_output`/`priority`も
        要求する(analyzer.py自体は現時点でこの2つを読まないが、analyze_plan()の型注釈上の
        契約であるため構造的に満たしておく)。"""
        plan = _make_execution_plan(expected_output="改善後のLPドラフト")

        wrapped = to_architect_execution_plan(plan)

        self.assertEqual(wrapped.expected_output, plan.expected_output)
        self.assertEqual(wrapped.priority, {})

    def test_to_architect_execution_plan_satisfies_real_analyze_plan(self) -> None:
        """ボーナス統合テスト: 実際に`architect.analyzer.analyze_plan()`を呼び出し、
        アダプタが本物の消費者を満たすことを直接証明する。"""
        plan = _make_execution_plan(
            objective="LP改善",
            task_list=["task-a"],
            dependencies={"task-a": ["task-b"]},
        )
        wrapped = to_architect_execution_plan(plan)

        result = analyze_plan(
            workflow_id="workflow-1",
            execution_plan=wrapped,
            knowledge=[],
            project_context=None,
            architecture_guidelines=None,
        )

        self.assertTrue(result.success)
        assert result.value is not None
        self.assertEqual(result.value.source_execution_plan_id, plan.id)
        self.assertEqual(result.value.constraints, ["task-a depends on task-b"])


class ToExecutorApprovedDesignTest(unittest.TestCase):
    """`_validate_approval()`が実際に読む`metadata`辞書(approval_status/design_id)を検証する。"""

    def test_wrapped_approved_design_exposes_approval_metadata(self) -> None:
        approved = ApprovedDesign(
            design_id="design-1",
            audit_id="audit-1",
            approved_at=utc_now(),
            comments=[],
        )

        wrapped = to_executor_approved_design(approved)

        self.assertEqual(wrapped.metadata["approval_status"], "approved")
        self.assertEqual(wrapped.metadata["design_id"], "design-1")

    def test_wrapped_approved_design_delegates_other_attributes_to_source(self) -> None:
        """metadata以外にexecutor.py側から将来アクセスされ得る属性
        (design_id/audit_id/approved_at/comments)も、sourceへ委譲して読めること。"""
        approved = ApprovedDesign(
            design_id="design-1",
            audit_id="audit-1",
            approved_at=utc_now(),
            comments=["LGTM"],
        )

        wrapped = to_executor_approved_design(approved)

        self.assertIs(wrapped.source, approved)
        self.assertEqual(wrapped.design_id, approved.design_id)
        self.assertEqual(wrapped.audit_id, approved.audit_id)
        self.assertEqual(wrapped.approved_at, approved.approved_at)
        self.assertEqual(wrapped.comments, approved.comments)

    def test_matches_executor_validate_approval_getattr_pattern(self) -> None:
        """`Executor._validate_approval()`と同一のgetattrパターンで直接検証する。"""
        approved = ApprovedDesign(
            design_id="design-1",
            audit_id="audit-1",
            approved_at=utc_now(),
            comments=[],
        )
        wrapped = to_executor_approved_design(approved)

        metadata = getattr(wrapped, "metadata", None) or {}
        self.assertEqual(metadata.get("approval_status"), "approved")
        self.assertEqual(metadata.get("design_id"), "design-1")

    def test_to_executor_approved_design_satisfies_real_load_design(self) -> None:
        """ボーナス統合テスト: 実際に`Executor.load_design()`を呼び出し、
        アダプタが承認検証(4.3)を通過することを直接証明する。"""
        design_document = Design(id="design-1")
        approved = ApprovedDesign(
            design_id="design-1",
            audit_id="audit-1",
            approved_at=utc_now(),
            comments=[],
        )
        wrapped = to_executor_approved_design(approved)
        executor = Executor(codex_adapter=FakeCodexAdapter(), repository_guard=RepositoryGuard())

        result = executor.load_design(
            workflow_id="workflow-1",
            approved_design=wrapped,
            design_document=design_document,
            project_context={},
            repository_information=RepositoryInfo(repository_id="repo-1", root_path=Path("."), default_branch="main"),
        )

        self.assertTrue(result.success)

    def test_to_executor_approved_design_rejects_mismatched_design_id(self) -> None:
        """design_document.idとapproved_design.design_idが不一致の場合は
        load_design()が失敗すること(委譲が正しく機能している裏付け)。"""
        design_document = Design(id="design-999")
        approved = ApprovedDesign(
            design_id="design-1",
            audit_id="audit-1",
            approved_at=utc_now(),
            comments=[],
        )
        wrapped = to_executor_approved_design(approved)
        executor = Executor(codex_adapter=FakeCodexAdapter(), repository_guard=RepositoryGuard())

        result = executor.load_design(
            workflow_id="workflow-1",
            approved_design=wrapped,
            design_document=design_document,
            project_context={},
            repository_information=RepositoryInfo(repository_id="repo-1", root_path=Path("."), default_branch="main"),
        )

        self.assertFalse(result.success)


if __name__ == "__main__":
    unittest.main()
