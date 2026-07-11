"""State Manager (M01) のunittestテストケース(IS01 7章)。"""

from __future__ import annotations

import threading
import time
import unittest
from typing import Any

from foundation.errors import NotFoundError, StateTransitionError
from foundation.interfaces import ConfigurationClient
from foundation.result import Result
from foundation.utils import utc_now
from state_manager import StateManager, TaskState, TaskStateEnum
from state_manager.exceptions import StateLockTimeoutError
from state_manager.models import TERMINAL_STATES
from state_manager.transitions import ALLOWED_TRANSITIONS

NON_TERMINAL_STATES = [state for state in TaskStateEnum if state not in TERMINAL_STATES]

# 正常系の直線遷移経路(設計書3.2)。
LINEAR_CHAIN = [
    TaskStateEnum.CREATED,
    TaskStateEnum.PLANNING,
    TaskStateEnum.DESIGNING,
    TaskStateEnum.DESIGN_REVIEW,
    TaskStateEnum.WAITING_APPROVAL,
    TaskStateEnum.EXECUTING,
    TaskStateEnum.TESTING,
    TaskStateEnum.REVIEWING,
    TaskStateEnum.PR_CREATED,
    TaskStateEnum.MERGED,
    TaskStateEnum.COMPLETED,
]


class FakeConfigurationClient(ConfigurationClient):
    """テスト用のConfigurationClient実装。get()は常にResult(success=True)を返す。"""

    def __init__(self, lock_timeout_seconds: float | None = None) -> None:
        self._lock_timeout_seconds = lock_timeout_seconds

    def get(self, module_name: str, key: str) -> Result[Any]:  # type: ignore[override]
        if key == "lock_timeout_seconds" and self._lock_timeout_seconds is not None:
            return Result(success=True, value=self._lock_timeout_seconds)
        return Result(success=True, value=None)


class FailingConfigurationClient(ConfigurationClient):
    """get()が常に失敗するConfigurationClient実装(ConfigurationErrorの伝播確認用)。"""

    def get(self, module_name: str, key: str) -> Result[Any]:  # type: ignore[override]
        from foundation.errors import ConfigurationError

        return Result(success=False, error=ConfigurationError(f"no config for {module_name}.{key}"))


class StateManagerTestBase(unittest.TestCase):
    def _make_manager(self, lock_timeout_seconds: float | None = None) -> StateManager:
        return StateManager(FakeConfigurationClient(lock_timeout_seconds))

    def _seed(
        self,
        manager: StateManager,
        task_id: str,
        state: TaskStateEnum,
        previous_state: TaskStateEnum | None = None,
        workflow_id: str | None = "wf-1",
    ) -> TaskState:
        record = TaskState(
            task_id=task_id,
            workflow_id=workflow_id,
            current_state=state,
            previous_state=previous_state,
            updated_at=utc_now(),
            updated_by="test-setup",
        )
        append_result = manager._store.append(record)
        self.assertTrue(append_result.success)
        return record


