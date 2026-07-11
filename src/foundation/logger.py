"""共通ログ初期化ユーティリティ(設計書3.7節)。"""

import logging

from foundation.constants import LOG_FORMAT


def get_logger(module_name: str) -> logging.Logger:
    """module_nameに対応するLoggerを返す。

    出力フォーマットは 'timestamp | module_name | level | message' に統一する。
    既にハンドラが設定済みの場合は追加しない(多重初期化・重複ハンドラの防止)。
    """
    logger = logging.getLogger(module_name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
