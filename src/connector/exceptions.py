"""Connector(M21)固有例外(IS21 5節)。

Foundationのエラー階層に存在しない「未対応プラットフォーム」「イベント解析失敗」を
表す例外を追加定義する(Foundation 3.6「各モジュールは必要に応じてこれらを継承し、
モジュール固有の例外を定義できる」に従う)。
"""

from foundation.errors import ExternalServiceError, ValidationError


class SlackApiError(ExternalServiceError):
    """Slack API呼び出しが失敗した場合に送出する。"""


class DiscordApiError(ExternalServiceError):
    """Discord API呼び出しが失敗した場合に送出する。"""


class UnsupportedPlatformError(ValidationError):
    """platformがSlack/Discordのいずれでもない場合に送出する。"""


class EventParseError(ValidationError):
    """Platform Eventのraw_payloadをNormalized Messageへ変換できない場合に送出する。"""
