import unittest
from unittest.mock import patch

from context_manager.errors import (
    ContextConfigurationRetrievalError,
    ContextNotFoundError,
    KnowledgeRetrievalError,
    RepositoryContextRetrievalError,
)
from context_manager.manager import ContextManager
from context_manager.types import ContextRequest, WorkflowScope, WorkflowType

from .fakes import (
    FakeGitHubManager,
    FakeKnowledgeDocument,
    FakeKnowledgeManager,
    make_fake_configuration_client,
)


def _make_request(workflow_id: str = "wf-1") -> ContextRequest:
    scope = WorkflowScope(workflow_id=workflow_id, workflow_type=WorkflowType.PLANNER)
    return ContextRequest(
        workflow_id=workflow_id,
        workflow_type=WorkflowType.PLANNER,
        workflow_scope=scope,
        user_instruction="improve LP",
    )


def _make_manager(
    documents_by_category=None, knowledge_fail=False, github_fail=False, configuration_fail=False
) -> ContextManager:
    knowledge_manager = FakeKnowledgeManager(
        documents_by_category=documents_by_category
        or {"business_goal": [FakeKnowledgeDocument(category="business_goal", body="secret goal body")]},
        fail=knowledge_fail,
    )
    github_manager = FakeGitHubManager(repository_context={"repo": "example"}, fail=github_fail)
    configuration_client = make_fake_configuration_client(fail=configuration_fail)
    return ContextManager(
        knowledge_manager=knowledge_manager,
        github_manager=github_manager,
        configuration_client=configuration_client,
    )


class ContextManagerNameTest(unittest.TestCase):
    def test_name_returns_context_manager(self) -> None:
        manager = _make_manager()
        self.assertEqual(manager.name(), "context_manager")


class ContextManagerHealthCheckTest(unittest.TestCase):
    def test_health_check_returns_success_result_bool(self) -> None:
        manager = _make_manager()
        result = manager.health_check()
        self.assertTrue(result.success)
        self.assertIsInstance(result.value, bool)
        self.assertTrue(result.value)


class ContextManagerBuildTest(unittest.TestCase):
    def test_build_returns_ai_context_with_incremented_context_version(self) -> None:
        manager = _make_manager()
        request = _make_request()

        first = manager.build(request)
        second = manager.build(request)

        self.assertTrue(first.success)
        self.assertTrue(second.success)
        self.assertEqual(first.value.context_version, "v1")
        self.assertEqual(second.value.context_version, "v2")

    def test_build_returns_failure_result_when_knowledge_manager_call_fails(self) -> None:
        manager = _make_manager(knowledge_fail=True)
        result = manager.build(_make_request())

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, KnowledgeRetrievalError)

    def test_build_returns_failure_result_when_github_manager_call_fails(self) -> None:
        manager = _make_manager(github_fail=True)
        result = manager.build(_make_request())

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, RepositoryContextRetrievalError)

    def test_build_returns_failure_result_when_configuration_client_call_fails(self) -> None:
        manager = _make_manager(configuration_fail=True)
        result = manager.build(_make_request())

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, ContextConfigurationRetrievalError)

    def test_build_stores_result_retrievable_via_get(self) -> None:
        manager = _make_manager()
        request = _make_request()

        build_result = manager.build(request)
        get_result = manager.get(request.workflow_id)

        self.assertTrue(get_result.success)
        self.assertIs(get_result.value, build_result.value)

    def test_build_never_forwards_raw_knowledge_document_bodies_to_logger(self) -> None:
        manager = _make_manager()
        request = _make_request()

        with patch("context_manager.manager.log_build_result") as mocked_log:
            manager.build(request)

        self.assertEqual(mocked_log.call_count, 1)
        _, kwargs = mocked_log.call_args
        for value in kwargs.values():
            self.assertNotIsInstance(value, FakeKnowledgeDocument)
            self.assertNotIn("secret goal body", repr(value))


class ContextManagerSelectTest(unittest.TestCase):
    def test_select_public_method_returns_selected_context_for_given_workflow_type(self) -> None:
        manager = _make_manager()
        request = _make_request()

        result = manager.select(WorkflowType.PLANNER, request)

        self.assertTrue(result.success)
        self.assertEqual(result.value.workflow_type, WorkflowType.PLANNER)
        self.assertEqual(result.value.user_instruction, "improve LP")


class ContextManagerValidateTest(unittest.TestCase):
    def test_validate_public_method_wraps_validator_result(self) -> None:
        manager = _make_manager(
            documents_by_category={
                "business_goal": [FakeKnowledgeDocument(category="business_goal", body="goal")],
                "knowledge": [FakeKnowledgeDocument(category="knowledge", body="know")],
            }
        )
        request = _make_request()

        build_result = manager.build(request)
        validate_result = manager.validate(build_result.value)

        self.assertTrue(validate_result.success)
        self.assertTrue(validate_result.value.is_valid)


class ContextManagerGetTest(unittest.TestCase):
    def test_get_returns_failure_result_with_context_not_found_error_when_absent(self) -> None:
        manager = _make_manager()
        result = manager.get("unknown-workflow")

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, ContextNotFoundError)

    def test_get_returns_latest_built_context_for_known_workflow_id(self) -> None:
        manager = _make_manager()
        request = _make_request()

        manager.build(request)
        second_build = manager.build(request)
        result = manager.get(request.workflow_id)

        self.assertTrue(result.success)
        self.assertIs(result.value, second_build.value)


if __name__ == "__main__":
    unittest.main()
