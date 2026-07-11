"""ConfigurationManager本体(IS17仕様書4.2節)。BaseModuleとConfigurationClientを実装する。"""

from __future__ import annotations

from dataclasses import fields
from typing import Any

from configuration_manager.constants import CATEGORY_NAMES, DEFAULT_VERSION
from configuration_manager.domain import Configuration, ConfigurationSource, ValidationResult
from configuration_manager.loader import (
    build_configuration,
    load_from_environment,
    load_from_files,
    merge_configuration_data,
)
from configuration_manager.validator import validate_configuration
from foundation.base_module import BaseModule
from foundation.errors import NotFoundError
from foundation.interfaces import ConfigurationClient
from foundation.logger import get_logger
from foundation.result import Result

_MODULE_NAME = "configuration_manager"

_logger = get_logger(_MODULE_NAME)


class ConfigurationManager(BaseModule, ConfigurationClient):
    """設計書3.5の公開インターフェース(load/get/validate/reload)を実装する。"""

    def __init__(self, source: ConfigurationSource) -> None:
        self._source = source
        self._configuration: Configuration | None = None

    # --- BaseModule (F02) ---
    def name(self) -> str:
        return _MODULE_NAME

    def health_check(self) -> Result[bool]:
        return Result(success=True, value=self._configuration is not None)

    # --- 設計書3.5 公開インターフェース ---
    def load(self, source: ConfigurationSource) -> Result[Configuration]:
        file_result = load_from_files(source.config_file_paths)
        if not file_result.success:
            return Result(success=False, value=None, error=file_result.error)

        environment_result = load_from_environment(source.environment_prefix)
        if not environment_result.success:
            return Result(success=False, value=None, error=environment_result.error)

        merged_data = merge_configuration_data(
            file_result.value or {},
            environment_result.value or {},
            source.startup_parameters,
        )

        build_result = build_configuration(merged_data, DEFAULT_VERSION)
        if not build_result.success or build_result.value is None:
            return Result(success=False, value=None, error=build_result.error)

        configuration = build_result.value

        validation_result = self.validate(configuration)
        if not validation_result.success:
            return Result(success=False, value=None, error=validation_result.error)

        self._source = source
        self._configuration = configuration
        _logger.info("configuration_version=%s", configuration.version)
        return Result(success=True, value=configuration)

    def validate(self, configuration: Configuration) -> Result[ValidationResult]:
        result = validate_configuration(configuration)
        if result.success and result.value is not None:
            if result.value.is_valid:
                _logger.info("validation_result=valid")
            else:
                _logger.warning("validation_result=invalid error_count=%d", len(result.value.errors))
        return result

    def reload(self) -> Result[Configuration]:
        result = self.load(self._source)
        if result.success:
            _logger.info("reload_result=success")
        else:
            _logger.error("reload_result=failure")
        return result

    # --- ConfigurationClient (F03) の実装 ---
    def get(self, module_name: str, key: str) -> Result[Any]:
        """F03契約は`module_name`をモジュール非依存の任意文字列として扱う。

        設計書3.2が定める7カテゴリ(system/github/slack/discord/codex/fable/monitoring)は
        型付きdataclassとデフォルト値検証を伴う。それ以外のmodule_name(各モジュール自身の名前)は
        `Configuration.extra`(設定ファイル/環境変数/起動パラメータで明示指定された値のみ)から
        参照する(統合レビューでの是正。CHANGELOG.md参照)。
        """
        _logger.info("configuration value requested module_name=%s key=%s", module_name, key)
        if self._configuration is None:
            return Result(
                success=False,
                value=None,
                error=NotFoundError("configuration has not been loaded yet"),
            )
        if module_name in CATEGORY_NAMES:
            category_config = getattr(self._configuration, module_name)
            known_keys = {f.name for f in fields(category_config)}
            if key not in known_keys:
                return Result(
                    success=False,
                    value=None,
                    error=NotFoundError(f"unknown key: {key}"),
                )
            return Result(success=True, value=getattr(category_config, key))

        module_values = self._configuration.extra.get(module_name)
        if module_values is None or key not in module_values:
            return Result(
                success=False,
                value=None,
                error=NotFoundError(f"no configuration value for module_name={module_name!r} key={key!r}"),
            )
        return Result(success=True, value=module_values[key])
