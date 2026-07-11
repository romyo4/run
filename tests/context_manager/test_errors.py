import unittest

from context_manager.errors import (
    ContextConfigurationRetrievalError,
    ContextNotFoundError,
    ContextValidationError,
    KnowledgeRetrievalError,
    RepositoryContextRetrievalError,
)
from foundation.errors import (
    ConfigurationError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
)


class ContextNotFoundErrorTest(unittest.TestCase):
    def test_context_not_found_error_is_not_found_error_subclass(self) -> None:
        self.assertTrue(issubclass(ContextNotFoundError, NotFoundError))


class ContextValidationErrorTest(unittest.TestCase):
    def test_context_validation_error_is_validation_error_subclass(self) -> None:
        self.assertTrue(issubclass(ContextValidationError, ValidationError))


class KnowledgeRetrievalErrorTest(unittest.TestCase):
    def test_knowledge_retrieval_error_is_external_service_error_subclass(self) -> None:
        self.assertTrue(issubclass(KnowledgeRetrievalError, ExternalServiceError))


class ContextConfigurationRetrievalErrorTest(unittest.TestCase):
    def test_context_configuration_retrieval_error_is_configuration_error_subclass(self) -> None:
        self.assertTrue(issubclass(ContextConfigurationRetrievalError, ConfigurationError))


class RepositoryContextRetrievalErrorTest(unittest.TestCase):
    def test_repository_context_retrieval_error_is_external_service_error_subclass(self) -> None:
        self.assertTrue(issubclass(RepositoryContextRetrievalError, ExternalServiceError))


if __name__ == "__main__":
    unittest.main()
