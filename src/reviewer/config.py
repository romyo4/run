"""ConfigurationClient経由のレビュー設定取得(IS12 4.3 / F03)。"""

from __future__ import annotations

from dataclasses import dataclass

from foundation.interfaces import ConfigurationClient
from foundation.result import Result

MODULE_NAME = "reviewer"

__all__ = ["MODULE_NAME", "ReviewerConfig", "get_reviewer_config"]


@dataclass
class ReviewerConfig:
    min_business_score: float
    blocker_severity_blocks_approval: bool


def get_reviewer_config(client: ConfigurationClient) -> Result[ReviewerConfig]:
    """ConfigurationClient.get(MODULE_NAME, key) を用いてレビュー設定を取得する(F03)。

    Foundation自体は値をキャッシュしないため、Reviewer側でも呼び出しごとに取得する。
    いずれかのキー取得が失敗した場合、その時点のエラーをそのまま返す(Safety原則)。
    """
    min_business_score_result = client.get(MODULE_NAME, "min_business_score")
    if not min_business_score_result.success:
        return Result(success=False, error=min_business_score_result.error)

    blocker_result = client.get(MODULE_NAME, "blocker_severity_blocks_approval")
    if not blocker_result.success:
        return Result(success=False, error=blocker_result.error)

    return Result(
        success=True,
        value=ReviewerConfig(
            min_business_score=min_business_score_result.value,
            blocker_severity_blocks_approval=blocker_result.value,
        ),
    )
