"""ArchitectModuleのテスト(IS07仕様書7節 test_module.py)。"""

from __future__ import annotations

import copy
import unittest
from dataclasses import dataclass, field
from typing import Any

from architect.errors import DesignCreationError, DesignValidationError, PlanAnalysisError
from architect.models import (
    DesignDocument,
    DesignStatus,
    ModuleDesignItem,
    ValidatedDesign,
    ValidationResult,
    ValidationStatus,
)
from architect.module import ArchitectModule
from foundation.errors import ConfigurationError
from foundation.interfaces import ConfigurationClient
from foundation.result import Result


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
        dependencies={"task-2": ["task-1"]},
        expected_output="改善済みLP",
    )
    defaults.update(overrides)
    return _FakeExecutionPlan(**defaults)


class _SuccessConfigurationClient(ConfigurationClient):
    def get(self, module_name: str, key: str) -> Result:
        return Result(success=True, value=True)


class _FailingConfigurationClient(ConfigurationClient):
    def get(self, module_name: str, key: str) -> Result:
        return Result(success=False, value=None, error=ConfigurationError("unavailable"))


class TestArchitectModule(unittest.TestCase):
    def setUp(self) -> None:
        self.module = ArchitectModule(config_client=_SuccessConfigurationClient())

    def test_name_returns_architect(self) -> None:
        self.assertEqual(self.module.name(), "architect")

    def test_health_check_returns_success_result_when_configuration_client_available(
        self,
    ) -> None:
        result = self.module.health_check()
        self.assertTrue(result.success)
        self.assertTrue(result.value)

    def test_health_check_returns_failure_result_when_configuration_client_unavailable(
        self,
    ) -> None:
        module = ArchitectModule(config_client=_FailingConfigurationClient())
        result = module.health_check()
        self.assertFalse(result.success)
        self.assertFalse(result.value)
        self.assertIsInstance(result.error, ConfigurationError)

    def test_analyze_plan_returns_success_result_with_design_requirement(self) -> None:
        plan = _make_execution_plan()
        result = self.module.analyze_plan("wf-1", plan)
        self.assertTrue(result.success)
        self.assertIsNone(result.error)
        self.assertEqual(result.value.workflow_id, "wf-1")
        self.assertEqual(result.value.source_execution_plan_id, "plan-1")

    def test_analyze_plan_returns_failure_result_when_execution_plan_task_list_empty(
        self,
    ) -> None:
        plan = _make_execution_plan(task_list=[])
        result = self.module.analyze_plan("wf-1", plan)
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, PlanAnalysisError)

    def test_analyze_plan_does_not_mutate_execution_plan_input(self) -> None:
        plan = _make_execution_plan()
        original_task_list = copy.deepcopy(plan.task_list)
        original_objective = plan.objective
        original_dependencies = copy.deepcopy(plan.dependencies)
        original_priority = copy.deepcopy(plan.priority)

        result = self.module.analyze_plan("wf-1", plan)

        self.assertTrue(result.success)
        self.assertEqual(plan.task_list, original_task_list)
        self.assertEqual(plan.objective, original_objective)
        self.assertEqual(plan.dependencies, original_dependencies)
        self.assertEqual(plan.priority, original_priority)

    def test_create_design_returns_success_result_with_design_document(self) -> None:
        plan = _make_execution_plan()
        requirement = self.module.analyze_plan("wf-1", plan).value
        result = self.module.create_design(requirement)
        self.assertTrue(result.success)
        self.assertIsInstance(result.value, DesignDocument)
        self.assertEqual(result.value.status, DesignStatus.DRAFT)

    def test_create_design_returns_failure_result_when_requirement_invalid(self) -> None:
        plan = _make_execution_plan()
        requirement = self.module.analyze_plan("wf-1", plan).value
        requirement.objective = ""
        result = self.module.create_design(requirement)
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, DesignCreationError)

    def test_validate_design_returns_valid_status_for_complete_document(self) -> None:
        plan = _make_execution_plan()
        requirement = self.module.analyze_plan("wf-1", plan).value
        document = self.module.create_design(requirement).value
        result = self.module.validate_design(document)
        self.assertTrue(result.success)
        self.assertEqual(result.value.status, ValidationStatus.VALID)
        self.assertEqual(result.value.issues, [])

    def test_validate_design_returns_invalid_status_when_required_field_missing(self) -> None:
        document = DesignDocument(objective="", module_design=[])
        result = self.module.validate_design(document)
        self.assertTrue(result.success)
        self.assertEqual(result.value.status, ValidationStatus.INVALID)
        self.assertTrue(result.value.issues)

    def test_publish_design_returns_published_status_when_validation_valid(self) -> None:
        document = DesignDocument(
            objective="obj",
            module_design=[ModuleDesignItem(module_name="m1", responsibility="r1")],
        )
        validation = ValidationResult(validation_id="v1", design_id=document.id, status=ValidationStatus.VALID)
        validated = ValidatedDesign(design_document=document, validation_result=validation)
        result = self.module.publish_design(validated)
        self.assertTrue(result.success)
        self.assertEqual(result.value.status, DesignStatus.PUBLISHED)

    def test_publish_design_returns_failure_result_when_validation_invalid(self) -> None:
        document = DesignDocument(objective="", module_design=[])
        validation = ValidationResult(
            validation_id="v1",
            design_id=document.id,
            status=ValidationStatus.INVALID,
            issues=[],
        )
        validated = ValidatedDesign(design_document=document, validation_result=validation)
        result = self.module.publish_design(validated)
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, DesignValidationError)
        self.assertEqual(document.status, DesignStatus.DRAFT)

    def test_full_pipeline_analyze_create_validate_publish_end_to_end(self) -> None:
        plan = _make_execution_plan()

        analyze_result = self.module.analyze_plan("wf-1", plan)
        self.assertTrue(analyze_result.success)

        create_result = self.module.create_design(analyze_result.value)
        self.assertTrue(create_result.success)

        validate_result = self.module.validate_design(create_result.value)
        self.assertTrue(validate_result.success)
        self.assertEqual(validate_result.value.status, ValidationStatus.VALID)

        validated = ValidatedDesign(design_document=create_result.value, validation_result=validate_result.value)
        publish_result = self.module.publish_design(validated)

        self.assertTrue(publish_result.success)
        self.assertEqual(publish_result.value.status, DesignStatus.PUBLISHED)
        self.assertEqual(publish_result.value.objective, plan.objective)

    def test_module_does_not_expose_code_generation_or_pr_methods(self) -> None:
        forbidden_methods = [
            "generate_code",
            "create_pull_request",
            "create_pr",
            "push_to_github",
            "review_code",
            "merge_pull_request",
            "commit",
        ]
        for method_name in forbidden_methods:
            self.assertFalse(
                hasattr(self.module, method_name),
                f"ArchitectModule must not expose '{method_name}' (4.1 Architectは実装しない)",
            )


if __name__ == "__main__":
    unittest.main()
