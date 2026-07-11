"""Architect固有例外のテスト(IS07仕様書7節 test_errors.py)。"""

from __future__ import annotations

import unittest

from architect.errors import (
    DesignCreationError,
    DesignNotFoundError,
    DesignValidationError,
    PlanAnalysisError,
)
from foundation.errors import NotFoundError, ValidationError


class TestErrors(unittest.TestCase):
    def test_plan_analysis_error_is_validation_error_subclass(self) -> None:
        self.assertTrue(issubclass(PlanAnalysisError, ValidationError))

    def test_design_creation_error_is_validation_error_subclass(self) -> None:
        self.assertTrue(issubclass(DesignCreationError, ValidationError))

    def test_design_validation_error_is_validation_error_subclass(self) -> None:
        self.assertTrue(issubclass(DesignValidationError, ValidationError))

    def test_design_not_found_error_is_not_found_error_subclass(self) -> None:
        self.assertTrue(issubclass(DesignNotFoundError, NotFoundError))


if __name__ == "__main__":
    unittest.main()
