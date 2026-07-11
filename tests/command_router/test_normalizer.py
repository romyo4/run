"""normalizer.normalize()のテスト(IS05仕様書7節)。"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from command_router.models import RawCommand
from command_router.normalizer import normalize
from foundation.errors import ValidationError


def _make_raw(**overrides: object) -> RawCommand:
    defaults: dict[str, object] = dict(
        command_id="cmd-1",
        source="cli",
        user_id="user-1",
        timestamp=datetime(2026, 7, 11, 10, 0, 0, tzinfo=UTC),
        command="plan LP改善",
        attachments=[],
        metadata={},
    )
    defaults.update(overrides)
    return RawCommand(**defaults)  # type: ignore[arg-type]


class TestNormalizer(unittest.TestCase):
    def test_receive_slack_command_strips_slash_prefix(self) -> None:
        raw = _make_raw(source="slack", command="/plan LP改善")
        result = normalize(raw)
        self.assertTrue(result.success)
        self.assertEqual(result.value.raw_text, "plan LP改善")

    def test_receive_discord_command_strips_at_bot_prefix(self) -> None:
        raw = _make_raw(source="discord", command="@bot plan LP改善")
        result = normalize(raw)
        self.assertTrue(result.success)
        self.assertEqual(result.value.raw_text, "plan LP改善")

    def test_receive_cli_command_passthrough_without_prefix(self) -> None:
        raw = _make_raw(source="cli", command="plan LP改善")
        result = normalize(raw)
        self.assertTrue(result.success)
        self.assertEqual(result.value.raw_text, "plan LP改善")

    def test_receive_preserves_command_id_user_id_timestamp(self) -> None:
        ts = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
        raw = _make_raw(command_id="cmd-42", user_id="user-42", timestamp=ts)
        result = normalize(raw)
        self.assertTrue(result.success)
        self.assertEqual(result.value.command_id, "cmd-42")
        self.assertEqual(result.value.user_id, "user-42")
        self.assertEqual(result.value.timestamp, ts)

    def test_receive_preserves_attachments_and_metadata(self) -> None:
        raw = _make_raw(
            attachments=["file1.png", "file2.png"],
            metadata={"channel": "general"},
        )
        result = normalize(raw)
        self.assertTrue(result.success)
        self.assertEqual(result.value.attachments, ["file1.png", "file2.png"])
        self.assertEqual(result.value.metadata, {"channel": "general"})

    def test_receive_empty_command_returns_validation_error(self) -> None:
        raw = _make_raw(command="")
        result = normalize(raw)
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, ValidationError)

    def test_receive_unrecognized_source_does_not_raise(self) -> None:
        raw = _make_raw(source="unknown-source-xyz", command="plan LP改善")
        try:
            result = normalize(raw)
        except Exception as exc:  # noqa: BLE001
            self.fail(f"normalize() raised unexpectedly for unknown source: {exc!r}")
        self.assertTrue(result.success)
        self.assertEqual(result.value.raw_text, "plan LP改善")


if __name__ == "__main__":
    unittest.main()
