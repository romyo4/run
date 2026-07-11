"""NotificationHistoryStore(通知履歴の記録、MVPはインメモリ)(IS15 4.3)。

publish()が生成したNotificationHistoryを保持する。MVPではプロセス内インメモリ
一覧のみ。永続化(DB等)は対象外。
"""

from __future__ import annotations

from foundation.result import Result
from notification.types import NotificationHistory


class NotificationHistoryStore:
    """publish()が生成したNotificationHistoryを保持する。

    MVPではプロセス内インメモリ一覧のみ。永続化(DB等)は対象外。
    """

    def __init__(self) -> None:
        self._histories: list[NotificationHistory] = []

    def append(self, history: NotificationHistory) -> Result[bool]:
        self._histories.append(history)
        return Result(success=True, value=True)

    def list_all(self) -> Result[list[NotificationHistory]]:
        return Result(success=True, value=list(self._histories))
