import dataclasses
import unittest

from context_manager.selector import WORKFLOW_FIELD_MAP, select
from context_manager.types import CollectedContext, WorkflowType

from .fakes import FakeKnowledgeDocument


def _all_selected_context_field_names() -> frozenset[str]:
    from context_manager.types import SelectedContext

    return frozenset(f.name for f in dataclasses.fields(SelectedContext) if f.name != "workflow_type")


def _make_full_collected_context() -> CollectedContext:
    """全カテゴリ・全直接フィールドを埋めたCollectedContextを生成する。"""
    return CollectedContext(
        knowledge_documents=[
            FakeKnowledgeDocument(category="business_goal", body="goal"),
            FakeKnowledgeDocument(category="knowledge", body="knowledge-item"),
            FakeKnowledgeDocument(category="requirements", body="requirement"),
            FakeKnowledgeDocument(category="architecture_principles", body="principle"),
            FakeKnowledgeDocument(category="coding_rules", body="rule"),
        ],
        repository_context={"repo": "example"},
        environment="staging",
        execution_plan={"plan": "example"},
        user_instruction="improve LP",
        implementation={"impl": "example"},
        test_report={"report": "example"},
        merged_pull_requests=[{"pr": 1}],
        review_reports=[{"review": 1}],
        technical_debt_reports=[{"debt": 1}],
    )


def _assert_only_fields_populated(
    test: unittest.TestCase, workflow_type: WorkflowType, expected_populated: frozenset[str]
) -> None:
    collected = _make_full_collected_context()
    selected = select(workflow_type, collected)

    for field_name in _all_selected_context_field_names():
        value = getattr(selected, field_name)
        if field_name in expected_populated:
            test.assertTrue(
                value not in (None, [], ""),
                msg=f"{field_name} should be populated but was {value!r}",
            )
        else:
            test.assertIn(value, (None, [], ""), msg=f"{field_name} should stay empty but was {value!r}")


class SelectorPlannerTest(unittest.TestCase):
    def test_select_for_planner_includes_only_business_goal_user_instruction_knowledge(
        self,
    ) -> None:
        _assert_only_fields_populated(self, WorkflowType.PLANNER, WORKFLOW_FIELD_MAP[WorkflowType.PLANNER])


class SelectorArchitectTest(unittest.TestCase):
    def test_select_for_architect_includes_only_requirements_knowledge_architecture_principles(
        self,
    ) -> None:
        _assert_only_fields_populated(self, WorkflowType.ARCHITECT, WORKFLOW_FIELD_MAP[WorkflowType.ARCHITECT])


class SelectorExecutorTest(unittest.TestCase):
    def test_select_for_executor_includes_only_execution_plan_repository_context_coding_rules_design_documents(
        self,
    ) -> None:
        _assert_only_fields_populated(self, WorkflowType.EXECUTOR, WORKFLOW_FIELD_MAP[WorkflowType.EXECUTOR])


class SelectorReviewerTest(unittest.TestCase):
    def test_select_for_reviewer_includes_only_implementation_design_documents_test_report_business_goal(
        self,
    ) -> None:
        _assert_only_fields_populated(self, WorkflowType.REVIEWER, WORKFLOW_FIELD_MAP[WorkflowType.REVIEWER])


class SelectorWeeklyReviewerTest(unittest.TestCase):
    def test_select_for_weekly_reviewer_includes_only_merged_prs_review_reports_business_goal_technical_debt_reports(
        self,
    ) -> None:
        _assert_only_fields_populated(self, WorkflowType.WEEKLY_REVIEWER, WORKFLOW_FIELD_MAP[WorkflowType.WEEKLY_REVIEWER])


class SelectorExclusionTest(unittest.TestCase):
    def test_select_excludes_fields_not_in_workflow_field_map(self) -> None:
        collected = _make_full_collected_context()
        selected = select(WorkflowType.PLANNER, collected)

        excluded_fields = _all_selected_context_field_names() - WORKFLOW_FIELD_MAP[WorkflowType.PLANNER]
        for field_name in excluded_fields:
            value = getattr(selected, field_name)
            self.assertIn(value, (None, [], ""), msg=f"{field_name} unexpectedly populated")


if __name__ == "__main__":
    unittest.main()
