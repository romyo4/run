import unittest

from context_manager.store import ContextStore
from context_manager.types import AIContext, WorkflowType


class StoreRoundTripTest(unittest.TestCase):
    def test_store_save_and_get_round_trip_returns_latest_context(self) -> None:
        store = ContextStore()
        first = AIContext(workflow_id="wf-1", workflow_type=WorkflowType.PLANNER, context_version="v1")
        second = AIContext(workflow_id="wf-1", workflow_type=WorkflowType.PLANNER, context_version="v2")

        store.save(first)
        store.save(second)

        self.assertIs(store.get("wf-1"), second)


class StoreUnknownWorkflowTest(unittest.TestCase):
    def test_store_get_returns_none_for_unknown_workflow_id(self) -> None:
        store = ContextStore()
        self.assertIsNone(store.get("unknown"))


class StoreVersionIncrementTest(unittest.TestCase):
    def test_store_next_version_increments_per_workflow_id(self) -> None:
        store = ContextStore()
        self.assertEqual(store.next_version("wf-1"), "v1")
        self.assertEqual(store.next_version("wf-1"), "v2")
        self.assertEqual(store.next_version("wf-1"), "v3")


class StoreVersionIndependenceTest(unittest.TestCase):
    def test_store_next_version_is_independent_across_different_workflow_ids(self) -> None:
        store = ContextStore()
        self.assertEqual(store.next_version("wf-1"), "v1")
        self.assertEqual(store.next_version("wf-2"), "v1")
        self.assertEqual(store.next_version("wf-1"), "v2")


if __name__ == "__main__":
    unittest.main()
