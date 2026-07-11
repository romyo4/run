"""Scheduler(M14) logging_utils.pyのテスト(IS14仕様書7節 test_logging_utils.py)。

設計書4.5(Secret/Access Token/Credentialをログへ出力してはならない)を検証する。
"""

from __future__ import annotations

import logging
import unittest
from datetime import UTC, datetime

from scheduler.logging_utils import _MASK, log_execution, sanitize_payload

_NOW = datetime(2026, 7, 11, 10, 0, 0, tzinfo=UTC)


class TestSanitizePayload(unittest.TestCase):
    def test_sanitize_payload_masks_secret_and_token_fields(self) -> None:
        payload = {
            "secret": "top-secret-value",
            "access_token": "ghp_abcdef123456",
            "workflow_name": "LP改善",
        }

        sanitized = sanitize_payload(payload)

        self.assertEqual(sanitized["secret"], _MASK)
        self.assertEqual(sanitized["access_token"], _MASK)
        self.assertEqual(sanitized["workflow_name"], "LP改善")

    def test_sanitize_payload_masks_nested_credential_fields(self) -> None:
        payload = {
            "workflow_id": "wf-1",
            "auth": {
                "credential": "user:pass",
                "api_key": "sk-xxxxx",
                "nested": {"password": "hunter2", "note": "keep"},
            },
        }

        sanitized = sanitize_payload(payload)

        self.assertEqual(sanitized["auth"]["credential"], _MASK)
        self.assertEqual(sanitized["auth"]["api_key"], _MASK)
        self.assertEqual(sanitized["auth"]["nested"]["password"], _MASK)
        self.assertEqual(sanitized["auth"]["nested"]["note"], "keep")

    def test_sanitize_payload_preserves_non_sensitive_fields(self) -> None:
        payload = {"workflow_id": "wf-1", "source": "slack", "count": 3}

        sanitized = sanitize_payload(payload)

        self.assertEqual(sanitized, payload)


class TestLogExecution(unittest.TestCase):
    def test_log_execution_emits_required_six_fields_only(self) -> None:
        logger = logging.getLogger("scheduler.test_logging_utils")
        logger.setLevel(logging.INFO)

        with self.assertLogs("scheduler.test_logging_utils", level="INFO") as captured:
            log_execution(
                logger,
                workflow_id="wf-1",
                trigger_type="MANUAL",
                execution_result="SUCCESS",
                retry_count=0,
                duration_seconds=1.23,
                timestamp=_NOW,
            )

        self.assertEqual(len(captured.output), 1)
        message = captured.output[0]
        for field_marker in (
            "timestamp=",
            "workflow_id=wf-1",
            "trigger_type=MANUAL",
            "execution_result=SUCCESS",
            "retry_count=0",
            "duration=1.23",
        ):
            self.assertIn(field_marker, message)


if __name__ == "__main__":
    unittest.main()
