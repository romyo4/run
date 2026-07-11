"""設計書3.4節の権限一覧をハードコードしたMVPデフォルトテーブル。

MVPでは外部ファイル・DBを持たず、この定数がフェイルセーフ時にも使われる唯一の正規データである
(IS04 2. ファイル構成 / default_permissions.py)。

「表に無い組み合わせ=Deny」というフェイルセーフ方針(設計書4.3)のため、
テーブルには Allow のエントリのみを列挙し、Denyは「該当エントリが存在しない」ことで
暗黙的に表現する。
"""

from __future__ import annotations

from .models import Effect, Module, Operation, PermissionEntry

DEFAULT_PERMISSIONS: tuple[PermissionEntry, ...] = (
    PermissionEntry(Module.PLANNER, Operation.EXECUTION_PLAN_CREATE, Effect.ALLOW),
    PermissionEntry(Module.DESIGNER, Operation.DESIGN_CREATE, Effect.ALLOW),
    PermissionEntry(Module.EXECUTOR, Operation.PULL_REQUEST_CREATE, Effect.ALLOW),
    PermissionEntry(Module.REVIEWER, Operation.REVIEW_CREATE, Effect.ALLOW),
    PermissionEntry(Module.SCHEDULER, Operation.WORKFLOW_START, Effect.ALLOW),
    PermissionEntry(Module.KNOWLEDGE_MANAGER, Operation.KNOWLEDGE_UPDATE, Effect.ALLOW),
    PermissionEntry(Module.COMMAND_ROUTER, Operation.COMMAND_DISPATCH, Effect.ALLOW),
)
