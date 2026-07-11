import unittest
from datetime import UTC, datetime

from context_manager.types import (
    AIContext,
    ContextMetadata,
    SelectedContext,
    ValidationResult,
    WorkflowScope,
    WorkflowType,
)
from foundation.types import Context


class AIContextTest(unittest.TestCase):
    def test_ai_context_inherits_foundation_context_common_fields(self) -> None:
        context = AIContext()
        self.assertIsInstance(context, Context)
        self.assertIsInstance(context.id, str)
        self.assertIsInstance(context.created_at, datetime)
        self.assertIsInstance(context.updated_at, datetime)
        self.assertEqual(context.metadata, {})

    def test_ai_context_default_workflow_type_is_valid_enum_member(self) -> None:
        context = AIContext()
        self.assertIsInstance(context.workflow_type, WorkflowType)
        self.assertIn(context.workflow_type, list(WorkflowType))


class SelectedContextTest(unittest.TestCase):
    def test_selected_context_defaults_all_optional_fields_to_empty(self) -> None:
        selected = SelectedContext(workflow_type=WorkflowType.PLANNER)
        self.assertIsNone(selected.business_goal)
        self.assertIsNone(selected.user_instruction)
        self.assertEqual(selected.knowledge, [])
        self.assertEqual(selected.requirements, [])
        self.assertEqual(selected.architecture_principles, [])
        self.assertIsNone(selected.execution_plan)
        self.assertIsNone(selected.repository_context)
        self.assertEqual(selected.coding_rules, [])
        self.assertEqual(selected.design_documents, [])
        self.assertIsNone(selected.implementation)
        self.assertIsNone(selected.test_report)
        self.assertEqual(selected.merged_pull_requests, [])
        self.assertEqual(selected.review_reports, [])
        self.assertEqual(selected.technical_debt_reports, [])


class ContextMetadataTest(unittest.TestCase):
    def test_context_metadata_built_at_defaults_to_utc_now(self) -> None:
        before = datetime.now(UTC)
        metadata = ContextMetadata(workflow_id="wf-1", workflow_type=WorkflowType.PLANNER, context_version="v1")
        after = datetime.now(UTC)
        self.assertIsInstance(metadata.built_at, datetime)
        self.assertLessEqual(before, metadata.built_at)
        self.assertLessEqual(metadata.built_at, after)


class ValidationResultTest(unittest.TestCase):
    def test_validation_result_missing_fields_defaults_to_empty_list(self) -> None:
        result = ValidationResult(is_valid=True)
        self.assertEqual(result.missing_fields, [])


class WorkflowScopeTest(unittest.TestCase):
    def test_workflow_scope_target_paths_defaults_to_empty_list(self) -> None:
        scope = WorkflowScope(workflow_id="wf-1", workflow_type=WorkflowType.EXECUTOR)
        self.assertEqual(scope.target_paths, [])


if __name__ == "__main__":
    unittest.main()
