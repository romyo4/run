"""Configuration Manager (M17) の定数(IS17仕様書4.4節/設計書3.2/4.4)。

必須設定キー一覧・カテゴリ既定値・環境変数プレフィックス等を定義する。
設計書4.4に明記のないキーは検証対象に追加しない。
"""

from __future__ import annotations

from typing import Final

# 設計書3.1の既定入力プレフィックス。
DEFAULT_ENVIRONMENT_PREFIX: Final[str] = "APP_"

# Configuration Version の既定値(設計書3.4/3.9 Design Freezeバージョンとは独立の設定バージョン)。
DEFAULT_VERSION: Final[str] = "v1.0"

# 設計書4.4に明記された起動時必須設定(例として挙げられた3項目のみを検証対象とする)。
REQUIRED_CONFIGURATION_KEYS: Final[tuple[tuple[str, str], ...]] = (
    ("github", "repository"),
    ("slack", "channel"),
    ("codex", "model"),
)

REQUIRED_CONFIGURATION_KEY_LABELS: Final[dict[tuple[str, str], str]] = {
    ("github", "repository"): "GitHub Repository",
    ("slack", "channel"): "Slack Channel",
    ("codex", "model"): "Codex Model",
}

# 設計書2.1「デフォルト値適用」に対応するカテゴリ既定値。
DEFAULT_SYSTEM: Final[dict[str, object]] = {
    "system_name": "ai-development-pipeline",
    "environment": "development",
    "log_level": "INFO",
    "timezone": "UTC",
}

DEFAULT_GITHUB: Final[dict[str, object]] = {
    "repository": "",
    "default_branch": "main",
    "organization": "",
}

DEFAULT_SLACK: Final[dict[str, object]] = {
    "workspace": "",
    "channel": "",
    "bot_name": "ai-pipeline-bot",
}

DEFAULT_DISCORD: Final[dict[str, object]] = {
    "server": "",
    "channel": "",
}

DEFAULT_CODEX: Final[dict[str, object]] = {
    "model": "",
    "timeout": 30,
    "max_retry": 3,
}

DEFAULT_FABLE: Final[dict[str, object]] = {
    "review_schedule": "",
    "review_period": "",
}

DEFAULT_MONITORING: Final[dict[str, object]] = {
    "health_interval": 60,
    "warning_threshold": 80,
}

# カテゴリ名 -> 既定値辞書。domain.Configuration のフィールド名と一致させる。
CATEGORY_DEFAULTS: Final[dict[str, dict[str, object]]] = {
    "system": DEFAULT_SYSTEM,
    "github": DEFAULT_GITHUB,
    "slack": DEFAULT_SLACK,
    "discord": DEFAULT_DISCORD,
    "codex": DEFAULT_CODEX,
    "fable": DEFAULT_FABLE,
    "monitoring": DEFAULT_MONITORING,
}

CATEGORY_NAMES: Final[tuple[str, ...]] = tuple(CATEGORY_DEFAULTS.keys())
