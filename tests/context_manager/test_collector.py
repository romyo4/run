import unittest

from context_manager import collector
from context_manager.errors import (
    ContextConfigurationRetrievalError,
    KnowledgeRetrievalError,
    RepositoryContextRetrievalError,
)
from context_manager.types import ContextRequest, WorkflowScope, WorkflowType

from .fakes import FakeGitHubManager, FakeKnowledgeManager, make_fake_configuration_client


def _make_request() -> ContextRequest:
    scope = WorkflowScope(workflow_id="wf-1", workflow_type=WorkflowType.PLANNER)
    return ContextRequest(workflow_id="wf-1", workflow_type=WorkflowType.PLANNER, workflow_scope=scope)


class CollectCallsKnowledgeManagerTest(unittest.TestCase):
    def test_collect_calls_knowledge_manager_list_documents_for_required_categories(self) -> None:
        knowledge_manager = FakeKnowledgeManager()
        github_manager = FakeGitHubManager()
        configuration_client = make_fake_configuration_client()

        result = collector.collect(_make_request(), knowledge_manager, github_manager, configuration_client)

        self.assertTrue(result.success)
        self.assertEqual(knowledge_manager.list_documents_calls, list(collector.REQUIRED_KNOWLEDGE_CATEGORIES))


class CollectCallsGitHubManagerTest(unittest.TestCase):
    def test_collect_calls_github_manager_build_repository_context_with_workflow_scope(
        self,
    ) -> None:
        knowledge_manager = FakeKnowledgeManager()
        github_manager = FakeGitHubManager()
        configuration_client = make_fake_configuration_client()
        request = _make_request()

        result = collector.collect(request, knowledge_manager, github_manager, configuration_client)

        self.assertTrue(result.success)
        self.assertEqual(github_manager.received_scopes, [request.workflow_scope])


class CollectCallsConfigurationClientTest(unittest.TestCase):
    def test_collect_calls_configuration_client_get_for_environment_only(self) -> None:
        knowledge_manager = FakeKnowledgeManager()
        github_manager = FakeGitHubManager()
        configuration_client = make_fake_configuration_client(environment="production")

        result = collector.collect(_make_request(), knowledge_manager, github_manager, configuration_client)

        self.assertTrue(result.success)
        self.assertEqual(configuration_client.calls, [(collector.MODULE_NAME, "system.environment")])
        self.assertEqual(result.value.environment, "production")


class CollectFailureTest(unittest.TestCase):
    def test_collect_returns_failure_result_when_knowledge_manager_call_fails(self) -> None:
        knowledge_manager = FakeKnowledgeManager(fail=True)
        github_manager = FakeGitHubManager()
        configuration_client = make_fake_configuration_client()

        result = collector.collect(_make_request(), knowledge_manager, github_manager, configuration_client)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, KnowledgeRetrievalError)

    def test_collect_returns_failure_result_when_github_manager_call_fails(self) -> None:
        knowledge_manager = FakeKnowledgeManager()
        github_manager = FakeGitHubManager(fail=True)
        configuration_client = make_fake_configuration_client()

        result = collector.collect(_make_request(), knowledge_manager, github_manager, configuration_client)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, RepositoryContextRetrievalError)

    def test_collect_returns_failure_result_when_configuration_client_call_fails(self) -> None:
        knowledge_manager = FakeKnowledgeManager()
        github_manager = FakeGitHubManager()
        configuration_client = make_fake_configuration_client(fail=True)

        result = collector.collect(_make_request(), knowledge_manager, github_manager, configuration_client)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, ContextConfigurationRetrievalError)


class CollectNoCachingTest(unittest.TestCase):
    def test_collect_does_not_cache_knowledge_documents_across_calls(self) -> None:
        knowledge_manager = FakeKnowledgeManager(documents_by_category={"business_goal": []})
        github_manager = FakeGitHubManager()
        configuration_client = make_fake_configuration_client()
        request = _make_request()

        first_result = collector.collect(request, knowledge_manager, github_manager, configuration_client)
        self.assertEqual(first_result.value.knowledge_documents, [])

        knowledge_manager.documents_by_category["business_goal"] = ["new-document"]
        second_result = collector.collect(request, knowledge_manager, github_manager, configuration_client)

        self.assertIn("new-document", second_result.value.knowledge_documents)


if __name__ == "__main__":
    unittest.main()
