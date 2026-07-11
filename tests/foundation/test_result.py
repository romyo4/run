import unittest

from foundation.errors import ValidationError
from foundation.result import Result


class ResultTest(unittest.TestCase):
    def test_result_success_holds_value(self) -> None:
        result = Result(success=True, value=42)
        self.assertTrue(result.success)
        self.assertEqual(result.value, 42)

    def test_result_failure_holds_error(self) -> None:
        error = ValidationError("bad input")
        result = Result(success=False, error=error)
        self.assertFalse(result.success)
        self.assertIs(result.error, error)

    def test_result_value_defaults_to_none(self) -> None:
        self.assertIsNone(Result(success=True).value)

    def test_result_error_defaults_to_none(self) -> None:
        self.assertIsNone(Result(success=True).error)

    def test_result_is_generic_and_accepts_any_value_type(self) -> None:
        self.assertEqual(Result(success=True, value=[1, 2, 3]).value, [1, 2, 3])
        self.assertEqual(Result(success=True, value="text").value, "text")


if __name__ == "__main__":
    unittest.main()
