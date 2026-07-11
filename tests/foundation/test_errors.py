import unittest

from foundation import errors, exceptions


class ErrorsTest(unittest.TestCase):
    def test_foundation_error_is_exception_subclass(self) -> None:
        self.assertTrue(issubclass(errors.FoundationError, Exception))

    def test_validation_error_is_foundation_error_subclass(self) -> None:
        self.assertTrue(issubclass(errors.ValidationError, errors.FoundationError))

    def test_not_found_error_is_foundation_error_subclass(self) -> None:
        self.assertTrue(issubclass(errors.NotFoundError, errors.FoundationError))

    def test_permission_denied_error_is_foundation_error_subclass(self) -> None:
        self.assertTrue(issubclass(errors.PermissionDeniedError, errors.FoundationError))

    def test_state_transition_error_is_foundation_error_subclass(self) -> None:
        self.assertTrue(issubclass(errors.StateTransitionError, errors.FoundationError))

    def test_configuration_error_is_foundation_error_subclass(self) -> None:
        self.assertTrue(issubclass(errors.ConfigurationError, errors.FoundationError))

    def test_external_service_error_is_foundation_error_subclass(self) -> None:
        self.assertTrue(issubclass(errors.ExternalServiceError, errors.FoundationError))

    def test_foundation_error_message_is_accessible(self) -> None:
        error = errors.FoundationError("boom")
        self.assertEqual(error.message, "boom")
        self.assertEqual(str(error), "boom")

    def test_exceptions_module_reexports_same_classes_as_errors_module(self) -> None:
        for name in exceptions.__all__:
            self.assertIs(getattr(exceptions, name), getattr(errors, name))


if __name__ == "__main__":
    unittest.main()
