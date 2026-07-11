"""SlackDiscordConnector(M21)本体(IS21 4.4)。

`BaseModule`(F02)を継承し、設計書3.6の公開インターフェース3関数
(`receive()`/`send()`/`health()`)を実装する。Platform種別に応じて適切な
Adapter(`MessageAdapter`)へ処理を委譲するのみで、メッセージ内容の解釈・
加工・コマンド解析・通知内容生成は一切行わない(設計書4.1/4.4)。
"""

from __future__ import annotations

from connector.adapter import MessageAdapter
from connector.discord_adapter import DiscordAdapter
from connector.exceptions import UnsupportedPlatformError
from connector.slack_adapter import SlackAdapter
from connector.types import (
    ConnectionStatus,
    DeliveryResult,
    NormalizedMessage,
    OutboundMessage,
    Platform,
    PlatformEvent,
)
from foundation.base_module import BaseModule
from foundation.errors import ExternalServiceError
from foundation.interfaces import ConfigurationClient
from foundation.logger import get_logger
from foundation.result import Result
from foundation.utils import utc_now

MODULE_NAME = "slack_discord_connector"

logger = get_logger("connector")


class SlackDiscordConnector(BaseModule):
    """Slack/Discordとの唯一の通信窓口(設計書全体)。送受信のみを担当する。"""

    def __init__(
        self,
        config_client: ConfigurationClient,
        slack_adapter: MessageAdapter | None = None,
        discord_adapter: MessageAdapter | None = None,
    ) -> None:
        self._config_client = config_client
        self._slack_adapter: MessageAdapter = slack_adapter or SlackAdapter(config_client)
        self._discord_adapter: MessageAdapter = discord_adapter or DiscordAdapter(config_client)
        self._logger = logger

    # --- F02: BaseModule ---

    def name(self) -> str:
        return MODULE_NAME

    def health_check(self) -> Result[bool]:
        """`health()`の結果から、Slack/Discordの少なくとも一方が接続可能であれば
        `Result(success=True, value=True)`を返す(F02が要求する真偽値判定への集約)。
        """
        health_result = self.health()
        if not health_result.success or health_result.value is None:
            return Result(success=False, error=health_result.error)
        status = health_result.value
        return Result(success=True, value=status.slack_connected or status.discord_connected)

    # --- 設計書3.6: 公開インターフェース ---

    def receive(self, event: PlatformEvent) -> Result[NormalizedMessage]:
        """`event.platform`から`_adapter_for()`でAdapterを選択し、
        `adapter.parse_event(event.raw_payload)`へ委譲する。Adapterが返す`Result`を
        そのまま返す(Connector自身はメッセージ内容の解釈・加工を行わない)。
        """
        adapter_result = self._adapter_for(event.platform)
        if not adapter_result.success or adapter_result.value is None:
            self._log_event(
                platform=event.platform,
                user_id=None,
                channel_id=None,
                event_type="unknown",
                result="failure",
                error=adapter_result.error,
            )
            return Result(success=False, error=adapter_result.error)

        try:
            parse_result = adapter_result.value.parse_event(event.raw_payload)
        except Exception as exc:  # noqa: BLE001 - Adapter内部の未捕捉例外をResultへ変換する
            self._log_event(
                platform=event.platform,
                user_id=None,
                channel_id=None,
                event_type="unknown",
                result="failure",
                error=exc,
            )
            return Result(success=False, error=ExternalServiceError(str(exc)))

        if parse_result.success and parse_result.value is not None:
            normalized = parse_result.value
            self._log_event(
                platform=normalized.platform,
                user_id=normalized.user_id,
                channel_id=normalized.channel_id,
                event_type=normalized.event_type.value,
                result="success",
            )
        else:
            self._log_event(
                platform=event.platform,
                user_id=None,
                channel_id=None,
                event_type="unknown",
                result="failure",
                error=parse_result.error,
            )
        return parse_result

    def send(self, message: OutboundMessage) -> Result[DeliveryResult]:
        """`message.platform`から`_adapter_for()`でAdapterを選択し、
        `adapter.deliver(message)`へ委譲する。通知本文の生成・加工は行わず、
        受け取った`OutboundMessage`をそのまま送信する(設計書4.4)。
        """
        adapter_result = self._adapter_for(message.platform)
        if not adapter_result.success or adapter_result.value is None:
            self._log_event(
                platform=message.platform,
                user_id=message.user_id,
                channel_id=message.channel_id,
                event_type=message.content_type.value,
                result="failure",
                error=adapter_result.error,
            )
            return Result(success=False, error=adapter_result.error)

        try:
            deliver_result = adapter_result.value.deliver(message)
        except Exception as exc:  # noqa: BLE001 - Adapter内部の未捕捉例外をResultへ変換する
            self._log_event(
                platform=message.platform,
                user_id=message.user_id,
                channel_id=message.channel_id,
                event_type=message.content_type.value,
                result="failure",
                error=exc,
            )
            return Result(success=False, error=ExternalServiceError(str(exc)))

        self._log_event(
            platform=message.platform,
            user_id=message.user_id,
            channel_id=message.channel_id,
            event_type=message.content_type.value,
            result="success" if deliver_result.success else "failure",
            error=None if deliver_result.success else deliver_result.error,
        )
        return deliver_result

    def health(self) -> Result[ConnectionStatus]:
        """保持している全Adapter(Slack/Discord)の`check_connection()`を呼び出し、
        結果を`ConnectionStatus`へ集約して返す。個々のAdapter呼び出しが例外を
        送出しても、他方のチェックは継続する(1プラットフォーム障害が全体を落とさない)。
        """
        detail: dict[str, str] = {}

        slack_connected, slack_error = self._check_adapter_connection(self._slack_adapter)
        if slack_error is not None:
            detail["slack"] = slack_error

        discord_connected, discord_error = self._check_adapter_connection(self._discord_adapter)
        if discord_error is not None:
            detail["discord"] = discord_error

        status = ConnectionStatus(
            slack_connected=slack_connected,
            discord_connected=discord_connected,
            detail=detail,
        )
        self._log_event(
            platform=None,
            user_id=None,
            channel_id=None,
            event_type="health_check",
            result="success" if (slack_connected or discord_connected) else "failure",
        )
        return Result(success=True, value=status)

    # --- 内部ヘルパー ---

    def _adapter_for(self, platform: Platform) -> Result[MessageAdapter]:
        """platformに対応するAdapterを返す。未対応のPlatformはUnsupportedPlatformError。"""
        if platform == Platform.SLACK:
            return Result(success=True, value=self._slack_adapter)
        if platform == Platform.DISCORD:
            return Result(success=True, value=self._discord_adapter)
        return Result(
            success=False,
            error=UnsupportedPlatformError(f"unsupported platform: {platform!r}"),
        )

    @staticmethod
    def _check_adapter_connection(adapter: MessageAdapter) -> tuple[bool, str | None]:
        try:
            result = adapter.check_connection()
        except Exception as exc:  # noqa: BLE001 - 1プラットフォームの障害を他方へ波及させない
            return False, type(exc).__name__
        if result.success:
            return bool(result.value), None
        return False, type(result.error).__name__ if result.error is not None else "unknown_error"

    def _log_event(
        self,
        *,
        platform: Platform | None,
        user_id: str | None,
        channel_id: str | None,
        event_type: str,
        result: str,
        error: BaseException | None = None,
    ) -> None:
        """設計書4.5のログ項目のみをkey=value形式で出力する。

        `NormalizedMessage`/`OutboundMessage`/`PlatformEvent`のインスタンスをそのまま
        ログへ渡すことはせず、メッセージ本文・添付ファイル・Access Tokenが
        ログに混入しないよう、許可された項目のみを明示的に組み立てる。
        """
        platform_value = platform.value if isinstance(platform, Platform) else platform
        log_message = (
            f"timestamp={utc_now().isoformat()} platform={platform_value} user_id={user_id} "
            f"channel_id={channel_id} event_type={event_type} result={result}"
        )
        if error is not None:
            log_message += f" error_class={type(error).__name__}"

        if result == "success":
            self._logger.info(log_message)
        else:
            self._logger.warning(log_message)
