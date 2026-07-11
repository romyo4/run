"""get_logger()経由のログ出力ヘルパー(IS20仕様書6章)。

出力項目をキーワード専用引数として固定することで、Access Token・Secret・Credential・
Repository内容(File Content, Diff本文, Commit本文の全文)を誤って渡せないようにする。
"""

from __future__ import annotations

import logging

__all__ = ["log_operation"]


def log_operation(
    logger: logging.Logger,
    level: int,
    *,
    operation: str,
    repository: str,
    result: str,
    duration: float,
    branch: str = "-",
    pull_request: str = "-",
) -> None:
    """IS20仕様書6章で定めた項目を1行でログ出力する。

    timestampはfoundation.logger.get_logger()が設定するFormatterが自動付与するため、
    引数には含めない。
    """
    logger.log(
        level,
        "operation=%s repository=%s branch=%s pull_request=%s result=%s duration=%.3f",
        operation,
        repository,
        branch,
        pull_request,
        result,
        duration,
    )
