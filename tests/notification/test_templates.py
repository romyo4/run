"""IS15 7. `tests/test_templates.py` に対応するテスト。"""

from __future__ import annotations

import inspect
import unittest

from notification import templates
from notification.errors import TemplateNotFoundError
from notification.templates import render_message_body
from notification.types import EventType, NotificationEvent

from .fakes import make_fake_configuration_client


class RenderWorkflowCompletedTest(unittest.TestCase):
    def test_render_message_body_workflow_completed(self) -> None:
        template_str = (
            "Workflow Completed\n\n"
            "Workflow:\n{workflow}\n\n"
            "Status:\n{status}\n\n"
            "Pull Request:\n{pull_request}\n\n"
            "Duration:\n{duration}"
        )
        config_client = make_fake_configuration_client({"workflow_completed": template_str})()
        event = NotificationEvent(
            workflow_id="wf-001",
            event_type=EventType.WORKFLOW_COMPLETED,
            event_result={
                "workflow": "LP Improvement",
                "status": "Completed",
                "pull_request": "#152",
                "duration": "8 min",
            },
            recipient="#dev-notifications",
            notification_template="workflow_completed",
            configuration={"channel": "slack"},
        )

        result = render_message_body(event, config_client)

        self.assertTrue(result.success)
        assert result.value is not None
        self.assertIn("LP Improvement", result.value)
        self.assertIn("Completed", result.value)
        self.assertIn("#152", result.value)
        self.assertIn("8 min", result.value)


class RenderReviewCompletedTest(unittest.TestCase):
    def test_render_message_body_review_completed(self) -> None:
        template_str = "Review Result\n\n{judgement}\n\nComment:\n{comment}"
        config_client = make_fake_configuration_client({"review_completed": template_str})()
        event = NotificationEvent(
            workflow_id="wf-002",
            event_type=EventType.REVIEW_COMPLETED,
            event_result={
                "judgement": "APPROVED",
                "comment": "Business Goalと一致しています。",
            },
            recipient="#dev-notifications",
            notification_template="review_completed",
            configuration={"channel": "discord"},
        )

        result = render_message_body(event, config_client)

        self.assertTrue(result.success)
        assert result.value is not None
        self.assertIn("APPROVED", result.value)
        self.assertIn("Business Goalと一致しています。", result.value)


class RenderWeeklyReviewTest(unittest.TestCase):
    def test_render_message_body_weekly_review(self) -> None:
        template_str = (
            "Weekly Review Completed\n\n" "Top Priority\n\n{top_priority}\n\n" "Technical Debt\n\n{technical_debt_count}件"
        )
        config_client = make_fake_configuration_client({"weekly_review": template_str})()
        event = NotificationEvent(
            workflow_id="wf-003",
            event_type=EventType.WEEKLY_REVIEW_COMPLETED,
            event_result={
                "top_priority": "LP First View改善",
                "technical_debt_count": 2,
            },
            recipient="team@example.com",
            notification_template="weekly_review",
            configuration={"channel": "email"},
        )

        result = render_message_body(event, config_client)

        self.assertTrue(result.success)
        assert result.value is not None
        self.assertIn("LP First View改善", result.value)
        self.assertIn("2件", result.value)


class RenderTemplateNotFoundTest(unittest.TestCase):
    def test_render_message_body_template_not_found_returns_error(self) -> None:
        config_client = make_fake_configuration_client({})()
        event = NotificationEvent(
            workflow_id="wf-004",
            event_type=EventType.SYSTEM_ERROR,
            event_result={},
            recipient="#dev-notifications",
            notification_template="does_not_exist",
            configuration={"channel": "slack"},
        )

        result = render_message_body(event, config_client)

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, TemplateNotFoundError)


class NoHardcodedTemplateInCodeTest(unittest.TestCase):
    def test_render_message_body_no_hardcoded_template_in_code(self) -> None:
        source = inspect.getsource(templates)

        forbidden_snippets = [
            "Workflow Completed",
            "Review Result",
            "APPROVED",
            "Weekly Review Completed",
            "Top Priority",
            "Technical Debt",
        ]
        for snippet in forbidden_snippets:
            self.assertNotIn(
                snippet,
                source,
                msg=f"templates.py にテンプレート文字列 {snippet!r} が直書きされています(4.4違反)",
            )


if __name__ == "__main__":
    unittest.main()
