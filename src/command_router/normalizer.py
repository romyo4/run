"""入力元(Slack/Discord/CLI/WebUI/API/Scheduler)ごとの正規化ロジック(IS05仕様書2節)。

本ファイルの責務は入力差異の吸収のみに限定する(F00: Single Responsibility)。
Command Type判定・Routing判断は一切行わない。
"""

from __future__ import annotations

from command_router.models import NormalizedCommand, RawCommandLike
from foundation.errors import ValidationError
from foundation.result import Result

_SLASH_PREFIX = "/"
_DISCORD_MENTION_PREFIX = "@bot"


def normalize(raw: RawCommandLike) -> Result[NormalizedCommand]:
    """入力元ごとの差異(Slackの`/`プレフィックス、Discordの`@bot`プレフィックス等)を
    吸収し、共通フォーマット(NormalizedCommand)へ変換する。(設計書3.2節)

    未知のsourceはエラーとせず、プレフィックスなしのコマンドとして扱う
    (passthrough)。
    """
    if raw.command is None or not raw.command.strip():
        return Result(
            success=False,
            value=None,
            error=ValidationError("command must not be empty"),
        )

    source_key = raw.source.strip().lower() if raw.source else ""
    raw_text = raw.command.strip()

    if source_key == "slack":
        raw_text = _strip_slash_prefix(raw_text)
    elif source_key == "discord":
        raw_text = _strip_at_bot_prefix(raw_text)
    # cli/web ui/api/scheduler、および未知のsourceはプレフィックスを持たないため
    # そのまま(passthrough)扱う。

    normalized = NormalizedCommand(
        command_id=raw.command_id,
        source=raw.source,
        user_id=raw.user_id,
        timestamp=raw.timestamp,
        raw_text=raw_text,
        attachments=list(raw.attachments),
        metadata=dict(raw.metadata),
    )
    return Result(success=True, value=normalized, error=None)


def _strip_slash_prefix(text: str) -> str:
    if text.startswith(_SLASH_PREFIX):
        return text[len(_SLASH_PREFIX) :].strip()
    return text


def _strip_at_bot_prefix(text: str) -> str:
    if text.lower().startswith(_DISCORD_MENTION_PREFIX):
        return text[len(_DISCORD_MENTION_PREFIX) :].strip()
    return text
