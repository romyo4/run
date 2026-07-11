"""Command Type→Destination ModuleのRouting Table(IS05仕様書4節)。

本ファイルの責務はCommand TypeとDestination Moduleの対応関係のみに限定する
(F00: Single Responsibility)。Command追加時は本ファイル(またはF03の
Configuration側設定)のみを更新すればよく、router.py本体の変更は不要である
(設計書3.3節)。
"""

from __future__ import annotations

from command_router.errors import UnknownCommandError
from command_router.models import CommandType, DestinationModule
from foundation.interfaces import ConfigurationClient
from foundation.result import Result

# 設計書3.4節のRoutingテーブル。STATUSはState Managerへ直接転送し、Schedulerは
# 含めない(Design Freeze是正事項: Command Router→Schedulerの転送経路は存在しない)。
ROUTING_TABLE: dict[CommandType, DestinationModule] = {
    CommandType.PLAN: DestinationModule.PLANNER,
    CommandType.DESIGN: DestinationModule.DESIGNER,
    CommandType.IMPLEMENT: DestinationModule.EXECUTOR,
    CommandType.REVIEW: DestinationModule.REVIEWER,
    CommandType.STATUS: DestinationModule.STATE_MANAGER,
    CommandType.HELP: DestinationModule.SYSTEM,
}


def resolve_destination(
    command_type: CommandType,
    config_client: ConfigurationClient | None = None,
) -> Result[DestinationModule]:
    """F03: ConfigurationClient.get("command_router", "routing_table") が
    Result[dict]で上書き値を返す場合はそれを優先し、取得不可・未設定の場合は
    ROUTING_TABLE(静的定義)にフォールバックする。CommandType.UNKNOWNは
    どちらのテーブルにも存在しないため必ずエラーResultとなる。
    """
    if command_type == CommandType.UNKNOWN:
        return Result(
            success=False,
            value=None,
            error=UnknownCommandError(f"no destination registered for command_type={command_type.value}"),
        )

    if config_client is not None:
        override_result = config_client.get("command_router", "routing_table")
        if (
            override_result is not None
            and override_result.success
            and override_result.value
            and command_type in override_result.value
        ):
            return Result(success=True, value=override_result.value[command_type], error=None)

    if command_type in ROUTING_TABLE:
        return Result(success=True, value=ROUTING_TABLE[command_type], error=None)

    return Result(
        success=False,
        value=None,
        error=UnknownCommandError(f"no destination registered for command_type={command_type.value}"),
    )
