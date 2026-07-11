"""State Manager (M01) 固有例外(IS01 5章 / 設計書4.5)。

Foundationのエラー階層に該当するものが存在しない「排他エラー」「タイムアウト」を
FoundationErrorを継承して追加定義する(Foundation3.6に基づく)。
"""

from __future__ import annotations

from foundation.errors import FoundationError


class StateLockError(FoundationError):
    """同一task_idに対する同時更新が競合した場合に送出する。"""


class StateLockTimeoutError(StateLockError):
    """排他ロック取得がタイムアウトした場合に送出する。"""
