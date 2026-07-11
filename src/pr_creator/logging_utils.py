"""get_logger()経由のログ出力ヘルパー(IS11 6章)。Secret除外を一元化する。"""

from __future__ import annotations

import logging

__all__ = ["log_operation"]

_ALLOWED_FIELDS = (
    "workflow_id",
    "repository",
    "branch",
    "pull_request_number",
    "pull_request_url",
    "result",
)


def log_operation(logger: logging.Logger, level: int, **fields: object) -> None:
    """IS11 4.5で定めた項目のみを許可してログ出力する。

    許可リストにない引数(access_token, credential, secret等)を渡してもValueErrorとして
    拒否し、誤って機密情報を出力できないようにする(ホワイトリスト方式)。
    timestampはlogging.Formatterが自動付与するため、呼び出し引数には含めない。
    """
    unknown = set(fields) - set(_ALLOWED_FIELDS)
    if unknown:
        raise ValueError(f"許可されていないログ項目: {sorted(unknown)}")
    message = " ".join(f"{key}={value}" for key, value in fields.items())
    logger.log(level, message)
