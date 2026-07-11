import unittest

from context_manager.types import AIContext, SelectedContext, WorkflowType
from context_manager.validator import validate


def _make_context(selected: SelectedContext) -> AIContext:
    return AIContext(
        workflow_id="wf-1",
        workflow_type=selected.workflow_type,
        selected_context=selected,
        context_version="v1",
    )


class ValidateValidTest(unittest.TestCase):
    def test_validate_returns_valid_when_all_required_fields_for_workflow_are_present(self) -> None:
        selected = SelectedContext(
            workflow_type=WorkflowType.PLANNER,
            business_goal=["goal"],
            user_instruction="do something",
            knowledge=["item"],
        )
        result = validate(_make_context(selected))

        self.assertTrue(result.is_valid)
        self.assertEqual(result.missing_fields, [])


class ValidateMissingNoneFieldTest(unittest.TestCase):
    def test_validate_returns_invalid_with_missing_fields_when_required_field_is_none(self) -> None:
        selected = SelectedContext(
            workflow_type=WorkflowType.PLANNER,
            business_goal=None,
            user_instruction="do something",
            knowledge=["item"],
        )
        result = validate(_make_context(selected))

        self.assertFalse(result.is_valid)
        self.assertIn("business_goal", result.missing_fields)


class ValidateMissingEmptyListFieldTest(unittest.TestCase):
    def test_validate_returns_invalid_with_missing_fields_when_required_list_field_is_empty(
        self,
    ) -> None:
        selected = SelectedContext(
            workflow_type=WorkflowType.PLANNER,
            business_goal=["goal"],
            user_instruction="do something",
            knowledge=[],
        )
        result = validate(_make_context(selected))

        self.assertFalse(result.is_valid)
        self.assertIn("knowledge", result.missing_fields)


class ValidateIgnoresUnrelatedFieldsTest(unittest.TestCase):
    def test_validate_does_not_flag_fields_outside_workflow_field_map(self) -> None:
        selected = SelectedContext(
            workflow_type=WorkflowType.PLANNER,
            business_goal=["goal"],
            user_instruction="do something",
            knowledge=["item"],
            # Plannerでは不要なフィールドが空でもmissing_fieldsに含まれてはならない。
            requirements=[],
            coding_rules=[],
            execution_plan=None,
        )
        result = validate(_make_context(selected))

        self.assertTrue(result.is_valid)
        self.assertNotIn("requirements", result.missing_fields)
        self.assertNotIn("coding_rules", result.missing_fields)
        self.assertNotIn("execution_plan", result.missing_fields)


if __name__ == "__main__":
    unittest.main()
