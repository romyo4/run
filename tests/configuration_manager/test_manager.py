import json
import os
import tempfile
import unittest
from pathlib import Path

from configuration_manager.constants import DEFAULT_VERSION
from configuration_manager.domain import ConfigurationSource
from configuration_manager.manager import ConfigurationManager
from foundation.errors import NotFoundError

_VALID_CONFIG_DATA = {
    "system": {
        "system_name": "pipeline",
        "environment": "test",
        "log_level": "INFO",
        "timezone": "UTC",
    },
    "github": {
        "repository": "secret-org/secret-repo",
        "default_branch": "main",
        "organization": "secret-org",
    },
    "slack": {"workspace": "ws", "channel": "#general", "bot_name": "bot"},
    "discord": {"server": "server", "channel": "general"},
    "codex": {"model": "gpt-4", "timeout": 30, "max_retry": 3},
    "fable": {"review_schedule": "daily", "review_period": "1h"},
    "monitoring": {"health_interval": 60, "warning_threshold": 80},
}


class ConfigurationManagerTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp_dir.cleanup)
        self.config_path = Path(self._tmp_dir.name) / "config.json"
        self.config_path.write_text(json.dumps(_VALID_CONFIG_DATA), encoding="utf-8")
        self.source = ConfigurationSource(config_file_paths=(self.config_path,))


class NameAndHealthCheckTest(ConfigurationManagerTestBase):
    def test_name_returns_configuration_manager(self) -> None:
        manager = ConfigurationManager(self.source)
        self.assertEqual(manager.name(), "configuration_manager")

    def test_health_check_returns_success_true_after_successful_load(self) -> None:
        manager = ConfigurationManager(self.source)
        manager.load(self.source)

        result = manager.health_check()

        self.assertTrue(result.success)
        self.assertTrue(result.value)

    def test_health_check_returns_success_false_before_first_load(self) -> None:
        manager = ConfigurationManager(self.source)

        result = manager.health_check()

        self.assertTrue(result.success)
        self.assertFalse(result.value)


class LoadTest(ConfigurationManagerTestBase):
    def test_load_returns_success_result_containing_configuration(self) -> None:
        manager = ConfigurationManager(self.source)

        result = manager.load(self.source)

        self.assertTrue(result.success)
        assert result.value is not None
        self.assertEqual(result.value.github.repository, "secret-org/secret-repo")
        self.assertEqual(result.value.version, DEFAULT_VERSION)

    def test_load_returns_error_result_when_underlying_loader_fails(self) -> None:
        missing_path = Path(self._tmp_dir.name) / "missing.json"
        broken_source = ConfigurationSource(config_file_paths=(missing_path,))
        manager = ConfigurationManager(broken_source)

        result = manager.load(broken_source)

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)


class GetTest(ConfigurationManagerTestBase):
    def test_get_returns_success_result_for_known_module_and_key(self) -> None:
        manager = ConfigurationManager(self.source)
        manager.load(self.source)

        result = manager.get("github", "repository")

        self.assertTrue(result.success)
        self.assertEqual(result.value, "secret-org/secret-repo")

    def test_get_returns_not_found_error_for_unknown_module_name(self) -> None:
        manager = ConfigurationManager(self.source)
        manager.load(self.source)

        result = manager.get("unknown_module", "repository")

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, NotFoundError)

    def test_get_returns_not_found_error_for_unknown_key(self) -> None:
        manager = ConfigurationManager(self.source)
        manager.load(self.source)

        result = manager.get("github", "unknown_key")

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, NotFoundError)

    def test_get_returns_not_found_error_before_configuration_is_loaded(self) -> None:
        manager = ConfigurationManager(self.source)

        result = manager.get("github", "repository")

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, NotFoundError)

    def test_get_returns_success_result_for_module_name_outside_official_categories(self) -> None:
        """F03のmodule_nameはモジュール非依存の任意文字列であるため、7カテゴリ以外の
        モジュール自身の名前(例: state_manager)をmodule_nameとして渡した設定値も
        Configuration.extra経由で取得できる(統合レビューでの是正)。"""
        config_data = dict(_VALID_CONFIG_DATA)
        config_data["state_manager"] = {"lock_timeout_seconds": 5}
        self.config_path.write_text(json.dumps(config_data), encoding="utf-8")
        manager = ConfigurationManager(self.source)
        manager.load(self.source)

        result = manager.get("state_manager", "lock_timeout_seconds")

        self.assertTrue(result.success)
        self.assertEqual(result.value, 5)

    def test_get_returns_not_found_error_for_unknown_key_in_non_official_module(self) -> None:
        config_data = dict(_VALID_CONFIG_DATA)
        config_data["state_manager"] = {"lock_timeout_seconds": 5}
        self.config_path.write_text(json.dumps(config_data), encoding="utf-8")
        manager = ConfigurationManager(self.source)
        manager.load(self.source)

        result = manager.get("state_manager", "unknown_key")

        self.assertFalse(result.success)
        self.assertIsInstance(result.error, NotFoundError)


class ValidateTest(ConfigurationManagerTestBase):
    def test_validate_returns_validation_result_reflecting_missing_required_keys(self) -> None:
        incomplete_data = json.loads(json.dumps(_VALID_CONFIG_DATA))
        incomplete_data["github"]["repository"] = ""
        incomplete_path = Path(self._tmp_dir.name) / "incomplete.json"
        incomplete_path.write_text(json.dumps(incomplete_data), encoding="utf-8")
        source = ConfigurationSource(config_file_paths=(incomplete_path,))
        manager = ConfigurationManager(source)

        # Configuration Manager itself must not abort the process on missing required
        # keys (design doc 4.4) - load() succeeds and returns the built Configuration;
        # it is the caller's responsibility to inspect ValidationResult.is_valid.
        load_result = manager.load(source)

        self.assertTrue(load_result.success)
        assert load_result.value is not None

        validate_result = manager.validate(load_result.value)

        self.assertTrue(validate_result.success)
        assert validate_result.value is not None
        self.assertFalse(validate_result.value.is_valid)
        self.assertTrue(any("GitHub Repository" in error for error in validate_result.value.errors))


class ReloadTest(ConfigurationManagerTestBase):
    def test_reload_rebuilds_configuration_from_original_source(self) -> None:
        manager = ConfigurationManager(self.source)
        manager.load(self.source)

        result = manager.reload()

        self.assertTrue(result.success)
        assert result.value is not None
        self.assertEqual(result.value.github.repository, "secret-org/secret-repo")

    def test_reload_returns_error_result_when_source_files_removed(self) -> None:
        manager = ConfigurationManager(self.source)
        manager.load(self.source)
        os.remove(self.config_path)

        result = manager.reload()

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)


class LoggingTest(ConfigurationManagerTestBase):
    def test_manager_does_not_include_configuration_values_in_log_output(self) -> None:
        manager = ConfigurationManager(self.source)

        with self.assertLogs("configuration_manager", level="INFO") as captured:
            manager.load(self.source)
            manager.get("github", "repository")

        for message in captured.output:
            self.assertNotIn("secret-org/secret-repo", message)
            self.assertNotIn("secret-org", message)

    def test_manager_logs_configuration_version_on_successful_load(self) -> None:
        manager = ConfigurationManager(self.source)

        with self.assertLogs("configuration_manager", level="INFO") as captured:
            manager.load(self.source)

        self.assertTrue(any(DEFAULT_VERSION in message for message in captured.output))


if __name__ == "__main__":
    unittest.main()
