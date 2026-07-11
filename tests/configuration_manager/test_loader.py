import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest import mock

from configuration_manager.loader import (
    build_configuration,
    load_from_environment,
    load_from_files,
    merge_configuration_data,
)
from foundation.errors import ConfigurationError


def _full_merged_data(**overrides: dict[str, Any]) -> dict[str, Any]:
    data: dict[str, Any] = {
        "system": {
            "system_name": "pipeline",
            "environment": "test",
            "log_level": "INFO",
            "timezone": "UTC",
        },
        "github": {"repository": "org/repo", "default_branch": "main", "organization": "org"},
        "slack": {"workspace": "ws", "channel": "#general", "bot_name": "bot"},
        "discord": {"server": "server", "channel": "general"},
        "codex": {"model": "gpt-4", "timeout": 30, "max_retry": 3},
        "fable": {"review_schedule": "daily", "review_period": "1h"},
        "monitoring": {"health_interval": 60, "warning_threshold": 80},
    }
    data.update(overrides)
    return data


class LoadFromFilesTest(unittest.TestCase):
    def test_load_from_files_reads_valid_json_configuration_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.json"
            config_path.write_text(json.dumps({"github": {"repository": "org/repo"}}), encoding="utf-8")

            result = load_from_files((config_path,))

            self.assertTrue(result.success)
            self.assertEqual(result.value, {"github": {"repository": "org/repo"}})

    def test_load_from_files_returns_error_result_when_file_missing(self) -> None:
        missing_path = Path(tempfile.gettempdir()) / "does-not-exist-configuration.json"

        result = load_from_files((missing_path,))

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, ConfigurationError)

    def test_load_from_files_returns_error_result_when_json_is_malformed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "broken.json"
            config_path.write_text("{ this is not valid json", encoding="utf-8")

            result = load_from_files((config_path,))

            self.assertFalse(result.success)
            self.assertIsInstance(result.error, ConfigurationError)


class LoadFromEnvironmentTest(unittest.TestCase):
    def test_load_from_environment_reads_variables_with_matching_prefix(self) -> None:
        with mock.patch.dict("os.environ", {"APP_GITHUB__REPOSITORY": "org/repo"}, clear=True):
            result = load_from_environment("APP_")

        self.assertTrue(result.success)
        self.assertEqual(result.value, {"github": {"repository": "org/repo"}})

    def test_load_from_environment_ignores_variables_without_prefix(self) -> None:
        with mock.patch.dict(
            "os.environ",
            {"OTHER_KEY": "ignored", "APP_GITHUB__REPOSITORY": "org/repo"},
            clear=True,
        ):
            result = load_from_environment("APP_")

        self.assertTrue(result.success)
        self.assertEqual(result.value, {"github": {"repository": "org/repo"}})


class MergeConfigurationDataTest(unittest.TestCase):
    def test_merge_configuration_data_startup_parameters_override_environment_variables(
        self,
    ) -> None:
        file_data = {"github": {"repository": "file-repo"}}
        environment_data = {"github": {"repository": "env-repo"}}
        startup_parameters = {"github.repository": "startup-repo"}

        merged = merge_configuration_data(file_data, environment_data, startup_parameters)

        self.assertEqual(merged["github"]["repository"], "startup-repo")

    def test_merge_configuration_data_environment_variables_override_file_values(self) -> None:
        file_data = {"github": {"repository": "file-repo"}}
        environment_data = {"github": {"repository": "env-repo"}}

        merged = merge_configuration_data(file_data, environment_data, {})

        self.assertEqual(merged["github"]["repository"], "env-repo")


class BuildConfigurationTest(unittest.TestCase):
    def test_build_configuration_sets_version_and_timestamps(self) -> None:
        result = build_configuration(_full_merged_data(), "v9.9")

        self.assertTrue(result.success)
        configuration = result.value
        assert configuration is not None
        self.assertEqual(configuration.version, "v9.9")
        self.assertIsInstance(configuration.created_at, datetime)
        self.assertIsInstance(configuration.updated_at, datetime)

    def test_build_configuration_returns_error_result_on_missing_category_data(self) -> None:
        merged_data = _full_merged_data()
        del merged_data["github"]

        result = build_configuration(merged_data, "v1.0")

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, ConfigurationError)


if __name__ == "__main__":
    unittest.main()
