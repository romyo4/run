import dataclasses
import unittest
from datetime import UTC, datetime

from configuration_manager.domain import (
    CodexConfig,
    Configuration,
    ConfigurationSource,
    DiscordConfig,
    FableConfig,
    GitHubConfig,
    MonitoringConfig,
    SlackConfig,
    SystemConfig,
    ValidationResult,
)


def _build_configuration() -> Configuration:
    now = datetime.now(UTC)
    return Configuration(
        id="config-1",
        created_at=now,
        updated_at=now,
        metadata={},
        version="v1.0",
        system=SystemConfig(system_name="pipeline", environment="test", log_level="INFO", timezone="UTC"),
        github=GitHubConfig(repository="org/repo", default_branch="main", organization="org"),
        slack=SlackConfig(workspace="ws", channel="#general", bot_name="bot"),
        discord=DiscordConfig(server="server", channel="general"),
        codex=CodexConfig(model="gpt", timeout=30, max_retry=3),
        fable=FableConfig(review_schedule="daily", review_period="1h"),
        monitoring=MonitoringConfig(health_interval=60, warning_threshold=80),
    )


class ConfigurationDomainTest(unittest.TestCase):
    def test_configuration_is_frozen_and_raises_on_attribute_assignment(self) -> None:
        configuration = _build_configuration()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            configuration.version = "v2.0"  # type: ignore[misc]

    def test_configuration_source_defaults_to_empty_file_paths_and_parameters(self) -> None:
        source = ConfigurationSource()
        self.assertEqual(source.config_file_paths, ())
        self.assertEqual(source.environment_prefix, "APP_")
        self.assertEqual(source.startup_parameters, {})

    def test_validation_result_defaults_to_empty_errors_tuple(self) -> None:
        result = ValidationResult(is_valid=True)
        self.assertEqual(result.errors, ())


if __name__ == "__main__":
    unittest.main()
