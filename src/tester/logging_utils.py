"""ログ出力補助(IS10 6節)。所定8項目の整形、およびSecret/Token/Credentialのマスク処理。"""

from __future__ import annotations

import re

__all__ = ["build_log_message", "sanitize_for_log"]

# key=value形式で出力される、Secret/Token/Credentialを示唆するキー名(大文字小文字を区別しない)。
_SECRET_KEY_PATTERN = re.compile(r"(?im)^.*\b(token|password|secret|api[_-]?key|credential)\b\s*[:=].*$")
# 長い英数字トークン様文字列(20文字以上の英数字・記号の連続)。
_LONG_TOKEN_PATTERN = re.compile(r"\b[A-Za-z0-9_\-\.]{20,}\b")

_REDACTED = "***REDACTED***"


def sanitize_for_log(text: str) -> str:
    """ログへ出力する文字列から、Secret/Token/Credentialに該当しうる文字列をマスクする。

    - 'token' / 'password' / 'secret' / 'api_key' / 'credential' 等をキー名に含む行は、
      行全体をマスクする。
    - 長い英数字トークン様文字列(20文字以上)は個別にマスクする。
    """
    if not text:
        return text
    masked = _SECRET_KEY_PATTERN.sub(_REDACTED, text)
    masked = _LONG_TOKEN_PATTERN.sub(_REDACTED, masked)
    return masked


def build_log_message(
    workflow_id: str,
    build_result: str,
    lint_result: str,
    test_result: str,
    quality_gate: str,
    duration_seconds: float,
    result: str,
) -> str:
    """固定8項目(timestampはlogging側で付与)をkey=value形式の1行に整形する。"""
    fields = {
        "workflow_id": workflow_id,
        "build_result": build_result,
        "lint_result": lint_result,
        "test_result": test_result,
        "quality_gate": quality_gate,
        "duration": f"{duration_seconds:.3f}",
        "result": result,
    }
    return " | ".join(f"{key}={sanitize_for_log(str(value))}" for key, value in fields.items())
