import unittest
from datetime import UTC, datetime

from configuration_manager.domain import (
    CodexConfig,
    Configuration,
    DiscordConfig,
    FableConfig,
    GitHubConfig,
    MonitoringConfig,
    SlackConfig,
    SystemConfig,
)
from configuration_manager.validator import validate_configuration


def _build_configuration(*, repository: str = "org/repo", channel: str = "#general", model: str = "gpt-4") -> Configuration:
    now = datetime.now(UTC)
    return Configuration(
        id="config-1",
        created_at=now,
        updated_at=now,
        metadata={},
        version="v1.0",
        system=SystemConfig(system_name="pipeline", environment="test", log_level="INFO", timezone="UTC"),
        github=GitHubConfig(repository=repository, default_branch="main", organization="org"),
        slack=SlackConfig(workspace="ws", channel=channel, bot_name="bot"),
        discord=DiscordConfig(server="server", channel="general"),
        codex=CodexConfig(model=model, timeout=30, max_retry=3),
        fable=FableConfig(review_schedule="daily", review_period="1h"),
        monitoring=MonitoringConfig(health_interval=60, warning_threshold=80),
    )


class ValidateConfigurationTest(unittest.TestCase):
    def test_validate_configuration_returns_valid_when_all_required_keys_present(self) -> None:
        result = validate_configuration(_build_configuration())

        self.assertTrue(result.success)
        assert result.value is not None
        self.assertTrue(result.value.is_valid)
        self.assertEqual(result.value.errors, ())

    def test_validate_configuration_flags_missing_github_repository(self) -> None:
        result = validate_configuration(_build_configuration(repository=""))

        self.assertTrue(result.success)
        assert result.value is not None
        self.assertFalse(result.value.is_valid)
        self.assertTrue(any("GitHub Repository" in error for error in result.value.errors))

    def test_validate_configuration_flags_missing_slack_channel(self) -> None:
        result = validate_configuration(_build_configuration(channel=""))

        self.assertTrue(result.success)
        assert result.value is not None
        self.assertFalse(result.value.is_valid)
        self.assertTrue(any("Slack Channel" in error for error in result.value.errors))

    def test_validate_configuration_flags_missing_codex_model(self) -> None:
        result = validate_configuration(_build_configuration(model=""))

        self.assertTrue(result.success)
        assert result.value is not None
        self.assertFalse(result.value.is_valid)
        self.assertTrue(any("Codex Model" in error for error in result.value.errors))

    def test_validate_configuration_collects_multiple_missing_keys_in_one_result(self) -> None:
        result = validate_configuration(_build_configuration(repository="", channel="", model=""))

        self.assertTrue(result.success)
        assert result.value is not None
        self.assertFalse(result.value.is_valid)
        self.assertEqual(len(result.value.errors), 3)


if __name__ == "__main__":
    unittest.main()
