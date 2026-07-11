import unittest

from foundation.errors import ValidationError
from foundation.validation import require_in, require_non_empty, require_not_none, validate


class ValidationTest(unittest.TestCase):
    def test_require_not_none_passes_for_non_none_value(self) -> None:
        require_not_none("value", "field")  # should not raise

    def test_require_not_none_raises_validation_error_for_none(self) -> None:
        with self.assertRaises(ValidationError):
            require_not_none(None, "field")

    def test_require_non_empty_passes_for_non_empty_value(self) -> None:
        require_non_empty("value", "field")  # should not raise

    def test_require_non_empty_raises_validation_error_for_empty_string(self) -> None:
        with self.assertRaises(ValidationError):
            require_non_empty("", "field")

    def test_require_non_empty_raises_validation_error_for_empty_collection(self) -> None:
        with self.assertRaises(ValidationError):
            require_non_empty([], "field")

    def test_require_in_passes_for_allowed_value(self) -> None:
        require_in("a", ["a", "b"], "field")  # should not raise

    def test_require_in_raises_validation_error_for_disallowed_value(self) -> None:
        with self.assertRaises(ValidationError):
            require_in("c", ["a", "b"], "field")

    def test_validate_returns_success_result_when_rule_passes(self) -> None:
        result = validate(5, lambda v: v > 0)
        self.assertTrue(result.success)
        self.assertTrue(result.value)

    def test_validate_returns_failure_result_when_rule_fails(self) -> None:
        result = validate(-5, lambda v: v > 0)
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, ValidationError)

    def test_validate_wraps_rule_exception_into_validation_error(self) -> None:
        def broken_rule(_: int) -> bool:
            raise RuntimeError("rule broke")

        result = validate(1, broken_rule)
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, ValidationError)


if __name__ == "__main__":
    unittest.main()
