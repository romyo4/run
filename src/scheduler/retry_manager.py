"""リトライ管理(IS14 4.4節)。

MVPでは最大3回の単純カウンタ方式のみを実装し、優先度・バックオフ戦略の高度化は
行わない(設計書4.3 リトライ回数)。
"""

from __future__ import annotations

from typing import ClassVar

from foundation.result import Result
from foundation.utils import generate_id, utc_now

from .exceptions import RetryLimitExceededError
from .models import FailedExecution, RetryRequest


class RetryManager:
    MAX_RETRY_COUNT: ClassVar[int] = 3  # 4.3 制約

    def __init__(self) -> None:
        self._retry_counts: dict[str, int] = {}

    def get_retry_count(self, workflow_id: str) -> int:
        return self._retry_counts.get(workflow_id, 0)

    def next_retry(self, failed_execution: FailedExecution) -> Result[RetryRequest]:
        """failed_execution.retry_count < MAX_RETRY_COUNT の場合のみRetryRequestを生成する。

        超過時はResult(success=False, error=RetryLimitExceededError)を返す。
        """
        if failed_execution.retry_count >= self.MAX_RETRY_COUNT:
            return Result(
                success=False,
                value=None,
                error=RetryLimitExceededError(
                    f"workflow_id={failed_execution.workflow_id} exceeded " f"max retry count of {self.MAX_RETRY_COUNT}"
                ),
            )

        new_retry_count = failed_execution.retry_count + 1
        self._retry_counts[failed_execution.workflow_id] = new_retry_count

        retry_request = RetryRequest(
            retry_request_id=generate_id(),
            original_request_id=failed_execution.request_id,
            workflow_id=failed_execution.workflow_id,
            retry_count=new_retry_count,
            requested_at=utc_now(),
        )
        return Result(success=True, value=retry_request, error=None)

    def reset(self, workflow_id: str) -> None:
        """正常終了時にリトライカウントを初期化する。"""
        self._retry_counts.pop(workflow_id, None)
