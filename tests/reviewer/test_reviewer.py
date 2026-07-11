import unittest
from typing import Any

from foundation.errors import ConfigurationError
from foundation.interfaces import ConfigurationClient
from foundation.result import Result
from foundation.types import Implementation, PullRequest
from reviewer.domain import (
    BusinessEvaluation,
    ReviewDecision,
    ReviewOutcome,
    ReviewReport,
)
from reviewer.reviewer import ReviewerModule


class FakeConfigurationClient(ConfigurationClient):
    values: dict[str, Any] = {
        "min_business_score": 0.5,
        "blocker_severity_blocks_approval": True,
    }

    @staticmethod
    def get(module_name: str, key: str) -> Result[Any]:
        return Result(success=True, value=FakeConfigurationClient.values[key])


class FailingConfigurationClient(ConfigurationClient):
    @staticmethod
    def get(module_name: str, key: str) -> Result[Any]:
        return Result(success=False, error=ConfigurationError("configuration unavailable"))


class _LockedPullRequest(PullRequest):
    """review()がPull Requestを一切変更しないことを検証するための変異検知Spy。"""

    def __setattr__(self, name: str, value: Any) -> None:
        if name != "_locked" and object.__getattribute__(self, "__dict__").get("_locked"):
            raise AssertionError(f"ReviewerModule must not mutate PullRequest.{name}")
        object.__setattr__(self, name, value)


class _LockedImplementation(Implementation):
    """review()がImplementation(コード実装結果)を一切変更しないことを検証するSpy。"""

    def __setattr__(self, name: str, value: Any) -> None:
        if name != "_locked" and object.__getattribute__(self, "__dict__").get("_locked"):
            raise AssertionError(f"ReviewerModule must not mutate Implementation.{name}")
        object.__setattr__(self, name, value)


def _lock(instance: Any) -> Any:
    object.__setattr__(instance, "_locked", True)
    return instance


def _make_pull_request(
    *,
    implementation_result: Implementation | None = None,
    unmet_requirements: list[str] | None = None,
    design_deviations: list[str] | None = None,
    summary: str = "課金プランのアップグレード機能を追加",
    required_keywords: list[str] | None = None,
    documentation_updated: bool = True,
    technical_debt_items: list[dict[str, Any]] | None = None,
) -> PullRequest:
    impl = implementation_result or Implementation(metadata={"design_deviations": design_deviations or []})
    return PullRequest(
        metadata={
            "workflow_id": "wf-001",
            "execution_plan": {},
            "design_document": {"requirements": ["課金プランのアップグレード機能"]},
            "audit_report": {"technical_debt_items": technical_debt_items or []},
            "implementation_result": impl,
            "test_report": {"unmet_requirements": unmet_requirements or []},
            "project_context": {},
            "business_goal": {"required_keywords": required_keywords or ["課金", "アップグレード"]},
            "summary": summary,
            "documentation_updated": documentation_updated,
        }
    )


class ReviewerModuleNameTest(unittest.TestCase):
    def test_name_returns_reviewer(self) -> None:
        module = ReviewerModule(FakeConfigurationClient())
        self.assertEqual(module.name(), "reviewer")


class ReviewerModuleHealthCheckTest(unittest.TestCase):
    def test_health_check_returns_success_result_when_dependencies_ok(self) -> None:
        module = ReviewerModule(FakeConfigurationClient())
        result = module.health_check()
        self.assertTrue(result.success)
        self.assertTrue(result.value)


