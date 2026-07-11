"""analyzer.analyze_plan()のテスト(IS07仕様書7節 test_analyzer.py)。"""

from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from typing import Any

from architect import analyzer
from architect.errors import PlanAnalysisError
from foundation.types import Context


@dataclass
class _FakeExecutionPlan:
    plan_id: str
    objective: str
    task_list: list[Any]
    priority: dict[str, str] = field(default_factory=dict)
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    expected_output: str = ""


def _make_execution_plan(**overrides: Any) -> _FakeExecutionPlan:
    defaults: dict[str, Any] = dict(
        plan_id="plan-1",
        objective="LPのファーストビューを改善する",
        task_list=["現状分析", "改善案作成"],
        priority={"task-1": "HIGH"},
        dependencies={},
        expected_output="改善済みLP",
    )
    defaults.update(overrides)
    return _FakeExecutionPlan(**defaults)


class TestAnalyzer(unittest.TestCase):
    def test_analyze_plan_extracts_objective_from_execution_plan(self) -> None:
        plan = _make_execution_plan(objective="新機能を設計する")
        result = analyzer.analyze_plan("wf-1", plan, [], None, None)
        self.assertTrue(result.success)
        self.assertEqual(result.value.objective, "新機能を設計する")

    def test_analyze_plan_extracts_constraints_from_execution_plan(self) -> None:
        plan = _make_execution_plan(dependencies={"task-2": ["task-1"]})
        result = analyzer.analyze_plan("wf-1", plan, [], None, None)
        self.assertTrue(result.success)
        self.assertIn("task-2 depends on task-1", result.value.constraints)

    def test_identify_reusable_components_uses_project_context(self) -> None:
        context = Context(metadata={"existing_modules": ["auth_module", "payment_module"]})
        components = analyzer.identify_reusable_components(context, None)
        self.assertIn("auth_module", components)
        self.assertIn("payment_module", components)

    def test_summarize_existing_architecture_uses_architecture_guidelines(self) -> None:
        guidelines = {"existing_architecture_summary": "レイヤードアーキテクチャを採用"}
        summary = analyzer.summarize_existing_architecture(guidelines)
        self.assertEqual(summary, "レイヤードアーキテクチャを採用")

    def test_analyze_plan_raises_plan_analysis_error_on_missing_objective(self) -> None:
        plan = _make_execution_plan(objective="")
        with self.assertRaises(PlanAnalysisError):
            analyzer.analyze_plan("wf-1", plan, [], None, None)

    def test_analyze_plan_preserves_original_objective_text(self) -> None:
        original_text = "既存デザインを維持しつつファーストビューのみ改善する"
        plan = _make_execution_plan(objective=original_text)
        result = analyzer.analyze_plan("wf-1", plan, [], None, None)
        self.assertEqual(result.value.objective, original_text)
        self.assertEqual(plan.objective, original_text)


if __name__ == "__main__":
    unittest.main()