class TransitionHappyPathTest(StateManagerTestBase):
    """7.1 全状態遷移(正常系)。"""

    def _assert_transition_succeeds(self, current: TaskStateEnum, target: TaskStateEnum) -> None:
        manager = self._make_manager()
        task_id = "task-1"
        self._seed(manager, task_id, current)

        result = manager.transition(task_id, target, updated_by="tester", reason="unit-test")

        self.assertTrue(result.success, msg=result.error)
        assert result.value is not None
        self.assertEqual(result.value.current_state, target)
        self.assertEqual(result.value.previous_state, current)
        self.assertEqual(result.value.updated_by, "tester")

    def test_transition_created_to_planning_succeeds(self) -> None:
        self._assert_transition_succeeds(TaskStateEnum.CREATED, TaskStateEnum.PLANNING)

    def test_transition_planning_to_designing_succeeds(self) -> None:
        self._assert_transition_succeeds(TaskStateEnum.PLANNING, TaskStateEnum.DESIGNING)

    def test_transition_designing_to_design_review_succeeds(self) -> None:
        self._assert_transition_succeeds(TaskStateEnum.DESIGNING, TaskStateEnum.DESIGN_REVIEW)

    def test_transition_design_review_to_waiting_approval_succeeds(self) -> None:
        self._assert_transition_succeeds(TaskStateEnum.DESIGN_REVIEW, TaskStateEnum.WAITING_APPROVAL)

    def test_transition_waiting_approval_to_executing_succeeds(self) -> None:
        self._assert_transition_succeeds(TaskStateEnum.WAITING_APPROVAL, TaskStateEnum.EXECUTING)

    def test_transition_executing_to_testing_succeeds(self) -> None:
        self._assert_transition_succeeds(TaskStateEnum.EXECUTING, TaskStateEnum.TESTING)

    def test_transition_testing_to_reviewing_succeeds(self) -> None:
        self._assert_transition_succeeds(TaskStateEnum.TESTING, TaskStateEnum.REVIEWING)

    def test_transition_reviewing_to_pr_created_succeeds(self) -> None:
        self._assert_transition_succeeds(TaskStateEnum.REVIEWING, TaskStateEnum.PR_CREATED)

    def test_transition_pr_created_to_merged_succeeds(self) -> None:
        self._assert_transition_succeeds(TaskStateEnum.PR_CREATED, TaskStateEnum.MERGED)

    def test_transition_merged_to_completed_succeeds(self) -> None:
        self._assert_transition_succeeds(TaskStateEnum.MERGED, TaskStateEnum.COMPLETED)

    def test_transition_any_non_terminal_state_to_failed_succeeds(self) -> None:
        for state in NON_TERMINAL_STATES:
            with self.subTest(state=state):
                self._assert_transition_succeeds(state, TaskStateEnum.FAILED)

    def test_transition_any_non_terminal_state_to_cancelled_succeeds(self) -> None:
        for state in NON_TERMINAL_STATES:
            with self.subTest(state=state):
                self._assert_transition_succeeds(state, TaskStateEnum.CANCELLED)


class TransitionRejectionTest(StateManagerTestBase):
    """7.2 不正遷移拒否。"""

    def _assert_transition_rejected(self, current: TaskStateEnum, target: TaskStateEnum) -> Result[TaskState]:
        manager = self._make_manager()
        task_id = "task-1"
        self._seed(manager, task_id, current)

        result = manager.transition(task_id, target)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, StateTransitionError)
        return result

    def test_transition_completed_to_executing_rejected(self) -> None:
        self._assert_transition_rejected(TaskStateEnum.COMPLETED, TaskStateEnum.EXECUTING)

    def test_transition_failed_to_testing_rejected(self) -> None:
        self._assert_transition_rejected(TaskStateEnum.FAILED, TaskStateEnum.TESTING)

    def test_transition_merged_to_planning_rejected(self) -> None:
        self._assert_transition_rejected(TaskStateEnum.MERGED, TaskStateEnum.PLANNING)

    def test_transition_from_completed_to_any_state_rejected(self) -> None:
        for state in TaskStateEnum:
            if state is TaskStateEnum.COMPLETED:
                continue
            with self.subTest(state=state):
                self._assert_transition_rejected(TaskStateEnum.COMPLETED, state)

    def test_transition_from_failed_to_any_state_rejected(self) -> None:
        for state in TaskStateEnum:
            if state is TaskStateEnum.FAILED:
                continue
            with self.subTest(state=state):
                self._assert_transition_rejected(TaskStateEnum.FAILED, state)

    def test_transition_from_cancelled_to_any_state_rejected(self) -> None:
        for state in TaskStateEnum:
            if state is TaskStateEnum.CANCELLED:
                continue
            with self.subTest(state=state):
                self._assert_transition_rejected(TaskStateEnum.CANCELLED, state)

    def test_transition_skipping_intermediate_state_rejected(self) -> None:
        self._assert_transition_rejected(TaskStateEnum.CREATED, TaskStateEnum.DESIGNING)

    def test_transition_unknown_task_id_returns_not_found_error(self) -> None:
        manager = self._make_manager()

        result = manager.transition("does-not-exist", TaskStateEnum.PLANNING)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, NotFoundError)

    def test_transition_returns_state_transition_error_on_invalid_move(self) -> None:
        result = self._assert_transition_rejected(TaskStateEnum.CREATED, TaskStateEnum.REVIEWING)
        self.assertIsInstance(result.error, StateTransitionError)

    def test_allowed_transitions_table_matches_linear_chain(self) -> None:
        # 遷移表がIS01/設計書の直線経路と一致していることの確認(回帰防止)。
        for current_state, next_state in zip(LINEAR_CHAIN, LINEAR_CHAIN[1:]):
            self.assertIn(next_state, ALLOWED_TRANSITIONS[current_state])


