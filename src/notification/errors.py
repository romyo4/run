"""Notification (M15) 固有例外(IS15 5. エラー処理)。

Foundationのエラー階層(`FoundationError`)を継承し、本モジュール固有の例外は
最小限に留める。
"""

from __future__ import annotations

from foundation.errors import ConfigurationError, ExternalServiceError, ValidationError


class NotificationError(Exception):
    """Notificationモジュール内部で捕捉し、Result[T].error へ格納するための基底。

    公開APIから直接送出はしない(F02 Result[T]パターンに従う)。
    """


class TemplateNotFoundError(ConfigurationError):
    """event.notification_template に対応するテンプレートがConfigurationに存在しない場合。"""


class UnsupportedChannelError(ValidationError):
    """MVP対応外(Slack/Discord/Email以外)のチャネルが指定された場合。"""


class DeliveryFailedError(ExternalServiceError):
    """ChannelConnector.send() が最大再送回数(3回)を尽くしても失敗した場合の内部記録用。

    send()の戻り値としては例外送出せず、DeliveryResult.status=FAILEDとして返す。
    """
