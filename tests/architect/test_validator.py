"""validator.validate_design()のテスト(IS07仕様書7節 test_validator.py)。"""

from __future__ import annotations

import inspect
import unittest

from architect import validator
from architect.models import (
    DesignDocument,
    InterfaceDesignItem,
    ModuleDesignItem,
    ValidationStatus,
)


def _make_valid_document() -> DesignDocument:
    return DesignDocument(
        objective="LPのファーストビューを改善する",
        module_design=[
            ModuleDesignItem(module_name="m1", responsibility="コア機能"),
        ],
        interface_design=[
            InterfaceDesignItem(
                interface_name="m1_interface",
                owning_module="m1",
                input_spec="TBD",
                output_spec="TBD",
            )
        ],
    )


class TestValidator(unittest.TestCase):
    def test_validate_design_detects_missing_objective(self) -> None:
        document = _make_valid_document()
        document.objective = ""
        result = validator.validate_design(document)
        self.assertTrue(result.success)
        self.assertEqual(result.value.status, ValidationStatus.INVALID)
        self.assertTrue(any(issue.field_name == "objective" for issue in result.value.issues))

    def test_validate_design_detects_empty_module_design(self) -> None:
        document = _make_valid_document()
        document.module_design = []
        document.interface_design = []
        result = validator.validate_design(document)
        self.assertEqual(result.value.status, ValidationStatus.INVALID)
        self.assertTrue(any(issue.field_name == "module_design" for issue in result.value.issues))

    def test_validate_design_detects_interface_without_matching_module(self) -> None:
        document = _make_valid_document()
        document.interface_design = [
            InterfaceDesignItem(
                interface_name="orphan_interface",
                owning_module="nonexistent_module",
                input_spec="TBD",
                output_spec="TBD",
            )
        ]
        result = validator.validate_design(document)
        self.assertEqual(result.value.status, ValidationStatus.INVALID)
        self.assertTrue(any(issue.field_name == "interface_design" for issue in result.value.issues))

    def test_validate_design_returns_valid_when_all_required_fields_present(self) -> None:
        document = _make_valid_document()
        result = validator.validate_design(document)
        self.assertTrue(result.success)
        self.assertEqual(result.value.status, ValidationStatus.VALID)
        self.assertEqual(result.value.issues, [])

    def test_validate_design_does_not_assess_mvp_conformance(self) -> None:
        # MVP範囲逸脱(重厚壮大化)であっても構造的に完全であればVALIDを返す
        # (MVP適合性判定はDesign Auditorの責務。4.3節境界確認)。
        document = _make_valid_document()
        document.module_design.extend(
            ModuleDesignItem(module_name=f"extra_module_{i}", responsibility="over-engineered") for i in range(20)
        )
        result = validator.validate_design(document)
        self.assertEqual(result.value.status, ValidationStatus.VALID)

    def test_validate_design_does_not_assess_requirement_fulfillment(self) -> None:
        # validate_design はDesign Documentのみを引数に取り、元のRequirementとの
        # 突合(要求充足度判定)は行わない(4.3節境界確認)。
        signature = inspect.signature(validator.validate_design)
        self.assertEqual(list(signature.parameters), ["design_document"])

        document = _make_valid_document()
        # objectiveの内容がどのような要求文言であっても、構造さえ整っていればVALID
        document.objective = "要求内容とは無関係な文言"
        result = validator.validate_design(document)
        self.assertEqual(result.value.status, ValidationStatus.VALID)


if __name__ == "__main__":
    unittest.main()
