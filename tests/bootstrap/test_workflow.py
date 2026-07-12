"""合成Workflow(Planner→Architect→Design Auditor→Executor→Tester→PR Creator→
Reviewer)が最後まで直列に成功で流れることを検証する統合テスト。

外部サービスへの実接続は一切発生しない(すべてStub経由、`build_application()`の
既定配線をそのまま利用する)。
"""

import unittest

from bootstrap.wiring import build_application
from bootstrap.workflow import run_workflow
from planner.types import NormalizedRequest
from reviewer.domain import ReviewDecision


class RunWorkflowTest(unittest.TestCase):
    def test_synthetic_workflow_completes_through_reviewer(self) -> None:
        app = build_application()
        request = NormalizedRequest(
            workflow_id="wf-bootstrap-1",
            command="LP改善",
            request_text="LPの登録導線を改善してください。既存のデザインは維持すること。",
        )

        result = run_workflow(app, request, business_goal="LINE登録数最大化")

        self.assertTrue(result.success, msg=str(result.error))
        self.assertIsNotNone(result.value)
        outcome = result.value
        self.assertIsInstance(outcome.decision, ReviewDecision)
        self.assertIn(outcome.next_module, ("merge_manager", "executor"))
        self.assertTrue(outcome.review_id)


if __name__ == "__main__":
    unittest.main()
