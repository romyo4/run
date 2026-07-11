"""designer.create_design()のテスト(IS07仕様書7節 test_designer.py)。"""

from __future__ import annotations

import unittest
from typing import Any

from architect import designer
from architect.errors import DesignCreationError
from architect.models import DesignRequirement, DesignStatus


def _make_requirement(**overrides: Any) -> DesignRequirement:
    defaults: dict[str, Any] = dict(
        requirement_id="req-1",
        workflow_id="wf-1",
        source_execution_plan_id="plan-1",
        objective="LPのファーストビューを改善する",
        constraints=["既存デザインを維持すること"],
        reusable_components=["auth_module", "payment_module"],
    )
    defaults.update(overrides)
    return DesignRequirement(**defaults)


class TestDesigner(unittest.TestCase):
    def test_create_design_produces_module_design_item_per_reusable_component(self) -> None:
        requirement = _make_requirement()
        result = designer.create_design(requirement)
        self.assertTrue(result.success)
        module_names = {module.module_name for module in result.value.module_design}
        for component in requirement.reusable_components:
            self.assertIn(component, module_names)
        # 再利用コンポーネント数 + 新規コアモジュール1件
        self.assertEqual(len(result.value.module_design), len(requirement.reusable_components) + 1)

    def test_create_design_produces_interface_design_matching_module_design(self) -> None:
        requirement = _make_requirement()
        result = designer.create_design(requirement)
        module_names = {module.module_name for module in result.value.module_design}
        self.assertEqual(len(result.value.interface_design), len(result.value.module_design))
        for interface in result.value.interface_design:
            self.assertIn(interface.owning_module, module_names)

    def test_create_design_copies_constraints_from_requirement(self) -> None:
        requirement = _make_requirement(constraints=["既存デザインを維持すること", "予算内で実施"])
        result = designer.create_design(requirement)
        self.assertEqual(result.value.constraints, requirement.constraints)
        # コピーであり同一リストではないこと(独立性)
        self.assertIsNot(result.value.constraints, requirement.constraints)

    def test_create_design_sets_reuse_rationale_when_existing_design_changed(self) -> None:
        requirement = _make_requirement(reusable_components=["auth_module"])
        result = designer.create_design(requirement)
        reused_modules = [m for m in result.value.module_design if not m.is_new]
        self.assertTrue(reused_modules)
        for module in reused_modules:
            self.assertTrue(module.reuse_rationale)

    def test_create_design_raises_design_creation_error_on_empty_requirement(self) -> None:
        requirement = _make_requirement(objective="")
        with self.assertRaises(DesignCreationError):
            designer.create_design(requirement)

    def test_create_design_sets_status_draft(self) -> None:
        requirement = _make_requirement()
        result = designer.create_design(requirement)
        self.assertEqual(result.value.status, DesignStatus.DRAFT)

    def test_create_design_populates_metadata_for_design_auditor(self) -> None:
        """Design Auditor(M08)の4監査が読み取るmetadataスキーマが構築されること
        (workflow_id: requirement_check/architecture_check等の前提, requirements/
        requirements_covered: requirement_check.py, features/content: mvp_check.py)。"""
        requirement = _make_requirement(
            functional_requirements=["task-1", "task-2"],
            non_functional_requirements=["性能要件"],
        )
        result = designer.create_design(requirement)
        metadata = result.value.metadata

        self.assertEqual(metadata["workflow_id"], requirement.workflow_id)
        self.assertEqual(metadata["requirements"], ["task-1", "task-2", "性能要件"])
        self.assertEqual(metadata["requirements_covered"], metadata["requirements"])
        self.assertEqual(metadata["features"], ["task-1", "task-2"])
        self.assertIn(requirement.objective, metadata["content"])

    def test_create_design_does_not_set_self_reported_violation_notes(self) -> None:
        """ArchitectはDesign Auditorの品質判定(architecture_notes/quality_notes)を
        自己申告しない(M07 4.3 Architectはレビューしない)。"""
        requirement = _make_requirement()
        result = designer.create_design(requirement)
        self.assertNotIn("architecture_notes", result.value.metadata)
        self.assertNotIn("quality_notes", result.value.metadata)


if __name__ == "__main__":
    unittest.main()
