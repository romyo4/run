"""Configuration Files / Environment Variables / Startup Parametersの読込・マージ処理(IS17仕様書4.3節)。

設定ファイルはUTF-8のJSON形式のみを対象とし、標準ライブラリ`json`のみを使用する(外部パーサ依存を持ち込まない)。
マージ優先順位は startup_parameters > environment_variables > configuration_files とする。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from configuration_manager.constants import CATEGORY_DEFAULTS, CATEGORY_NAMES
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
from foundation.errors import ConfigurationError
from foundation.result import Result
from foundation.utils import generate_id, utc_now


def load_from_files(config_file_paths: tuple[Path, ...]) -> Result[dict[str, Any]]:
    """UTF-8 JSON形式の設定ファイル群を読み込み、順に深いマージを行った辞書を返す。"""
    merged: dict[str, Any] = {}
    for path in config_file_paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return Result(
                success=False,
                error=ConfigurationError(f"configuration file could not be read: {path}"),
            )
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return Result(
                success=False,
                error=ConfigurationError(f"configuration file contains malformed JSON: {path}"),
            )
        if not isinstance(data, dict):
            return Result(
                success=False,
                error=ConfigurationError(f"configuration file did not contain a JSON object: {path}"),
            )
        merged = _deep_merge(merged, data)
    return Result(success=True, value=merged)


def load_from_environment(environment_prefix: str) -> Result[dict[str, Any]]:
    """`{prefix}{CATEGORY}__{FIELD}` 形式の環境変数を読み込み、カテゴリ別の辞書を返す。"""
    data: dict[str, Any] = {}
    try:
        for env_key, env_value in os.environ.items():
            if not env_key.startswith(environment_prefix):
                continue
            remainder = env_key[len(environment_prefix) :]
            parts = remainder.split("__")
            if len(parts) != 2 or not parts[0] or not parts[1]:
                continue
            category, field_name = parts[0].lower(), parts[1].lower()
            data.setdefault(category, {})[field_name] = env_value
    except Exception as exc:  # noqa: BLE001 - 環境変数読込時の予期しない例外をResultへ変換する
        return Result(
            success=False,
            error=ConfigurationError(f"failed to read environment variables: {exc}"),
        )
    return Result(success=True, value=data)


def merge_configuration_data(
    file_data: dict[str, Any],
    environment_data: dict[str, Any],
    startup_parameters: dict[str, str],
) -> dict[str, Any]:
    """configuration_files -> environment_variables -> startup_parametersの順に後勝ちマージする。"""
    merged = _deep_merge({}, file_data)
    merged = _deep_merge(merged, environment_data)
    merged = _deep_merge(merged, _expand_startup_parameters(startup_parameters))
    return merged


def build_configuration(merged_data: dict[str, Any], version: str) -> Result[Configuration]:
    """マージ済み辞書からConfigurationを構築する。カテゴリ丸ごとの欠落はエラーとする。"""
    for category in CATEGORY_NAMES:
        category_data = merged_data.get(category)
        if category not in merged_data:
            return Result(
                success=False,
                error=ConfigurationError(f"missing configuration category: {category}"),
            )
        if not isinstance(category_data, dict):
            return Result(
                success=False,
                error=ConfigurationError(f"invalid configuration category: {category}"),
            )

    try:
        system_data = _apply_defaults("system", merged_data["system"])
        github_data = _apply_defaults("github", merged_data["github"])
        slack_data = _apply_defaults("slack", merged_data["slack"])
        discord_data = _apply_defaults("discord", merged_data["discord"])
        codex_data = _apply_defaults("codex", merged_data["codex"])
        fable_data = _apply_defaults("fable", merged_data["fable"])
        monitoring_data = _apply_defaults("monitoring", merged_data["monitoring"])

        configuration = Configuration(
            id=generate_id(),
            created_at=utc_now(),
            updated_at=utc_now(),
            metadata={},
            version=version,
            system=SystemConfig(
                system_name=str(system_data["system_name"]),
                environment=str(system_data["environment"]),
                log_level=str(system_data["log_level"]),
                timezone=str(system_data["timezone"]),
            ),
            github=GitHubConfig(
                repository=str(github_data["repository"]),
                default_branch=str(github_data["default_branch"]),
                organization=str(github_data["organization"]),
            ),
            slack=SlackConfig(
                workspace=str(slack_data["workspace"]),
                channel=str(slack_data["channel"]),
                bot_name=str(slack_data["bot_name"]),
            ),
            discord=DiscordConfig(
                server=str(discord_data["server"]),
                channel=str(discord_data["channel"]),
            ),
            codex=CodexConfig(
                model=str(codex_data["model"]),
                timeout=int(codex_data["timeout"]),
                max_retry=int(codex_data["max_retry"]),
            ),
            fable=FableConfig(
                review_schedule=str(fable_data["review_schedule"]),
                review_period=str(fable_data["review_period"]),
            ),
            monitoring=MonitoringConfig(
                health_interval=int(monitoring_data["health_interval"]),
                warning_threshold=int(monitoring_data["warning_threshold"]),
            ),
            extra={
                module_name: dict(module_data)
                for module_name, module_data in merged_data.items()
                if module_name not in CATEGORY_NAMES and isinstance(module_data, dict)
            },
        )
    except (TypeError, ValueError):
        return Result(
            success=False,
            error=ConfigurationError("failed to build configuration from merged data"),
        )
    return Result(success=True, value=configuration)


def _apply_defaults(category: str, data: dict[str, Any]) -> dict[str, Any]:
    """カテゴリ既定値に、指定データで存在するキーのみを上書き適用する(未知キーは無視)。"""
    defaults = CATEGORY_DEFAULTS[category]
    result = dict(defaults)
    for key in defaults:
        if key in data:
            result[key] = data[key]
    return result


def _expand_startup_parameters(startup_parameters: dict[str, str]) -> dict[str, Any]:
    """`category.field` 形式のドット区切りキーをカテゴリ別の辞書へ展開する。"""
    expanded: dict[str, Any] = {}
    for dotted_key, value in startup_parameters.items():
        if "." not in dotted_key:
            continue
        category, field_name = dotted_key.split(".", 1)
        if not category or not field_name:
            continue
        expanded.setdefault(category, {})[field_name] = value
    return expanded


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """baseにoverrideを再帰的に後勝ちマージした新しい辞書を返す(引数は変更しない)。"""
    result: dict[str, Any] = {k: (dict(v) if isinstance(v, dict) else v) for k, v in base.items()}
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
