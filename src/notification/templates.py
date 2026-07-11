"""Configuration経由のテンプレート取得・レンダリング(IS15 4.2, 4.4対応)。

テンプレート文字列は必ず `ConfigurationClient` 経由で取得し、コード内に固定文字列
テンプレートを持たない(4.4)。
"""

from __future__ import annotations

from foundation.errors import ValidationError
from foundation.interfaces import ConfigurationClient
from foundation.result import Result
from notification.constants import MODULE_NAME
from notification.errors import TemplateNotFoundError
from notification.types import NotificationEvent


def render_message_body(
    event: NotificationEvent,
    config_client: ConfigurationClient,
) -> Result[str]:
    """F03 ConfigurationClient.get("notification", event.notification_template) で
    テンプレート文字列を取得し、event_type/event_resultの値で埋め込みレンダリングする。

    コード内に固定文字列テンプレートを持たない(4.4)。
    """
    template_result = config_client.get(MODULE_NAME, event.notification_template)

    if not template_result.success or template_result.value is None:
        return Result(
            success=False,
            error=TemplateNotFoundError(f"notification_templateが見つかりません: {event.notification_template!r}"),
        )

    template_str = template_result.value
    if not isinstance(template_str, str):
        return Result(
            success=False,
            error=TemplateNotFoundError(f"notification_templateが文字列ではありません: {event.notification_template!r}"),
        )

    render_values: dict[str, object] = {"event_type": event.event_type.value, **event.event_result}

    try:
        rendered = template_str.format(**render_values)
    except (KeyError, IndexError, ValueError) as exc:
        return Result(
            success=False,
            error=ValidationError(
                f"notification_templateのレンダリングに失敗しました " f"({event.notification_template!r}): {exc}"
            ),
        )

    return Result(success=True, value=rendered)
