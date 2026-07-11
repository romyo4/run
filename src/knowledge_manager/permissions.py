"""Knowledge更新許可ロール定義と権限判定関数(設計書3.5節)。

更新は Planner・Architect・Reviewer のみ許可し、Executor・Context Manager等
他モジュールは参照専用(read-only)とする。認証・OAuth等は一切扱わない。
"""

from __future__ import annotations

ALLOWED_UPDATE_ROLES: frozenset[str] = frozenset({"planner", "architect", "reviewer"})


def is_update_allowed(role: str) -> bool:
    """指定ロールがKnowledge更新を許可されているか判定する(設計書3.5節)。

    大文字小文字・前後の空白は区別しない。空文字列・Noneに相当する値はFalseとする。
    """
    if not role:
        return False
    return role.strip().lower() in ALLOWED_UPDATE_ROLES
