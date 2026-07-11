"""IS19 6章のログ項目を組み立てて`get_logger()`経由で出力するための薄いヘルパー。

Context本文・Knowledge本文・Repository情報・Secretを引数に取らない設計とし、
誤って本文を渡せないようにする(引数はプリミティブ型 / `WorkflowType` Enumのみに限定する)。
"""

from context_manager.types import WorkflowType
from foundation.logger import get_logger

logger = get_logger("context_manager")


def log_build_result(
    workflow_id: str,
    workflow_type: WorkflowType,
    context_version: str,
    context_size: int,
    validation_result: bool,
) -> None:
    """設計書4.6節の記録項目(workflow_id, workflow_type, context_version, context_size,
    validation_result)のみを出力する。timestampはFoundation LoggerのFormatterが自動付与する。"""
    logger.info(
        "workflow_id=%s workflow_type=%s context_version=%s context_size=%d validation_result=%s",
        workflow_id,
        workflow_type.value,
        context_version,
        context_size,
        validation_result,
    )
