"""publisher.publish_design()のテスト(IS07仕様書7節 test_publisher.py)。"""

from __future__ import annotations

import unittest

from architect import publisher
from architect.errors import DesignValidationError
from architect.models import (
    DesignDocument,
    DesignStatus,
    ModuleDesignItem,
    ValidatedDesign,
    ValidationResult,
    ValidationStatus,
)


def _make_document(**overrides: object) -> DesignDocument:
    defaults: dict[str, object] = dict(
        objective="obj",
        module_design=[ModuleDesignItem(module_name="m1", responsibility="r1")],
        status=DesignStatus.DRAFT,
    )
    defaults.update(overrides)
    return DesignDocument(**defaults)


class TestPublisher(unittest.TestCase):
    def test_publish_design_sets_status_published(self) -> None:
        document = _make_document()
        validation = ValidationResult(validation_id="v1", design_id=document.id, status=ValidationStatus.VALID)
        validated = ValidatedDesign(design_document=document, validation_result=validation)

        result = publisher.publish_design(validated)

        self.assertTrue(result.success)
        self.assertEqual(result.value.status, DesignStatus.PUBLISHED)

    def test_publish_design_preserves_design_id(self) -> None:
        document = _make_document()
        original_id = document.id
        validation = ValidationResult(validation_id="v1", design_id=document.id, status=ValidationStatus.VALID)
        validated = ValidatedDesign(design_document=document, validation_result=validation)

        result = publisher.publish_design(validated)

        self.assertEqual(result.value.id, original_id)

    def test_publish_design_rejects_when_validation_status_invalid(self) -> None:
        document = _make_document()
        validation = ValidationResult(validation_id="v1", design_id=document.id, status=ValidationStatus.INVALID)
        validated = ValidatedDesign(design_document=document, validation_result=validation)

        result = publisher.publish_design(validated)

        self.assertFalse(result.success)
        self.assertIsNone(result.value)
        self.assertIsInstance(result.error, DesignValidationError)
        # Publishが拒否された場合、元のDocumentのstatusは変更されない(F00 Safety)。
        self.assertEqual(document.status, DesignStatus.DRAFT)

    def test_publish_design_returns_result_wrapping_design_document(self) -> None:
        document = _make_document()
        validation = ValidationResult(validation_id="v1", design_id=document.id, status=ValidationStatus.VALID)
        validated = ValidatedDesign(design_document=document, validation_result=validation)

        result = publisher.publish_design(validated)

        self.assertIsInstance(result.value, DesignDocument)


if __name__ == "__main__":
    unittest.main()