class ReviewerModuleReviewTest(unittest.TestCase):
    def test_review_returns_success_result_with_review_report(self) -> None:
        module = ReviewerModule(FakeConfigurationClient())
        result = module.review(_make_pull_request())
        self.assertTrue(result.success)
        self.assertIsInstance(result.value, ReviewReport)
        self.assertEqual(result.value.result, ReviewDecision.APPROVED)

    def test_review_returns_failure_result_when_pull_request_is_none(self) -> None:
        module = ReviewerModule(FakeConfigurationClient())
        result = module.review(None)
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)

    def test_review_report_contains_review_id_result_strengths_issues_technical_debt_business_evaluation_recommendations(
        self,
    ) -> None:
        module = ReviewerModule(FakeConfigurationClient())
        result = module.review(_make_pull_request())
        self.assertTrue(result.success)
        report = result.value
        self.assertTrue(hasattr(report, "id"))
        self.assertTrue(hasattr(report, "result"))
        self.assertTrue(hasattr(report, "strengths"))
        self.assertTrue(hasattr(report, "issues"))
        self.assertTrue(hasattr(report, "technical_debt"))
        self.assertTrue(hasattr(report, "business_evaluation"))
        self.assertTrue(hasattr(report, "recommendations"))
        self.assertIsInstance(report.business_evaluation, BusinessEvaluation)

    def test_review_does_not_call_any_code_modification_api(self) -> None:
        module = ReviewerModule(FakeConfigurationClient())
        self.assertFalse(hasattr(module, "modify_code"))
        self.assertFalse(hasattr(module, "apply_fix"))
        self.assertFalse(hasattr(module, "update_code"))
        self.assertFalse(hasattr(module, "generate_code"))

        locked_impl = _lock(_LockedImplementation(metadata={"design_deviations": []}))
        pull_request = _make_pull_request(implementation_result=locked_impl)
        result = module.review(pull_request)
        self.assertTrue(result.success)

    def test_review_does_not_call_any_pull_request_update_api(self) -> None:
        module = ReviewerModule(FakeConfigurationClient())
        self.assertFalse(hasattr(module, "update_pull_request"))
        self.assertFalse(hasattr(module, "merge_pull_request"))
        self.assertFalse(hasattr(module, "create_pull_request"))

        pull_request = _make_pull_request()
        locked_pull_request = _LockedPullRequest(id=pull_request.id, metadata=pull_request.metadata)
        _lock(locked_pull_request)
        result = module.review(locked_pull_request)
        self.assertTrue(result.success)

    def test_review_returns_failure_result_when_configuration_unavailable(self) -> None:
        module = ReviewerModule(FailingConfigurationClient())
        result = module.review(_make_pull_request())
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, ConfigurationError)


class ReviewerModuleEvaluateBusinessTest(unittest.TestCase):
    def test_evaluate_business_returns_success_result_with_business_evaluation(self) -> None:
        module = ReviewerModule(FakeConfigurationClient())
        pull_request = _make_pull_request()
        result = module.evaluate_business(pull_request)
        self.assertTrue(result.success)
        self.assertIsInstance(result.value, BusinessEvaluation)


class ReviewerModuleEvaluateMvpTest(unittest.TestCase):
    def test_evaluate_mvp_returns_success_result_with_mvp_assessment(self) -> None:
        module = ReviewerModule(FakeConfigurationClient())
        result = module.evaluate_mvp(Implementation())
        self.assertTrue(result.success)
        self.assertTrue(result.value.is_mvp_compliant)

    def test_evaluate_mvp_returns_failure_result_when_implementation_result_is_none(self) -> None:
        module = ReviewerModule(FakeConfigurationClient())
        result = module.evaluate_mvp(None)
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)


class ReviewerModulePublishReviewTest(unittest.TestCase):
    def _approved_report(self) -> ReviewReport:
        return ReviewReport(
            workflow_id="wf-001",
            result=ReviewDecision.APPROVED,
            business_evaluation=BusinessEvaluation(aligned_with_business_goal=True, business_score=1.0),
        )

    def _changes_requested_report(self) -> ReviewReport:
        return ReviewReport(
            workflow_id="wf-001",
            result=ReviewDecision.CHANGES_REQUESTED,
            business_evaluation=BusinessEvaluation(aligned_with_business_goal=True, business_score=1.0),
        )

    def test_publish_review_returns_success_result_with_review_outcome(self) -> None:
        module = ReviewerModule(FakeConfigurationClient())
        result = module.publish_review(self._approved_report())
        self.assertTrue(result.success)
        self.assertIsInstance(result.value, ReviewOutcome)

    def test_publish_review_routes_approved_decision_to_merge_manager(self) -> None:
        module = ReviewerModule(FakeConfigurationClient())
        result = module.publish_review(self._approved_report())
        self.assertEqual(result.value.next_module, "merge_manager")

    def test_publish_review_routes_changes_requested_decision_to_executor(self) -> None:
        module = ReviewerModule(FakeConfigurationClient())
        result = module.publish_review(self._changes_requested_report())
        self.assertEqual(result.value.next_module, "executor")

    def test_publish_review_does_not_execute_merge(self) -> None:
        module = ReviewerModule(FakeConfigurationClient())
        self.assertFalse(hasattr(module, "merge"))
        self.assertFalse(hasattr(module, "execute_merge"))
        self.assertFalse(hasattr(module, "merge_pull_request"))
        result = module.publish_review(self._approved_report())
        self.assertTrue(result.success)
        # next_moduleはあくまで次モジュール名の提示に留まり、マージは実行されない。
        self.assertEqual(result.value.next_module, "merge_manager")


if __name__ == "__main__":
    unittest.main()
