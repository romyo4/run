"""Planner (M06) の公開インターフェース・制約に対するUnit Test(IS06 7節)。"""

from __future__ import annotations

import inspect
import unittest
from typing import Any

from foundation.errors import ValidationError
from foundation.interfaces import ConfigurationClient
from foundation.result import Result
from foundation.types import Context, Knowledge
from planner.planner import Planner
from planner.types import (
    ExecutionPlan,
    NormalizedRequest,
    PlannerSubTask,
    Priority,
    Requirement,
)


class FakeConfigurationClient(ConfigurationClient):
    """ConfigurationClient(F03)の最小限のテスト用フェイク。常に成功を返す。"""

    @staticmethod
    def get(module_name: str, key: str) -> Result[Any]:
        return Result(success=True, value=None)


class _LockedKnowledge(Knowledge):
    """analyze()がKnowledgeを一切変更しないことを検証するための変異検知Spy(M06 4.4節)。"""

    def __setattr__(self, name: str, value: Any) -> None:
        if name != "_locked" and object.__getattribute__(self, "__dict__").get("_locked"):
            raise AssertionError(f"Planner must not mutate Knowledge.{name}")
        object.__setattr__(self, name, value)


def _lock(instance: Any) -> Any:
    object.__setattr__(instance, "_locked", True)
    return instance


def _make_request(
    *,
    workflow_id: str | None = "wf-001",
    command: str = "plan",
    request_text: str = ("LPのファーストビューを改善してPRを作って。" "ただし既存デザインは維持すること。"),
    knowledge: list[Knowledge] | None = None,
    project_context: Context | None = None,
) -> NormalizedRequest:
    return NormalizedRequest(
        workflow_id=workflow_id,
        command=command,
        request_text=request_text,
        knowledge=knowledge if knowledge is not None else [],
        project_context=project_context,
    )


def _subtask(order: int, title: str, depends_on: list[str] | None = None) -> PlannerSubTask:
    from foundation.types import SubTask

    return PlannerSubTask(
        subtask=SubTask(),
        order=order,
        title=title,
        description=f"{title}の説明",
        depends_on=depends_on or [],
        priority=None,
    )


class PlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.planner = Planner(FakeConfigurationClient())

    def _run_pipeline(self, request: NormalizedRequest | None = None):
        request = request or _make_request()
        requirement_result = self.planner.analyze(request)
        self.assertTrue(requirement_result.success)
        task_list_result = self.planner.create_tasks(requirement_result.value)
        self.assertTrue(task_list_result.success)
        prioritized_result = self.planner.prioritize(task_list_result.value)
        self.assertTrue(prioritized_result.success)
        return requirement_result.value, task_list_result.value, prioritized_result.value

    # ------------------------------------------------------------------
    # 7.1 公開インターフェース(正常系)
    # ------------------------------------------------------------------

    def test_analyze_returns_success_result_with_requirement(self) -> None:
        result = self.planner.analyze(_make_request())
        self.assertTrue(result.success)
        self.assertIsInstance(result.value, Requirement)
        self.assertIsNone(result.error)

    def test_analyze_extracts_objective_background_constraints_deliverable_priority(
        self,
    ) -> None:
        context = Context()
        result = self.planner.analyze(
            _make_request(
                request_text=("LPのファーストビューを改善してPRを作って。" "ただし既存デザインは維持すること。"),
                project_context=context,
            )
        )
        self.assertTrue(result.success)
        requirement = result.value
        self.assertTrue(requirement.objective)
        self.assertIn(str(context.id), requirement.background)
        self.assertTrue(any("既存" in c or "維持" in c for c in requirement.constraints))
        self.assertEqual(requirement.deliverable, "Pull Request")
        self.assertEqual(requirement.priority, Priority.MEDIUM)

    def test_create_tasks_returns_success_result_with_task_list(self) -> None:
        requirement_result = self.planner.analyze(_make_request())
        result = self.planner.create_tasks(requirement_result.value)
        self.assertTrue(result.success)
        self.assertIsInstance(result.value, list)
        self.assertTrue(len(result.value) > 0)
        for item in result.value:
            self.assertIsInstance(item, PlannerSubTask)

    def test_create_tasks_preserves_task_order(self) -> None:
        requirement_result = self.planner.analyze(_make_request())
        result = self.planner.create_tasks(requirement_result.value)
        self.assertTrue(result.success)
        orders = [task.order for task in result.value]
        self.assertEqual(orders, list(range(1, len(result.value) + 1)))

    def test_prioritize_assigns_priority_to_every_task(self) -> None:
        _, _, prioritized = self._run_pipeline()
        self.assertTrue(len(prioritized) > 0)
        for task in prioritized:
            self.assertIsNotNone(task.priority)
            self.assertIsInstance(task.priority, Priority)

    def test_prioritize_orders_tasks_considering_dependencies(self) -> None:
        task_a = _subtask(1, "A")
        task_b = _subtask(2, "B", depends_on=[task_a.subtask.id])
        task_c = _subtask(3, "C", depends_on=[task_b.subtask.id])
        # 意図的に依存先が後ろに来る順序でリストを渡す。
        result = self.planner.prioritize([task_c, task_b, task_a])
        self.assertTrue(result.success)
        ordered_ids = [task.subtask.id for task in result.value]
        self.assertLess(ordered_ids.index(task_a.subtask.id), ordered_ids.index(task_b.subtask.id))
        self.assertLess(ordered_ids.index(task_b.subtask.id), ordered_ids.index(task_c.subtask.id))

    def test_create_execution_plan_returns_success_result_with_execution_plan(self) -> None:
        _, _, prioritized = self._run_pipeline()
        result = self.planner.create_execution_plan(prioritized)
        self.assertTrue(result.success)
        self.assertIsInstance(result.value, ExecutionPlan)

    def test_create_execution_plan_maps_plan_id_to_common_id_attribute(self) -> None:
        _, _, prioritized = self._run_pipeline()
        result = self.planner.create_execution_plan(prioritized)
        self.assertTrue(result.success)
        plan = result.value
        self.assertTrue(hasattr(plan, "id"))
        self.assertIsInstance(plan.id, str)
        self.assertTrue(plan.id)
        self.assertFalse(hasattr(plan, "plan_id"))

    def test_create_execution_plan_embeds_priority_in_task_list_not_top_level(self) -> None:
        _, _, prioritized = self._run_pipeline()
        result = self.planner.create_execution_plan(prioritized)
        self.assertTrue(result.success)
        plan = result.value
        self.assertFalse(hasattr(plan, "priority"))
        for task in plan.task_list:
            self.assertIsNotNone(task.priority)

    # ------------------------------------------------------------------
    # 7.2 公開インターフェース(異常系)
    # ------------------------------------------------------------------

    def test_analyze_returns_failure_result_when_request_text_is_empty(self) -> None:
        result = self.planner.analyze(_make_request(request_text=""))
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, ValidationError)

    def test_analyze_returns_failure_result_when_workflow_id_is_missing(self) -> None:
        result = self.planner.analyze(_make_request(workflow_id=None))
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, ValidationError)

    def test_create_tasks_returns_failure_result_when_requirement_is_invalid(self) -> None:
        result = self.planner.create_tasks(None)
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, ValidationError)

    def test_prioritize_returns_failure_result_when_task_list_is_empty(self) -> None:
        result = self.planner.prioritize([])
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, ValidationError)

    def test_create_execution_plan_returns_failure_result_when_prioritized_tasks_is_empty(
        self,
    ) -> None:
        result = self.planner.create_execution_plan([])
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, ValidationError)

    # ------------------------------------------------------------------
    # 7.3 F02 Common Interface
    # ------------------------------------------------------------------

    def test_name_returns_module_name(self) -> None:
        self.assertEqual(self.planner.name(), "planner")

    def test_health_check_returns_success_result(self) -> None:
        result = self.planner.health_check()
        self.assertTrue(result.success)
        self.assertTrue(result.value)

    # ------------------------------------------------------------------
    # 7.4 制約(M06 4章)に対応するテスト
    # ------------------------------------------------------------------

    def test_planner_does_not_mutate_input_knowledge(self) -> None:
        locked_knowledge = _lock(_LockedKnowledge())
        request = _make_request(knowledge=[locked_knowledge])
        result = self.planner.analyze(request)
        self.assertTrue(result.success)
        self.assertEqual(len(request.knowledge), 1)
        self.assertIs(request.knowledge[0], locked_knowledge)

    def test_planner_has_no_design_related_public_method(self) -> None:
        public_methods = {
            name for name, _ in inspect.getmembers(self.planner, predicate=inspect.ismethod) if not name.startswith("_")
        }
        self.assertEqual(
            public_methods,
            {
                "name",
                "health_check",
                "analyze",
                "create_tasks",
                "prioritize",
                "create_execution_plan",
            },
        )
        for forbidden in ("design_class", "design_api", "design_database", "design"):
            self.assertFalse(hasattr(self.planner, forbidden))

    def test_planner_has_no_implementation_related_public_method(self) -> None:
        for forbidden in (
            "generate_code",
            "create_pull_request",
            "push_to_github",
            "implement",
            "apply_patch",
            "commit_code",
        ):
            self.assertFalse(hasattr(self.planner, forbidden))

    def test_execution_plan_does_not_contain_review_decision_field(self) -> None:
        _, _, prioritized = self._run_pipeline()
        result = self.planner.create_execution_plan(prioritized)
        self.assertTrue(result.success)
        plan = result.value
        self.assertFalse(hasattr(plan, "review_decision"))
        self.assertFalse(hasattr(plan, "decision"))
        self.assertFalse(hasattr(plan, "approved"))

    # ------------------------------------------------------------------
    # 7.5 ロギング(M06 4.5節)
    # ------------------------------------------------------------------

    def test_create_execution_plan_logs_required_fields_on_success(self) -> None:
        _, _, prioritized = self._run_pipeline()
        with self.assertLogs("planner", level="INFO") as cm:
            result = self.planner.create_execution_plan(prioritized)
        self.assertTrue(result.success)
        joined = "\n".join(cm.output)
        self.assertIn("workflow_id=", joined)
        self.assertIn("objective=", joined)
        self.assertIn("task_count=", joined)
        self.assertIn("execution_plan_id=", joined)
        self.assertIn("result=success", joined)

    def test_create_execution_plan_logs_result_failure_without_secrets_on_error(self) -> None:
        with self.assertLogs("planner", level="ERROR") as cm:
            result = self.planner.create_execution_plan([])
        self.assertFalse(result.success)
        joined = "\n".join(cm.output)
        self.assertIn("result=failure", joined)
        self.assertNotIn("Secret", joined)
        self.assertNotIn("Token", joined)
        self.assertNotIn("Credential", joined)

    def test_logging_never_includes_knowledge_body(self) -> None:
        secret_body = "SECRET_KNOWLEDGE_BODY_DO_NOT_LOG"
        knowledge = Knowledge(metadata={"body": secret_body})
        request = _make_request(knowledge=[knowledge])
        with self.assertLogs("planner", level="DEBUG") as cm:
            requirement_result = self.planner.analyze(request)
            task_list_result = self.planner.create_tasks(requirement_result.value)
            prioritized_result = self.planner.prioritize(task_list_result.value)
            self.planner.create_execution_plan(prioritized_result.value)
        joined = "\n".join(cm.output)
        self.assertNotIn(secret_body, joined)


if __name__ == "__main__":
    unittest.main()
