"""CommandRouter本体(IS05仕様書4節)。

公開インターフェースは設計書3.5節のreceive/classify/route/dispatchの4メソッドに
限定する。本ファイルの責務はこれらの実装と各モジュール(Handler)へのオーケスト
レーションのみであり、GitHub API呼び出し・Slack返信生成・PR作成・Workflow/Task/
Knowledge状態の保持は行わない(4.2, 4.4節の制約)。
"""

from __future__ import annotations

from collections.abc import Callable

from command_router.errors import DispatchTargetNotRegisteredError
from command_router.models import (
    CommandType,
    DestinationModule,
    DispatchResult,
    NormalizedCommand,
    RawCommandLike,
    RoutedCommand,
)
from command_router.normalizer import normalize
from command_router.routing_table import resolve_destination
from foundation.base_module import BaseModule
from foundation.interfaces import ConfigurationClient
from foundation.logger import get_logger
from foundation.result import Result

# 転送先モジュールを呼び出すための最小限のAdapterインターフェース(F00: Adapter
# Pattern)。Command Router自身は各モジュールの処理内容を理解しない(4.1節)。
CommandHandler = Callable[[RoutedCommand], "Result[object]"]

_MODULE_LOGGER = get_logger("command_router")


def _first_token(raw_text: str) -> str:
    """raw_textの先頭トークン(command_type相当語)のみを取り出す。
    ペイロード本文はSecretを含みうるためログ出力対象外とする(6節)。
    """
    stripped = raw_text.strip()
    if not stripped:
        return ""
    return stripped.split(None, 1)[0]


class CommandRouter(BaseModule):
    def __init__(
        self,
        handlers: dict[DestinationModule, CommandHandler],
        config_client: ConfigurationClient | None = None,
    ) -> None:
        """handlers: Destination ModuleごとのCommandHandler。
        Planner/Designer/Executor/Reviewer/State Managerの実処理には関与せず、
        登録済みのCallableへ転送するのみ(4.4節: Routerは転送専用)。
        config_client: F03のConfigurationClient。Routing Table上書き取得に使用(任意)。
        """
        self._handlers = handlers
        self._config_client = config_client
        self._logger = _MODULE_LOGGER

    def name(self) -> str:
        return "command_router"

    def health_check(self) -> Result[bool]:
        return Result(success=True, value=True, error=None)

    def receive(self, raw_command: RawCommandLike) -> Result[NormalizedCommand]:
        """入力元(Slack/Discord/CLI/WebUI/API/Scheduler)ごとの差異を吸収し、
        共通フォーマット(NormalizedCommand)へ変換する。(設計書3.2節)

        引数は`RawCommandLike`(構造的契約)であればよく、`command_router.models.RawCommand`
        の具象インスタンスである必要はない(Scheduler(M14)等、他モジュールからの入力を許容)。
        """
        result = normalize(raw_command)
        if result.success and result.value is not None:
            token = _first_token(result.value.raw_text)
            self._log(result.value.source, token, None, None, "OK")
        else:
            error_name = type(result.error).__name__ if result.error else "Error"
            self._log(raw_command.source, "", None, None, f"ERROR:{error_name}", level="error")
        return result

    def classify(self, normalized: NormalizedCommand) -> Result[CommandType]:
        """NormalizedCommand.raw_textの先頭語をCommandTypeに解決する。
        NLP/AI推論は行わず、単純な文字列一致(大文字小文字を無視)のみ。
        一致しない場合はResult(success=True, value=CommandType.UNKNOWN, error=None)を
        返す(UNKNOWNは「不正コマンド」であり「処理失敗」ではないためsuccess=True
        で表現する)。
        """
        token = _first_token(normalized.raw_text)
        try:
            command_type = CommandType(token.upper()) if token else CommandType.UNKNOWN
        except ValueError:
            command_type = CommandType.UNKNOWN

        result_label = "OK" if command_type != CommandType.UNKNOWN else "UNKNOWN"
        self._log(normalized.source, token, command_type, None, result_label)
        return Result(success=True, value=command_type, error=None)

    def route(self, command_type: CommandType) -> Result[DestinationModule]:
        """Routing Table(routing_table.py)を用いてDestination Moduleを決定する。
        CommandType.UNKNOWNは転送先を持たないためResult(success=False, value=None,
        error=UnknownCommandError(...))を返す。
        """
        result = resolve_destination(command_type, self._config_client)
        if result.success:
            self._log("-", "-", command_type, result.value, "OK")
        else:
            label = "UNKNOWN" if command_type == CommandType.UNKNOWN else f"ERROR:{type(result.error).__name__}"
            self._log("-", "-", command_type, None, label, level="error")
        return result

    def dispatch(self, destination: DestinationModule, command: RoutedCommand) -> Result[DispatchResult]:
        """destinationに登録されたCommandHandlerへcommandを転送する。
        Router自身がGitHub API呼び出し・Slack返信生成・PR作成を行うことはない
        (4.4節)。未登録のdestinationはResult(success=False,
        error=DispatchTargetNotRegisteredError(...))。
        """
        token = _first_token(command.normalized.raw_text)
        handler = self._handlers.get(destination)

        if handler is None:
            error = DispatchTargetNotRegisteredError(f"no handler registered for destination={destination.value}")
            self._log(
                command.normalized.source,
                token,
                command.command_type,
                destination,
                "ERROR:DispatchTargetNotRegisteredError",
                level="error",
            )
            return Result(success=False, value=None, error=error)

        handler_result = handler(command)
        if not handler_result.success:
            error_name = type(handler_result.error).__name__ if handler_result.error else "Error"
            self._log(
                command.normalized.source,
                token,
                command.command_type,
                destination,
                f"ERROR:{error_name}",
                level="error",
            )
            # Handlerが返すResultのerrorをそのままdispatch()の戻り値に伝播する
            # (Command Routerはエラー内容を変換・解釈しない: 5節)。
            return Result(success=False, value=None, error=handler_result.error)

        dispatch_result = DispatchResult(
            command_id=command.normalized.command_id,
            destination=destination,
            accepted=True,
        )
        self._log(command.normalized.source, token, command.command_type, destination, "OK")
        return Result(success=True, value=dispatch_result, error=None)

    def _log(
        self,
        source: str,
        command_token: str,
        command_type: CommandType | None,
        destination: DestinationModule | None,
        result: str,
        level: str = "info",
    ) -> None:
        """設計書4.5節の6項目(timestamp/source/command/command_type/destination/
        result)を記録する。timestampはloggingのデフォルトフォーマッタに委譲する。
        metadataの値・attachmentsの内容・コマンド全文は出力しない(6節)。
        """
        message = (
            f"source={source} command={command_token} "
            f"command_type={command_type.value if command_type else '-'} "
            f"destination={destination.value if destination else '-'} "
            f"result={result}"
        )
        if level == "error":
            self._logger.error(message)
        else:
            self._logger.info(message)
