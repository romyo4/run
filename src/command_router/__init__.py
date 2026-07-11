"""Command Router(M05)パッケージ公開API。

CommandRouter・データクラス・固有例外を再エクスポートする。
"""

from __future__ import annotations

from command_router.errors import DispatchTargetNotRegisteredError, UnknownCommandError
from command_router.models import (
    CommandType,
    DestinationModule,
    DispatchResult,
    NormalizedCommand,
    RawCommand,
    RoutedCommand,
)
from command_router.router import CommandHandler, CommandRouter

__all__ = [
    "CommandRouter",
    "CommandHandler",
    "CommandType",
    "DestinationModule",
    "DispatchResult",
    "NormalizedCommand",
    "RawCommand",
    "RoutedCommand",
    "UnknownCommandError",
    "DispatchTargetNotRegisteredError",
]