class ConcurrencyTest(StateManagerTestBase):
    """7.3 並列更新(排他制御)。"""

    def test_concurrent_transition_same_task_id_is_serialized(self) -> None:
        manager = self._make_manager()
        task_id = "task-concurrent"
        self._seed(manager, task_id, TaskStateEnum.CREATED)

        results: list[Result[TaskState]] = []
        results_lock = threading.Lock()

        def worker() -> None:
            result = manager.transition(task_id, TaskStateEnum.PLANNING, updated_by="worker")
            with results_lock:
                results.append(result)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        successes = [r for r in results if r.success]
        failures = [r for r in results if not r.success]

        # ロックにより厳密に直列化されるため、Created→Planningに成功できるのは1件のみ。
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 4)
        for failure in failures:
            self.assertIsInstance(failure.error, StateTransitionError)

        final_state = manager.get_state(task_id)
        self.assertTrue(final_state.success)
        assert final_state.value is not None
        self.assertEqual(final_state.value.current_state, TaskStateEnum.PLANNING)

        history_result = manager.history(task_id)
        assert history_result.value is not None
        # Created(seed) + Planning(唯一の成功)の2件のみで、重複や破損がないこと。
        self.assertEqual(len(history_result.value), 2)

    def test_concurrent_transition_different_task_ids_do_not_block_each_other(self) -> None:
        manager = self._make_manager()
        task_a = "task-a"
        task_b = "task-b"
        self._seed(manager, task_a, TaskStateEnum.CREATED)
        self._seed(manager, task_b, TaskStateEnum.CREATED)

        lock_result = manager._store.acquire_lock(task_a, timeout_seconds=5.0)
        self.assertTrue(lock_result.success)

        try:
            result_holder: dict[str, Result[TaskState]] = {}

            def worker() -> None:
                result_holder["result"] = manager.transition(task_b, TaskStateEnum.PLANNING)

            thread = threading.Thread(target=worker)
            start = time.monotonic()
            thread.start()
            thread.join(timeout=2.0)
            elapsed = time.monotonic() - start

            self.assertFalse(thread.is_alive(), "task_bの遷移がtask_aのロックにブロックされている")
            self.assertLess(elapsed, 2.0)
            self.assertTrue(result_holder["result"].success)
        finally:
            manager._store.release_lock(task_a)

    def test_transition_raises_lock_timeout_when_lock_held_too_long(self) -> None:
        manager = self._make_manager(lock_timeout_seconds=0.2)
        task_id = "task-locked"
        self._seed(manager, task_id, TaskStateEnum.CREATED)

        lock_result = manager._store.acquire_lock(task_id, timeout_seconds=5.0)
        self.assertTrue(lock_result.success)

        try:
            result = manager.transition(task_id, TaskStateEnum.PLANNING)
            self.assertFalse(result.success)
            self.assertIsInstance(result.error, StateLockTimeoutError)
        finally:
            manager._store.release_lock(task_id)


class RollbackTest(StateManagerTestBase):
    """7.4 ロールバック。"""

    def test_rollback_reverts_to_previous_state(self) -> None:
        manager = self._make_manager()
        task_id = "task-1"
        self._seed(manager, task_id, TaskStateEnum.CREATED)
        transition_result = manager.transition(task_id, TaskStateEnum.PLANNING)
        self.assertTrue(transition_result.success)

        rollback_result = manager.rollback(task_id)

        self.assertTrue(rollback_result.success)
        assert rollback_result.value is not None
        self.assertEqual(rollback_result.value.current_state, TaskStateEnum.CREATED)
        self.assertEqual(rollback_result.value.previous_state, TaskStateEnum.PLANNING)

    def test_rollback_without_previous_state_returns_error(self) -> None:
        manager = self._make_manager()
        task_id = "task-1"
        self._seed(manager, task_id, TaskStateEnum.CREATED, previous_state=None)

        result = manager.rollback(task_id)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, StateTransitionError)

    def test_rollback_unknown_task_id_returns_not_found_error(self) -> None:
        manager = self._make_manager()

        result = manager.rollback("does-not-exist")

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, NotFoundError)

    def test_rollback_is_recorded_in_history(self) -> None:
        manager = self._make_manager()
        task_id = "task-1"
        self._seed(manager, task_id, TaskStateEnum.CREATED)
        manager.transition(task_id, TaskStateEnum.PLANNING)

        history_before = manager.history(task_id)
        assert history_before.value is not None
        count_before = len(history_before.value)

        rollback_result = manager.rollback(task_id)
        self.assertTrue(rollback_result.success)

        history_after = manager.history(task_id)
        assert history_after.value is not None
        self.assertEqual(len(history_after.value), count_before + 1)
        self.assertEqual(history_after.value[-1].current_state, TaskStateEnum.CREATED)


