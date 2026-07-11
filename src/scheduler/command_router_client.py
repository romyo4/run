"""Command Router(M05)連携(IS14 4.2節)。

Scheduler→Command Routerの一方向依存のみを持つ。Command Routerの公開インターフェースの
うち `receive()` のみを呼び出し、`classify`/`route`/`dispatch` 等は直接呼び出さない。
Command RouterがSchedulerを呼び返す経路(コールバック)は一切提供しない。

Command Router(`command_router.router.CommandRouter.receive()`)が実際に要求する入力は
設計書(M05)3.1節のRaw Command形状(command_id/source/user_id/timestamp/command/
attachments/metadata、属性アクセス前提)であり、JSON風のdictではない。本ファイルは
Command Router側の具象クラス(`command_router.models.RawCommand`)をimportせず、
Scheduler側で同一形状の`RawCommand`(dataclass)を独自定義し、ダックタイピングにより
Command Routerの`RawCommandLike`契約を満たす値を渡す(依存方向はScheduler→Command Router
の一方向のみを維持する)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from foundation.result import Result

from .exceptions import CommandRouterDispatchError
from .models import ExecutionRequest

# Scheduler自身が起動する内部コマンドであることを示す固定user_id。
# ExecutionRequestはエンドユーザーID(user_id)を保持しないため(3節)、
# Command Router設計書1節「適用対象: Scheduler(内部コマンド)」に合わせた固定値を用いる。
_SCHEDULER_USER_ID = "scheduler"


@dataclass(frozen=True)
class RawCommand:
    """Command Router(M05)設計書3.1節のRaw Command形状をScheduler側で複製した入力値。

    `command_router.models.RawCommand`とは別クラスだが、フィールド名・型を完全に一致させる
    ことで、Command Routerの`receive()`(`RawCommandLike`構造的契約)を属性アクセスのみで
    満たす。Command Router側の具象クラスは直接importしない。
    """

    command_id: str
    source: str
    user_id: str
    timestamp: datetime
    command: str
    attachments: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class CommandRouterClient(Protocol):
    def receive(self, raw_command: RawCommand) -> Result[Any]:
        """Command Router(M05)の公開インターフェース receive() をそのまま呼び出す。

        Schedulerはこれ以外(classify/route/dispatch)を直接呼び出さない。
        """
        ...


class CommandRouterAdapter:
    """CommandRouterClient の具象実装。Scheduler→Command Routerの一方向依存のみを持つ。"""

    def __init__(self, command_router: CommandRouterClient) -> None:
        self._command_router = command_router

    def submit(self, request: ExecutionRequest) -> Result[Any]:
        """ExecutionRequestをCommand Router向けRaw Command形式へ変換し、receive()へ渡す。"""
        raw_command = self._to_raw_command(request)

        result = self._command_router.receive(raw_command)

        if not result.success:
            reason = getattr(result.error, "message", None) or "Command Router receive() failed"
            return Result(success=False, value=None, error=CommandRouterDispatchError(reason))

        return Result(success=True, value=result.value, error=None)

    @staticmethod
    def _to_raw_command(request: ExecutionRequest) -> RawCommand:
        """ExecutionRequestをCommand Router(M05)のRaw Command形状(属性アクセス前提)へ変換する。

        - command_id : request_id をそのまま用いる(Command Router側の一意識別子相当)。
        - source     : request.source をそのまま用いる(起動元。設計書1節の適用対象に準拠)。
        - user_id    : ExecutionRequestはuser_idを持たないため、Scheduler内部起動コマンド
                       であることを示す固定値を用いる。
        - timestamp  : request.requested_at をそのまま用いる(型はdatetimeのまま、文字列化しない)。
        - command    : workflow_id をコマンド文字列として渡す。Command Routerのclassify()/
                       route()呼び出しはSchedulerの責務外(4.2節)であり、Schedulerはreceive()
                       の呼び出しのみを保証する。
        - attachments: ExecutionRequestに相当概念がないため空リスト。
        - metadata   : trigger_type/retry_count/payloadをそのまま保持し、情報欠落を防ぐ
                       (Command Routerはmetadataの値をログ出力しないため機密混入も生じない)。
        """
        return RawCommand(
            command_id=request.request_id,
            source=request.source,
            user_id=_SCHEDULER_USER_ID,
            timestamp=request.requested_at,
            command=request.workflow_id,
            attachments=[],
            metadata={
                "trigger_type": request.trigger_type.value,
                "retry_count": request.retry_count,
                "payload": dict(request.payload),
            },
        )
