import unittest

from context_manager.ports import GitHubManagerPort, KnowledgeManagerPort
from context_manager.types import WorkflowScope, WorkflowType
from foundation.result import Result


class FakeKnowledgeManager:
    def get(self, document_id: str) -> Result:
        return Result(success=True, value={"id": document_id})

    def search(self, keyword: str) -> Result:
        return Result(success=True, value=[])

    def list_documents(self, category: str) -> Result:
        return Result(success=True, value=[])


class FakeGitHubManager:
    def build_repository_context(self, repository: str, workflow_scope: WorkflowScope) -> Result:
        return Result(success=True, value={"repository": repository, "scope": workflow_scope})


class KnowledgeManagerPortTest(unittest.TestCase):
    def test_knowledge_manager_port_accepts_conforming_fake_implementation(self) -> None:
        fake: KnowledgeManagerPort = FakeKnowledgeManager()
        self.assertTrue(fake.get("doc-1").success)
        self.assertTrue(fake.search("keyword").success)
        self.assertTrue(fake.list_documents("business_goal").success)


class GitHubManagerPortTest(unittest.TestCase):
    def test_github_manager_port_accepts_conforming_fake_implementation(self) -> None:
        fake: GitHubManagerPort = FakeGitHubManager()
        scope = WorkflowScope(workflow_id="wf-1", workflow_type=WorkflowType.EXECUTOR)
        result = fake.build_repository_context("owner/repo", scope)
        self.assertTrue(result.success)
        self.assertEqual(result.value["repository"], "owner/repo")
        self.assertEqual(result.value["scope"], scope)


if __name__ == "__main__":
    unittest.main()
