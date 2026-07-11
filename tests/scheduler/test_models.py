"""Scheduler(M14) models.pyのテスト(IS14仕様書7節 test_models.py)。"""

from __future__ import annotations

import dataclasses
import unittest
from datetime import UTC, datetime

from foundation.errors import ValidationError
from scheduler.models import (
    Event,
    EventType,
    ExecutionRequest,
    ScheduleDefinition,
    ScheduleFrequency,
    TriggerType,
)

_NOW = datetime(2026, 7, 11, 10, 0, 0, tzinfo=UTC)


class TestExecutionRequestDefaults(unittest.TestCase):
    def test_execution_request_default_retry_count_is_zero(self) -> None:
        request = ExecutionRequest(
            request_id="req-1",
            workflow_id="wf-1",
            trigger_type=TriggerType.MANUAL,
            source="cli",
            requested_at=_NOW,
        )
        self.assertEqual(request.retry_count, 0)


class TestScheduleDefinitionImmutability(unittest.TestCase):
    def test_schedule_definition_is_frozen_and_immutable(self) -> None:
        definition = ScheduleDefinition(
            workflow_id="wf-1",
            frequency=ScheduleFrequency.DAILY,
            time_of_day="09:00",
        )
        with self.assertRaises(dataclasses.FrozenInstanceError):
            definition.workflow_id = "wf-2"  # type: ignore[misc]


class TestEventValidation(unittest.TestCase):
    def test_event_requires_event_type_only_when_trigger_type_is_event(self) -> None:
        # trigger_type == EVENT なのにevent_type未設定 -> ValidationError
        with self.assertRaises(ValidationError):
            Event(
                workflow_id="wf-1",
                trigger_type=TriggerType.EVENT,
                source="github_webhook",
                occurred_at=_NOW,
                event_type=None,
            )

        # trigger_type == EVENT でevent_typeを設定していれば成功する
        event = Event(
            workflow_id="wf-1",
            trigger_type=TriggerType.EVENT,
            source="github_webhook",
            occurred_at=_NOW,
            event_type=EventType.PULL_REQUEST_MERGED,
        )
        self.assertEqual(event.event_type, EventType.PULL_REQUEST_MERGED)

        # trigger_type != EVENT の場合はevent_type未設定でも成功する(MANUAL/SCHEDULED)
        manual_event = Event(
            workflow_id="wf-1",
            trigger_type=TriggerType.MANUAL,
            source="cli",
            occurred_at=_NOW,
        )
        self.assertIsNone(manual_event.event_type)

        scheduled_event = Event(
            workflow_id="wf-1",
            trigger_type=TriggerType.SCHEDULED,
            source="scheduler",
            occurred_at=_NOW,
        )
        self.assertIsNone(scheduled_event.event_type)


if __name__ == "__main__":
    unittest.main()
