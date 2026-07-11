"""Configuration Manager (M17) の設定値dataclass定義(IS17仕様書3節)。

Foundation `types.py` の Configuration Domain(共通属性: id/created_at/updated_at/metadata)
を前提に、本モジュール固有のカテゴリ属性(System/GitHub/Slack/Discord/Codex/Fable/Monitoring)
を組み込んだ具体構造をここで定義する。設計書に明記のない属性は追加しない。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SystemConfig:
    system_name: str
    environment: str
    log_level: str
    timezone: str


@dataclass(frozen=True)
class GitHubConfig:
    repository: str
    default_branch: str
    organization: str


@dataclass(frozen=True)
class SlackConfig:
    workspace: str
    channel: str
    bot_name: str


@dataclass(frozen=True)
class DiscordConfig:
    server: str
    channel: str


@dataclass(frozen=True)
class CodexConfig:
    model: str
    timeout: int
    max_retry: int


@dataclass(frozen=True)
class FableConfig:
    review_schedule: str
    review_period: str


@dataclass(frozen=True)
class MonitoringConfig:
    health_interval: int
    warning_threshold: int


@dataclass(frozen=True)
class Configuration:
    """Foundation Configuration Domain(id/created_at/updated_at/metadata)の具体構造。

    `extra` は設計書3.2が列挙する7カテゴリ(system/github/slack/discord/codex/fable/monitoring)
    以外に、他モジュールがF03 ConfigurationClient経由で自モジュール名をmodule_nameとして
    要求する設定値(例: state_manager.lock_timeout_seconds)を保持する。統合レビューで、
    F03の`get(module_name, key)`が本来モジュール非依存の汎用契約であるにもかかわらず、
    本モジュールの初版実装が7カテゴリのみに制限していたことが判明したための追加
    (CHANGELOG.md参照)。7カテゴリのように型付きdataclass・デフォルト値検証は行わず、
    設定ファイル/環境変数/起動パラメータで明示的に指定された値のみを保持する。
    """

    id: str
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]
    version: str
    system: SystemConfig
    github: GitHubConfig
    slack: SlackConfig
    discord: DiscordConfig
    codex: CodexConfig
    fable: FableConfig
    monitoring: MonitoringConfig
    extra: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class ConfigurationSource:
    """load()/reload()の入力(設計書3.1: configuration_files/environment_variables/startup_parameters)。"""

    config_file_paths: tuple[Path, ...] = field(default_factory=tuple)
    environment_prefix: str = "APP_"
    startup_parameters: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationResult:
    """設計書3.4の成果物「Validation Result」。"""

    is_valid: bool
    errors: tuple[str, ...] = field(default_factory=tuple)
