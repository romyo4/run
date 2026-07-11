"""Command Router固有例外(IS05仕様書5節)。

Foundationの`FoundationError`階層を継承する。新しい基底例外は追加せず、
既存階層のサブクラスとしてのみ定義する(M00 3.6節)。
"""

from __future__ import annotations

from foundation.errors import NotFoundError, ValidationError


class UnknownCommandError(ValidationError):
    """classify()がCommandType.UNKNOWNと判定したコマンドをroute()する際に送出。
    実行しない・ログ出力・ユーザーへの通知(Result経由で呼び出し元へ伝播)を行う。
    """


class DispatchTargetNotRegisteredError(NotFoundError):
    """dispatch()時にdestinationに対応するCommandHandlerが未登録の場合に送出。"""
