"""ロギングユーティリティ(IS14 6節)。

`foundation.logger.get_logger("scheduler")` で取得したLoggerのみを使用する。
出力項目は設計書4.5の通り `timestamp`/`workflow_id`/`trigger_type`/`execution_result`/
`retry_count`/`duration` の6項目に固定し、Secret/Access Token/Credential系フィールドは
出力しない。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from logging import Logger
from typing import Any

_SENSITIVE_KEYS = frozenset({"secret", "token", "access_token", "credential", "password", "api_key"})
_MASK = "***REDACTED***"


def _normalize_key(key: Any) -> str:
    """キーの大小文字・スネーク/キャメル差異を吸収するため英数字のみを小文字化して比較する。"""
    return "".join(ch for ch in str(key).lower() if ch.isalnum())


_SENSITIVE_KEYS_NORMALIZED = frozenset(_normalize_key(key) for key in _SENSITIVE_KEYS)


def _is_sensitive_key(key: Any) -> bool:
    return _normalize_key(key) in _SENSITIVE_KEYS_NORMALIZED


def sanitize_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """payload内のSecret/Access Token/Credential系フィールドを再帰的にマスキングする。"""
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, Mapping):
            sanitized[key] = sanitize_payload(value)
        elif _is_sensitive_key(key):
            sanitized[key] = _MASK
        else:
            sanitized[key] = value
    return sanitized


def log_execution(
    logger: Logger,
    *,
    workflow_id: str,
    trigger_type: str,
    execution_result: str,
    retry_count: int,
    duration_seconds: float | None,
    timestamp: datetime | None = None,
) -> None:
    """設計書4.5の6項目のみを構造化してINFO/ERRORログとして出力する。

    payloadやconfiguration値そのものは本関数の引数に含めない(関数シグネチャレベルで
    Secret/Access Token/Credential混入を防止する)。
    """
    ts = timestamp or datetime.now(UTC)
    level_method = logger.error if execution_result == "FAILURE" else logger.info
    level_method(
        "timestamp=%s workflow_id=%s trigger_type=%s execution_result=%s " "retry_count=%s duration=%s",
        ts.isoformat(),
        workflow_id,
        trigger_type,
        execution_result,
        retry_count,
        duration_seconds,
    )