class HistoryTest(StateManagerTestBase):
    """7.5 履歴保存。"""

    def test_history_returns_all_recorded_states_in_chronological_order(self) -> None:
        manager = self._make_manager()
        task_id = "task-1"
        self._seed(manager, task_id, TaskStateEnum.CREATED)
        manager.transition(task_id, TaskStateEnum.PLANNING)
        manager.transition(task_id, TaskStateEnum.DESIGNING)

        result = manager.history(task_id)

        self.assertTrue(result.success)
        assert result.value is not None
        states_in_order = [record.current_state for record in result.value]
        self.assertEqual(
            states_in_order,
            [TaskStateEnum.CREATED, TaskStateEnum.PLANNING, TaskStateEnum.DESIGNING],
        )

    def test_history_unknown_task_id_returns_not_found_error(self) -> None:
        manager = self._make_manager()

        result = manager.history("does-not-exist")

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, NotFoundError)

    def test_history_reflects_multiple_transitions(self) -> None:
        manager = self._make_manager()
        task_id = "task-1"
        self._seed(manager, task_id, TaskStateEnum.CREATED)
        manager.transition(task_id, TaskStateEnum.PLANNING)
        manager.transition(task_id, TaskStateEnum.DESIGNING)
        manager.transition(task_id, TaskStateEnum.FAILED)

        result = manager.history(task_id)

        assert result.value is not None
        self.assertEqual(len(result.value), 4)
        self.assertEqual(result.value[-1].current_state, TaskStateEnum.FAILED)


class OtherPublicInterfaceTest(StateManagerTestBase):
    """7.6 その他公開インターフェース。"""

    def test_get_state_returns_latest_state(self) -> None:
        manager = self._make_manager()
        task_id = "task-1"
        self._seed(manager, task_id, TaskStateEnum.CREATED)
        manager.transition(task_id, TaskStateEnum.PLANNING)

        result = manager.get_state(task_id)

        self.assertTrue(result.success)
        assert result.value is not None
        self.assertEqual(result.value.current_state, TaskStateEnum.PLANNING)

    def test_get_state_unknown_task_id_returns_not_found_error(self) -> None:
        manager = self._make_manager()

        result = manager.get_state("does-not-exist")

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, NotFoundError)

    def test_list_running_excludes_terminal_states(self) -> None:
        manager = self._make_manager()
        self._seed(manager, "task-running-1", TaskStateEnum.EXECUTING)
        self._seed(manager, "task-running-2", TaskStateEnum.PLANNING)
        self._seed(manager, "task-completed", TaskStateEnum.COMPLETED)
        self._seed(manager, "task-failed", TaskStateEnum.FAILED)
        self._seed(manager, "task-cancelled", TaskStateEnum.CANCELLED)

        result = manager.list_running()

        self.assertTrue(result.success)
        assert result.value is not None
        running_ids = {record.task_id for record in result.value}
        self.assertEqual(running_ids, {"task-running-1", "task-running-2"})

    def test_list_running_returns_empty_list_when_no_tasks(self) -> None:
        manager = self._make_manager()

        result = manager.list_running()

        self.assertTrue(result.success)
        self.assertEqual(result.value, [])

    def test_health_check_returns_success(self) -> None:
        manager = self._make_manager()

        result = manager.health_check()

        self.assertTrue(result.success)
        self.assertTrue(result.value)

    def test_name_returns_module_name(self) -> None:
        manager = self._make_manager()
        self.assertEqual(manager.name(), "state_manager")

    def test_configuration_error_propagates_when_backend_config_resolution_fails(self) -> None:
        with self.assertRaises(Exception):
            StateManager(FailingConfigurationClient())


if __name__ == "__main__":
    unittest.main()
