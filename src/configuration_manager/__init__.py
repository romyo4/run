"""Configuration Manager (M17) 公開API。

Foundation `ConfigurationClient` (F03) の唯一の実体である `ConfigurationManager` と、
その入出力に用いるdataclass群を再エクスポートする。
"""

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
from configuration_manager.manager import ConfigurationManager

__all__ = [
    "CodexConfig",
    "Configuration",
    "ConfigurationManager",
    "ConfigurationSource",
    "DiscordConfig",
    "FableConfig",
    "GitHubConfig",
    "MonitoringConfig",
    "SlackConfig",
    "SystemConfig",
    "ValidationResult",
]
